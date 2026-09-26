"""Part B: causal accident anticipation.

Every k-th frame we detect and track road users, keep a short history per track, and turn
three kinds of evidence into a risk score:

* conflict: constant-velocity closest-approach between two road users (one a vehicle) that
  predicts contact within the horizon; the sooner and the closer, the higher the risk,
* hard braking of a vehicle,
* a vehicle moving against the learned traffic direction.

Scores are combined as independent evidences (1 - prod(1 - r)), held with an exponential decay
so an alarm does not flicker, and mapped to a probability with a logistic calibration.
Only frames already received are used; the estimator never opens the video file.
"""
from __future__ import annotations

import math
import os
import sys
import traceback
from collections import defaultdict, deque

import numpy as np

from .config import load_config
from .detector import Detections, category_of, get_detector
from .geometry import same_pace
from .runtime import cuda_available, device_for, set_determinism, stride_for
from .scene import Scene, load_scene
from .tracking import make_tracker
from .tracks import edge_mask


class _History:
    """Recent ground points of one track."""

    def __init__(self, maxlen: int):
        self.t: deque = deque(maxlen=maxlen)
        self.xy: deque = deque(maxlen=maxlen)
        self.scale: deque = deque(maxlen=maxlen)
        self.edge: deque = deque(maxlen=maxlen)      # box touches the frame border
        self.votes: dict[str, float] = defaultdict(float)

    def add(self, t: float, box: np.ndarray, conf: float, cls_id: int, edge: bool = False) -> None:
        x1, y1, x2, y2 = box
        self.t.append(t)
        self.xy.append(((x1 + x2) / 2.0, y2))
        self.scale.append(max(4.0, math.sqrt(max((x2 - x1) * (y2 - y1), 1.0))))
        self.edge.append(bool(edge))
        self.votes[category_of(cls_id)] += conf

    @property
    def category(self) -> str:
        return max(self.votes.items(), key=lambda kv: kv[1])[0]

    def velocity(self, t_now: float, window: float, offset: float = 0.0) -> np.ndarray | None:
        """Least-squares velocity over [t_now - offset - window, t_now - offset]."""
        t = np.fromiter(self.t, float)
        sel = (t <= t_now - offset + 1e-6) & (t >= t_now - offset - window - 1e-6)
        sel &= ~np.fromiter(self.edge, bool)      # a cut-off box moves (or stops) for no reason
        if sel.sum() < 3:
            return None
        tt = t[sel] - t[sel].mean()
        xy = np.asarray(self.xy)[sel]
        den = (tt ** 2).sum()
        if den < 1e-9:
            return None
        return (tt[:, None] * (xy - xy.mean(axis=0))).sum(axis=0) / den


def _opposite(va: np.ndarray, sa: float, vb: np.ndarray, sb: float, min_nspeed: float = 0.3) -> bool:
    """Both moving and driving towards each other (headings more than 135 degrees apart)."""
    na, nb = math.hypot(*va), math.hypot(*vb)
    if na / sa < min_nspeed or nb / sb < min_nspeed:
        return False
    return float(va @ vb) / (na * nb) < math.cos(math.radians(135))


