"""Track assembly and kinematics.

Raw tracker output (one row per processed frame and object) is grouped per track id,
resampled onto the uniform processing grid (short gaps are linearly interpolated) and
smoothed. Every rule works on these arrays:

* ``gp``      ground point (bottom centre of the box), smoothed, pixels
* ``vel``     ground-point velocity, pixels / s
* ``scale``   object size sqrt(w * h), pixels - used to normalise speeds and distances
* ``nspeed``  speed / scale, "object sizes per second" (roughly perspective invariant)
* ``heading`` direction of motion in image coordinates (radians, NaN when too slow)
* ``edge``    the box touches the frame border (or did within the smoothing window): the object is
              cut off, so its ground point and size - and every speed derived from them - are not
              trustworthy. A car leaving at the bottom of the frame seems to stop there.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

from .detector import category_of


@dataclass
class Track:
    tid: int
    category: str
    cls_id: int
    t: np.ndarray            # (M,) uniform time grid, seconds
    box: np.ndarray          # (M, 4) xyxy, interpolated where unobserved
    observed: np.ndarray     # (M,) bool
    conf: np.ndarray         # (M,) detection score (0 where interpolated)
    gp: np.ndarray           # (M, 2)
    vel: np.ndarray          # (M, 2)
    scale: np.ndarray        # (M,)
    meta: dict = field(default_factory=dict)
    edge: np.ndarray | None = None   # (M,) bool, see module docstring

    def __post_init__(self) -> None:
        if self.edge is None or len(self.edge) != len(self.t):
            self.edge = np.zeros(len(self.t), dtype=bool)

    @property
    def reliable(self) -> np.ndarray:
        """Samples whose box is fully inside the frame."""
        return ~self.edge

    @property
    def t0(self) -> float:
        return float(self.t[0])

    @property
    def t1(self) -> float:
        return float(self.t[-1])

    @property
    def duration(self) -> float:
        return self.t1 - self.t0

    @property
    def speed(self) -> np.ndarray:
        return np.hypot(self.vel[:, 0], self.vel[:, 1])

    @property
    def nspeed(self) -> np.ndarray:
        return self.speed / self.scale

    def heading(self, min_nspeed: float = 0.3) -> np.ndarray:
        h = np.arctan2(self.vel[:, 1], self.vel[:, 0])
        h[self.nspeed < min_nspeed] = np.nan
        return h

    def index_at(self, t: float) -> int:
        return int(np.clip(np.searchsorted(self.t, t), 0, len(self.t) - 1))

    def slice(self, t_start: float, t_end: float) -> np.ndarray:
        return (self.t >= t_start) & (self.t <= t_end)

    @property
    def is_vehicle(self) -> bool:
        return self.category in ("vehicle", "two_wheeler")


def _odd_window(n_samples: int, want: int) -> int:
    w = min(want, n_samples if n_samples % 2 == 1 else n_samples - 1)
    return w if w >= 3 else 0


def _smooth(values: np.ndarray, dt: float, smooth_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Savitzky-Golay smoothed values and their time derivative (per second)."""
    n = len(values)
    want = int(round(smooth_s / dt)) | 1
    w = _odd_window(n, max(want, 5))
    if w >= 5:
        sm = savgol_filter(values, w, 2, axis=0, mode="interp")
        d = savgol_filter(values, w, 2, deriv=1, delta=dt, axis=0, mode="interp")
    elif n >= 2:
        sm = values.copy()
        d = np.gradient(values, dt, axis=0)
    else:
        sm = values.copy()
        d = np.zeros_like(values)
    return sm, d


def edge_mask(box: np.ndarray, frame_size: tuple[int, int] | None, margin: float = 0.01,
              grow: int = 0) -> np.ndarray:
    """Samples whose xyxy box comes within ``margin`` (a fraction of the frame width / height; the
    detector often stops a cut-off object's box a few pixels short of the border) of the frame
    border, grown by ``grow`` samples on both sides (what smoothing spreads the clipped values into)."""
    box = np.asarray(box, dtype=np.float64).reshape(-1, 4)
    if frame_size is None or not frame_size[0] or not frame_size[1]:
        return np.zeros(len(box), dtype=bool)
    w, h = frame_size
    mx, my = max(2.0, margin * w), max(2.0, margin * h)
    edge = (box[:, 0] <= mx) | (box[:, 1] <= my) | (box[:, 2] >= w - 1 - mx) | (box[:, 3] >= h - 1 - my)
    if grow > 0 and edge.any():
        edge = np.convolve(edge.astype(np.int32), np.ones(2 * grow + 1, dtype=np.int32), mode="same") > 0
    return edge


