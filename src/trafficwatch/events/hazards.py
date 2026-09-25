"""Hazards: obstacles on the road (animals, static foreign objects) and fire / smoke."""
from __future__ import annotations

import cv2
import numpy as np

from ..tracks import intervals
from .common import Context, Event


def _occupied(ctx: Context, shape: tuple[int, int]) -> np.ndarray:
    """(N, h, w) mask of pixels covered by any tracked object at each background sample."""
    P = ctx.perception
    n = len(P.bg_times)
    h, w = shape
    sx, sy = w / ctx.info.width, h / ctx.info.height
    occ = np.zeros((n, h, w), dtype=bool)
    for tr in P.tracks:
        i0, i1 = np.searchsorted(P.bg_times, [tr.t0 - 0.5, tr.t1 + 0.5])
        for i in range(i0, i1):
            x1, y1, x2, y2 = tr.box[tr.index_at(P.bg_times[i])]
            occ[i, max(0, int(y1 * sy) - 2): int(y2 * sy) + 3, max(0, int(x1 * sx) - 2): int(x2 * sx) + 3] = True
    return occ


def _link_blobs(per_sample: list[list[tuple]], times: np.ndarray, max_gap: int = 2) -> list[dict]:
    """Chain blobs over time by box overlap."""
    chains: list[dict] = []
    for i, blobs in enumerate(per_sample):
        for (x, y, w, h) in blobs:
            box = np.array([x, y, x + w, y + h], dtype=float)
            for ch in chains:
                if i - ch["last"] <= max_gap:
                    b = ch["box"]
                    iw = max(0.0, min(b[2], box[2]) - max(b[0], box[0]))
                    ih = max(0.0, min(b[3], box[3]) - max(b[1], box[1]))
                    union = (b[2] - b[0]) * (b[3] - b[1]) + w * h - iw * ih
                    if union > 0 and iw * ih / union > 0.3:
                        ch.update(last=i, box=box)
                        break
            else:
                chains.append({"first": i, "last": i, "box": box})
    for ch in chains:
        ch["t0"], ch["t1"] = float(times[ch["first"]]), float(times[ch["last"]])
    return chains


def _static_objects(ctx: Context, p: dict) -> list[Event]:
    """Foreign objects that appear on the carriageway and stay: the short-term median of the frames
    differs from a long-term reference median, in a place no tracked road user explains."""
    P = ctx.perception
    if len(P.bg_frames) < 20 or not ctx.scene.has_road:
        return []
    frames = P.bg_frames
    n, h, w, _ = frames.shape
    road = cv2.resize(ctx.scene.road_mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    occ = _occupied(ctx, (h, w))
    area_min, area_max = p["static_min_area_frac"] * h * w, p["static_max_area_frac"] * h * w
    kernel = np.ones((3, 3), np.uint8)
    refs: dict[int, np.ndarray] = {}
    per_sample: list[list[tuple]] = []
    for i in range(n):
        key = i // 10
        if key not in refs:   # reference: wide window, excluding the neighbourhood of i
            c = key * 10 + 5
            idx = [j for j in range(max(0, c - 90), min(n, c + 90)) if abs(j - c) > 10]
            refs[key] = np.median(frames[idx], axis=0) if len(idx) >= 10 else np.median(frames, axis=0)
        lo, hi = max(0, i - 2), min(n, i + 3)
        short = np.median(frames[lo:hi], axis=0)
        diff = np.abs(short.astype(np.int16) - refs[key].astype(np.int16)).max(axis=2)
        diff = diff - np.median(diff[road]) if road.any() else diff
        fg = (diff > p["diff_thr"]) & road & ~occ[lo:hi].any(axis=0)
        fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        num, _, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
        per_sample.append([tuple(stats[k, :4]) for k in range(1, num)
                           if area_min <= stats[k, cv2.CC_STAT_AREA] <= area_max])
    events = []
    for ch in _link_blobs(per_sample, P.bg_times):
        if ch["t1"] - ch["t0"] >= p["static_min_s"]:
            end = ctx.duration if ch["last"] >= n - 2 else ch["t1"]
            events.append(Event(ch["t0"], end, "road_obstacle", info={"kind": "static"}))
    return events


def road_obstacle(ctx: Context) -> list[Event]:
    p = ctx.params("road_obstacle")
    events = []
    for tr in ctx.tracks:
        if tr.category != "animal":
            continue
        for a, b in intervals(ctx.scene.on_road(tr.gp), tr.t, min_len=p["animal_min_s"], max_gap=1.0):
            events.append(Event(a, b, "road_obstacle", tracks=(tr.tid,), info={"kind": "animal"}))
    return events + _static_objects(ctx, p)


def fire_smoke(ctx: Context) -> list[Event]:
    """Flickering, saturated orange/yellow blobs (flames). Static lamps do not flicker; lights of
    configured traffic signals are masked out."""
    p = ctx.params("fire_smoke")
    P = ctx.perception
    if len(P.bg_frames) < 3:
        return []
    n, h, w, _ = P.bg_frames.shape
    sx, sy = w / ctx.info.width, h / ctx.info.height
    keep = np.ones((h, w), dtype=bool)
    for x1, y1, x2, y2 in ctx.scene.lights.values():
        keep[int(y1 * sy): int(y2 * sy) + 1, int(x1 * sx): int(x2 * sx) + 1] = False
    kernel = np.ones((3, 3), np.uint8)
    masks = []
    for f in P.bg_frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        m = (hsv[..., 0] <= 25) & (hsv[..., 1] >= 120) & (hsv[..., 2] >= 200) & keep
        masks.append(cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool))
    fire = np.zeros(n, dtype=bool)
    for i in range(1, n):
        area = masks[i].sum()
        if area < p["min_area_frac"] * h * w:
            continue
        inter = (masks[i] & masks[i - 1]).sum()
        union = (masks[i] | masks[i - 1]).sum()
        fire[i] = union > 0 and inter / union < 0.8   # shape changes between samples: flicker
    return [Event(a, b, "fire_smoke") for a, b in intervals(fire, P.bg_times, min_len=p["min_s"], max_gap=2.0)]
