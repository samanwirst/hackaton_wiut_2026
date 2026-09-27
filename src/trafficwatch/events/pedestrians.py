"""Official pedestrian classes: roadway entry outside a crossing, and failure to yield.

The organiser definitions do not classify crossing on red as jaywalking and do not exempt
drivers from failure_to_yield when the pedestrian signal is red.
"""
from __future__ import annotations

import numpy as np

from ..geometry import lookup
from ..tracks import Track, intervals
from .common import Context, Event


def _crossing_axis(poly: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Walking direction over a crossing (its long axis) and the extent of the crossing along it."""
    pts = np.asarray(poly, dtype=np.float64)
    centred = pts - pts.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    u = vt[0]
    s = pts @ u
    return u, float(s.min()), float(s.max())


def jaywalking(ctx: Context) -> list[Event]:
    p = ctx.params("jaywalking")
    events = []
    if not ctx.scene.has_road:
        return events  # without a carriageway mask we cannot tell road from pavement
    road = ctx.eroded_road(ctx.px(p.get("road_margin_px", 8)))
    crossing = ctx.dilated(ctx.scene.crosswalk_map, ctx.px(p["crosswalk_margin_px"]))
    for ped in ctx.pedestrians:
        # a road user cut off by the frame border has no reliable feet (and a half-visible car at
        # the edge is easily taken for a person)
        on_road = lookup(road, ped.gp, outside=False) & ped.reliable
        if crossing is not None:
            on_road &= lookup(crossing, ped.gp, outside=-1) < 0
        for a, b in intervals(on_road, ped.t, min_len=p["min_s"], max_gap=0.5):
            m = ped.slice(a, b)
            travel = np.hypot(*(ped.gp[m] - ped.gp[m][0]).T).max() / np.median(ped.scale[m])
            if travel < p.get("min_travel_scale", 0.0):
                continue  # not walking: a rider waiting with the traffic, or a false detection
            events.append(Event(a, b, "jaywalking", tracks=(ped.tid,)))
    return events


def _net_speed(tr: Track, t: np.ndarray, half_s: float = 0.75) -> np.ndarray:
    """Displacement over [t - half_s, t + half_s] in object sizes per second: jitter of someone
    standing still averages out, walking does not."""
    i0 = np.searchsorted(tr.t, t - half_s).clip(0, len(tr.t) - 1)
    i1 = np.searchsorted(tr.t, t + half_s).clip(0, len(tr.t) - 1)
    span = np.maximum(tr.t[i1] - tr.t[i0], 1e-6)
    return np.hypot(*(tr.gp[i1] - tr.gp[i0]).T) / tr.scale[np.searchsorted(tr.t, t).clip(0, len(tr.t) - 1)] / span


def failure_to_yield(ctx: Context) -> list[Event]:
    p = ctx.params("failure_to_yield")
    cw_map = ctx.scene.crosswalk_map
    if cw_map is None:
        return []
    ped_map = ctx.dilated(cw_map, ctx.px(p["ped_margin_px"]))
    peds = ctx.pedestrians
    polys = ctx.scene.crosswalk_polys
    events = []
    for veh in ctx.vehicles:
        cw = np.where(veh.reliable, lookup(cw_map, veh.gp, outside=-1), -1)
        for c in np.unique(cw[cw >= 0]):
            axis = _crossing_axis(polys[c])[0] if c < len(polys) else None
            for a, b in intervals(cw == c, veh.t, min_len=0.2, max_gap=0.3):
                m = veh.slice(a, b)
                if np.median(veh.nspeed[m]) < p["min_vehicle_nspeed"]:
                    continue  # the vehicle crept or stopped: it yielded
                if axis is not None and veh.category == "two_wheeler":
                    v = veh.vel[m].mean(axis=0)
                    if abs(v @ axis) > 0.7 * np.hypot(*v):
                        continue  # a cyclist riding over the crossing with the pedestrians is crossing too
                for ped in peds:
                    ia, ib = ctx.common(veh, ped)
                    sel = (veh.t[ia] >= a) & (veh.t[ia] <= b)
                    if not sel.any():
                        continue
                    ia, ib = ia[sel], ib[sel]
                    # walking on the crossing or stepping onto it (at its edge now, on it within
                    # step_on_s); someone waiting at the kerb edge looks just the same in the image
                    on_now = lookup(cw_map, ped.gp, outside=-1) == c
                    near = lookup(ped_map, ped.gp[ib], outside=-1) == c
                    j = np.searchsorted(ped.t, ped.t[ib] + p["step_on_s"], side="right")
                    soon = np.array([on_now[i:k].any() for i, k in zip(ib, j)], dtype=bool)
                    on_cw = near & soon & (_net_speed(ped, ped.t[ib]) >= p["ped_moving_nspeed"]) & ped.reliable[ib]
                    dist = np.hypot(*(ped.gp[ib] - veh.gp[ia]).T) / veh.scale[ia]
                    if (on_cw & (dist <= p["max_ped_distance_scale"])).any():
                        events.append(Event(a, b, "failure_to_yield", tracks=(veh.tid, ped.tid)))
                        break
    return events