def build_tracks(rows: np.ndarray, fps: float, stride: int, smooth_s: float = 0.8,
                 min_track_s: float = 0.6, frame_size: tuple[int, int] | None = None) -> list[Track]:
    """Build tracks from tracker rows ``[frame_idx, tid, x1, y1, x2, y2, conf, cls]``.
    ``frame_size`` (width, height) enables the ``edge`` flag of the tracks."""
    tracks: list[Track] = []
    if len(rows) == 0:
        return tracks
    dt = stride / fps
    rows = rows[np.lexsort((rows[:, 0], rows[:, 1]))]
    tids, starts = np.unique(rows[:, 1], return_index=True)
    bounds = list(starts[1:]) + [len(rows)]
    for tid, a, b in zip(tids, starts, bounds):
        r = rows[a:b]
        frames = r[:, 0].astype(int)
        grid = np.arange(frames[0], frames[-1] + 1, stride)
        if len(grid) * dt < min_track_s:
            continue
        pos = np.searchsorted(grid, frames)
        observed = np.zeros(len(grid), dtype=bool)
        observed[pos] = True
        box = np.empty((len(grid), 4), dtype=np.float64)
        for k in range(4):
            box[:, k] = np.interp(grid, frames, r[:, 2 + k])
        conf = np.zeros(len(grid))
        conf[pos] = r[:, 6]
        # Category: confidence-weighted vote over the track's detections.
        votes: dict[str, float] = {}
        cls_votes: dict[int, float] = {}
        for c, s in zip(r[:, 7].astype(int), r[:, 6]):
            votes[category_of(c)] = votes.get(category_of(c), 0.0) + float(s)
            cls_votes[c] = cls_votes.get(c, 0.0) + float(s)
        category = max(votes.items(), key=lambda kv: kv[1])[0]
        cls_id = max(cls_votes.items(), key=lambda kv: kv[1])[0]

        w = box[:, 2] - box[:, 0]
        h = box[:, 3] - box[:, 1]
        raw_scale = np.sqrt(np.clip(w * h, 1.0, None))
        size = int(round(1.0 / dt)) | 1
        scale = median_filter(raw_scale, size=min(size, len(raw_scale)), mode="nearest")
        scale = np.clip(scale, 4.0, None)
        ground = np.stack([(box[:, 0] + box[:, 2]) / 2, box[:, 3]], axis=1)
        gp, vel = _smooth(ground, dt, smooth_s)
        grow = _odd_window(len(grid), max(int(round(smooth_s / dt)) | 1, 5)) // 2
        tracks.append(Track(
            tid=int(tid), category=category, cls_id=int(cls_id), t=grid / fps, box=box,
            observed=observed, conf=conf, gp=gp, vel=vel, scale=scale,
            edge=edge_mask(box, frame_size, grow=grow),
        ))
    return tracks


def filled_heading(tr: Track, min_nspeed: float = 0.3, default: float | None = None) -> np.ndarray:
    """Heading where the gaps (too slow to tell, or cut off by the frame border) carry the last
    known heading forward: a car waiting at a stop line still points where it was driving. Before
    the first known heading: ``default`` if given, else the first known heading. All NaN when the
    track never moves and no default is given."""
    h = tr.heading(min_nspeed)
    h[tr.edge] = np.nan
    valid = ~np.isnan(h)
    if not valid.any():
        return np.full(len(h), np.nan if default is None else float(default))
    last = np.maximum.accumulate(np.where(valid, np.arange(len(h)), -1))
    out = h[np.maximum(last, 0)]
    out[last < 0] = h[np.argmax(valid)] if default is None else float(default)
    return out


def unwrap_heading(h: np.ndarray) -> np.ndarray:
    """Unwrap a heading series with NaNs (NaNs are carried forward for unwrapping only)."""
    out = h.copy()
    valid = ~np.isnan(h)
    if valid.sum() < 2:
        return out
    out[valid] = np.unwrap(h[valid])
    return out


def intervals(mask: np.ndarray, t: np.ndarray, min_len: float = 0.0,
              max_gap: float = 0.0) -> list[tuple[float, float]]:
    """Maximal runs of True in ``mask`` as (t_start, t_end); gaps up to ``max_gap`` are bridged."""
    runs: list[list[float]] = []
    if len(mask) == 0:
        return []
    idx = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(np.int8), [0]])))
    for a, b in zip(idx[::2], idx[1::2]):
        start, end = float(t[a]), float(t[b - 1])
        if runs and start - runs[-1][1] <= max_gap:
            runs[-1][1] = end
        else:
            runs.append([start, end])
    return [(a, b) for a, b in runs if b - a >= min_len]


def hysteresis(values: np.ndarray, low: float, high: float, below: bool = True) -> np.ndarray:
    """Boolean state that turns on when ``values`` crosses ``low`` and off when it crosses ``high``
    (for ``below=True``: on while the value stays under ``high`` after dipping under ``low``)."""
    state = np.zeros(len(values), dtype=bool)
    on = False
    for i, v in enumerate(values):
        if below:
            on = (v < high) if on else (v < low)
        else:
            on = (v > low) if on else (v > high)
        state[i] = on
    return state