class CausalRisk:
    def __init__(self, cfg: dict | None = None, *, with_detector: bool = True):
        self.cfg = cfg or load_config()
        self.p = self.cfg["risk"]
        set_determinism(int(self.cfg.get("seed", 0)))
        want = os.environ.get("TRAFFICWATCH_PROFILE") or self.p.get("profile", "auto")
        gpu = want == "gpu" or (want == "auto" and cuda_available())
        device = device_for(gpu)
        self.target_fps = self.p["target_fps"] if gpu else self.p.get("target_fps_cpu", self.p["target_fps"])
        dcfg = self.cfg.get("detector", {})
        self.detector = get_detector(self.p["weights_gpu" if gpu else "weights_cpu"], device,
                                     int(self.p["imgsz"]), device.startswith("cuda"), 1, float(dcfg.get("conf", 0.1)),
                                     float(dcfg.get("iou", 0.6)), float(dcfg.get("vehicle_merge_iou", 0.7))) if with_detector else None
        self.scene: Scene | None = None
        self.reset({"fps": 25.0, "width": 0, "height": 0})

    def reset(self, meta: dict, stride: int | None = None) -> None:
        """Start a new video. ``stride`` overrides the frame subsampling (1 when the caller already
        feeds only the frames to process, e.g. the demo reusing Part A detections via update())."""
        fps = float(meta.get("fps") or 25.0)
        self.stride = stride or stride_for(fps, self.target_fps)
        self.tracker = make_tracker(self.cfg, fps / self.stride)
        maxlen = int(math.ceil(self.p["history_s"] * fps / self.stride)) + 2
        self.hist: dict[int, _History] = defaultdict(lambda: _History(maxlen))
        self.i = 0
        self.last_t = None
        self.held = 0.0
        self.score = self._calibrate(0.0)
        w, h = int(meta.get("width") or 0), int(meta.get("height") or 0)
        self.frame_size = (w, h) if w and h else None
        self.scene = load_scene(self.cfg, w, h) if w and h else None

    # -- public API ------------------------------------------------------------------------
    def step(self, frame: np.ndarray, t_sec: float) -> float:
        if self.detector is None:
            raise RuntimeError("This risk estimator accepts detections via update(), not video frames.")
        i = self.i
        self.i += 1
        if i % self.stride:
            return self.score
        try:
            if self.frame_size is None:
                self.frame_size = (frame.shape[1], frame.shape[0])
            if self.scene is None:
                self.scene = load_scene(self.cfg, frame.shape[1], frame.shape[0])
            return self.update(self.detector([frame])[0], t_sec)
        except Exception:  # never let one bad frame end the whole risk curve
            print(f"[trafficwatch] risk step failed at t={t_sec:.2f}:\n{traceback.format_exc()}",
                  file=sys.stderr)
            return self.score

    def update(self, det: Detections, t_sec: float) -> float:
        """Advance with the detections of one processed frame."""
        tracks = self.tracker.update(det)
        edges = edge_mask(tracks[:, :4], self.frame_size) if len(tracks) else []
        active = []
        for (x1, y1, x2, y2, tid, conf, cls_id), edge in zip(tracks, edges):
            h = self.hist[int(tid)]
            h.add(t_sec, np.array([x1, y1, x2, y2]), float(conf), int(cls_id), bool(edge))
            active.append(int(tid))
        for tid in [k for k, h in self.hist.items() if h.t and t_sec - h.t[-1] > self.p["history_s"]]:
            del self.hist[tid]
        raw = self._raw_risk(active, t_sec)
        dt = 0.0 if self.last_t is None else max(t_sec - self.last_t, 0.0)
        self.last_t = t_sec
        self.held = max(raw, self.held * math.exp(-dt / self.p["decay_s"]))
        self.score = self._calibrate(self.held)
        return self.score

    # -- internals ---------------------------------------------------------------------------
    def _calibrate(self, x: float) -> float:
        z = self.p["calib_a"] * x + self.p["calib_b"]
        return float(1.0 / (1.0 + math.exp(-z)))

    def _raw_risk(self, active: list[int], t: float) -> float:
        p = self.p
        ww = self.cfg["rules"]["wrong_way"]
        states = []
        for tid in active:
            h = self.hist[tid]
            cat = h.category
            if cat not in ("vehicle", "two_wheeler", "person") or h.edge[-1]:
                continue
            v = h.velocity(t, 0.6)
            if v is None:
                continue
            states.append((cat, np.asarray(h.xy[-1]), v, h.scale[-1], h))
        risks = []
        # pairwise conflicts
        for a in range(len(states)):
            ca, pa, va, sa, _ = states[a]
            for b in range(a + 1, len(states)):
                cb, pb, vb, sb, _ = states[b]
                if ca == "person" and cb == "person":
                    continue
                if "person" in (ca, cb) and math.hypot(*(vb if ca == "person" else va)) / (sb if ca == "person" else sa) < p["min_vehicle_nspeed"]:
                    continue      # someone walking past a vehicle that stands still
                s = 0.5 * (sa + sb)
                r = (pb - pa) / s
                if math.hypot(*r) > p["pair_radius_scale"]:
                    continue
                v = (vb - va) / s
                vv = float(v @ v)
                if vv < p["min_rel_nspeed"] ** 2:
                    continue
                tcpa = -float(r @ v) / vv
                if not 0.0 < tcpa <= p["horizon_s"]:
                    continue
                dcpa = math.hypot(*(r + v * tcpa))
                if dcpa >= p["collision_scale"]:
                    continue
                if dcpa >= p["head_on_scale"] and _opposite(va, sa, vb, sb):
                    continue      # passing in the opposite lane, not a head-on course
                if same_pace(va, sa, vb, sb, p["same_pace_ratio"])[0]:
                    continue      # one behind the other at the same pace: perspective, not closing
                closeness = 1.0 - dcpa / p["collision_scale"]
                urgency = 1.0 if tcpa <= p["ttc_full_s"] else (p["horizon_s"] - tcpa) / (p["horizon_s"] - p["ttc_full_s"])
                risks.append(closeness * urgency)
        # hard braking and wrong-way motion
        for cat, pos, v, s, h in states:
            if cat == "person":
                continue
            v_prev = h.velocity(t, 0.6, offset=0.6)
            if v_prev is not None:
                decel = (math.hypot(*v_prev) - math.hypot(*v)) / s / 0.6
                if decel > p["brake_decel"]:
                    risks.append(p["brake_weight"] * min(decel / (2 * p["brake_decel"]), 1.0))
            field = self.scene.flow_field if self.scene is not None else None
            if field is not None and math.hypot(*v) / s > ww["min_nspeed"]:
                prob, count, p_opp = field.query(pos[None], np.array([math.atan2(v[1], v[0])]))
                if (count[0] >= ww["field_min_count"] and prob[0] <= ww["field_p_max"]
                        and p_opp[0] >= ww["field_opposite_min"]):
                    risks.append(p["wrong_way_weight"])
        out = 1.0
        for r in risks:
            out *= 1.0 - min(max(r, 0.0), 1.0)
        return 1.0 - out


def risk_curve_from_perception(perception, cfg: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Part B scores for the frames Part A already detected, fed one by one through the same causal
    estimator. Used by the demo and the website export to avoid detecting every frame twice; the
    submission itself calls RiskEstimator.step on every frame."""
    # Only raw, per-frame detections are reused. Part A's smoothed tracks, rules and
    # future frames never enter this estimator. Do not load an unused second model:
    # the CPU Space intentionally ships only the nano detector, even on a CUDA host.
    est = CausalRisk(cfg, with_detector=False)
    info = perception.info
    est.reset({"fps": info.fps / perception.stride, "width": info.width, "height": info.height}, stride=1)
    scores = [est.update(det, t) for t, det in zip(perception.times, perception.detections)]
    return np.asarray(perception.times), np.asarray(scores)
