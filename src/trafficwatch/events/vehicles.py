"""Rules on single-vehicle trajectories: stopped vehicle, congestion, wrong way, turns, solid lines."""
from __future__ import annotations

import numpy as np

from ..detector import box_iou
from ..geometry import angle_diff, polyline_side, projection_param
from ..signal import AMBER, GREEN, RED
from ..tracks import Track, filled_heading, hysteresis, intervals, unwrap_heading
from .common import Context, Event
from .signals import _lines_with_signal, _past_line


def queued_at_signal(ctx: Context, tr: Track) -> tuple[np.ndarray, np.ndarray]:
    """Per sample, for a vehicle behind a signalised stop line (heading over it): ``waiting`` - the
    signal is red or amber; ``releasing`` - it turned green at most ``queue_release_s`` ago (the
    queue is still driving off)."""
    release = ctx.params("stopped_vehicle").get("queue_release_s", 20.0)
    waiting = np.zeros(len(tr.t), dtype=bool)
    releasing = np.zeros(len(tr.t), dtype=bool)
    for sl, sig in _lines_with_signal(ctx):
        fwd = float(np.arctan2(sl.forward[1], sl.forward[0]))
        head = filled_heading(tr, ctx.heading_min, default=fwd)
        u = projection_param(sl.a, sl.b, tr.gp)
        # far up the approach the lanes bend away on screen (perspective): cos > 0.3 still keeps out
        # the opposite direction and the cross traffic
        near = (_past_line(sl, tr.gp) < 0.5 * tr.scale) & (u > -0.3) & (u < 1.3) & (np.cos(head - fwd) > 0.3)
        for i in np.flatnonzero(near):
            state = sig.state_at(tr.t[i])
            waiting[i] |= state in (RED, AMBER)
            releasing[i] |= state == GREEN and sig.since(tr.t[i]) <= release
    return waiting, releasing


# --------------------------------------------------------------------------------------------
# stopped_vehicle
# --------------------------------------------------------------------------------------------
def _reference_heading(ctx: Context, tr: Track, t0: float, gp: np.ndarray) -> float | None:
    """Direction the vehicle was travelling before it stopped, else the usual direction here."""
    before = tr.slice(t0 - 3.0, t0) & (tr.nspeed > 0.5)
    if before.sum() >= 3:
        v = tr.vel[before].mean(axis=0)
        return float(np.arctan2(v[1], v[0]))
    if ctx.scene.flow_field is not None:
        ang, strength = ctx.scene.flow_field.dominant(gp[None])
        if strength[0] > 0.15:
            return float(ang[0])
    return None


def _flow_past(ctx: Context, stopped: Track, t0: float, t1: float, gp: np.ndarray, scale: float,
               heading: float | None, radius_scale: float) -> int:
    """Number of other vehicles that drive past the stopped one (same direction) during its stop."""
    n = 0
    radius = radius_scale * scale if heading is not None else 2.0 * scale
    for tr in ctx.vehicles:
        if tr.tid == stopped.tid or tr.t1 < t0 or tr.t0 > t1:
            continue
        m = tr.slice(t0, t1) & (tr.nspeed > 1.0)
        if not m.any():
            continue
        near = np.hypot(*(tr.gp[m] - gp).T) < radius
        if heading is not None:
            h = np.arctan2(tr.vel[m, 1], tr.vel[m, 0])
            near &= angle_diff(h, heading) < np.deg2rad(60)
            # it must drive past in a neighbouring lane and get ahead: the car in front of it in the
            # same lane driving off at green is not traffic flowing past a stopped vehicle
            u = np.array([np.cos(heading), np.sin(heading)])
            rel = tr.gp[m][near] - gp
            along = rel @ u
            lateral = np.abs(rel @ np.array([-u[1], u[0]]))
            if near.sum() >= 2 and np.median(lateral) >= 0.5 * scale and along.max() > 0.3 * scale:
                n += 1
        elif near.sum() >= 2:
            n += 1
    return n


def stopped_vehicle(ctx: Context) -> list[Event]:
    p = ctx.params("stopped_vehicle")
    if not ctx.scene.has_road:
        return []  # without the carriageway, cars parked at the kerb would all become events
    stops = []
    for tr in ctx.vehicles:
        # a vehicle cut off by the frame border seems to stand still: never trust those samples
        speed = np.where(tr.edge, np.inf, tr.nspeed)
        still = hysteresis(speed, p["stop_nspeed"], p["move_nspeed"], below=True)
        queued = None
        for a, b in intervals(still, tr.t, min_len=1.0):
            m = tr.slice(a, b)
            if queued is None:
                queued = queued_at_signal(ctx, tr)
            idx = np.flatnonzero(m)
            waiting, releasing = queued
            stops.append({"t0": a, "t1": b, "box": np.median(tr.box[m], axis=0), "tr": tr,
                          "scale": float(np.median(tr.scale[m])), "ids": [tr.tid],
                          # stopped for a red signal ... and drove off with the queue (or is still waiting)
                          "q0": bool(waiting[idx[0]]), "q1": bool(waiting[idx[-1]] or releasing[idx[-1]])})
    # One parked vehicle often gets several track ids (occlusions): join stationary fragments.
    stops.sort(key=lambda s: s["t0"])
    groups: list[dict] = []
    for s in stops:
        for g in groups:
            if s["t0"] - g["t1"] <= p["link_gap_s"] and box_iou(g["box"], s["box"])[0, 0] >= p["link_iou"]:
                if s["t1"] > g["t1"]:
                    g["t1"], g["q1"] = s["t1"], s["q1"]
                g["ids"] += s["ids"]
                break
        else:
            groups.append(dict(s))

    events = []
    for g in groups:
        dur = g["t1"] - g["t0"]
        if dur < p["min_stop_s"]:
            continue
        gp = np.array([(g["box"][0] + g["box"][2]) / 2, g["box"][3]])
        if not ctx.scene.on_road(gp[None])[0] or ctx.scene.in_parking(gp[None])[0]:
            continue
        if g["q0"] and g["q1"]:
            continue  # stopped at a red signal and drove off with the queue at green
        if dur < p["long_stop_s"]:
            heading = _reference_heading(ctx, g["tr"], g["t0"], gp)
            flow = _flow_past(ctx, g["tr"], g["t0"], g["t1"], gp, g["scale"], heading, p["flow_radius_scale"])
            if flow < p["flow_past_min"]:
                continue  # everything around it is stopped too: a queue, not a stopped vehicle
        end = ctx.duration if g["t1"] >= ctx.duration - 3 * ctx.dt else g["t1"]
        events.append(Event(g["t0"], end, "stopped_vehicle", tracks=tuple(g["ids"]),
                            info={"box": g["box"].round(1).tolist()}))
    return events


# --------------------------------------------------------------------------------------------
# congestion
# --------------------------------------------------------------------------------------------
def _direction_group(ctx: Context, pts: np.ndarray) -> np.ndarray:
    """Group id per point: hand-drawn direction regions, else the learned dominant direction
    quantised to 4 sectors, else a single group."""
    if ctx.scene.group_map is not None:
        return ctx.scene.group_at(pts).astype(int)
    if ctx.scene.flow_field is not None:
        ang, strength = ctx.scene.flow_field.dominant(pts)
        sector = (np.round(ang / (np.pi / 2)).astype(int) % 4)
        sector[strength < 0.1] = -1
        return sector
    return np.zeros(len(pts), dtype=int)


def _parked(ctx: Context, tr: Track) -> bool:
    """Never moved and visible for (almost) the whole video: a parked vehicle, not traffic."""
    return tr.nspeed.max() < 0.3 and tr.duration > 0.9 * ctx.duration


def congestion(ctx: Context) -> list[Event]:
    p = ctx.params("congestion")
    if not ctx.scene.has_road:
        return []
    bin_s = p["bin_s"]
    n_bins = int(np.ceil(ctx.duration / bin_s)) + 1
    stats: dict[int, dict[int, list]] = {}
    for tr in ctx.vehicles:
        if _parked(ctx, tr):
            continue
        on = ctx.scene.on_road(tr.gp) & ~ctx.scene.in_parking(tr.gp) & tr.reliable
        waiting, releasing = queued_at_signal(ctx, tr)
        on &= ~(waiting | releasing)         # a queue at a red signal is not congestion
        groups = _direction_group(ctx, tr.gp)
        bins = (tr.t / bin_s).astype(int)
        for b, g, v, ok in zip(bins, groups, tr.nspeed, on):
            if ok and g >= 0:
                stats.setdefault(int(g), {}).setdefault(int(b), []).append((tr.tid, v))
    events = []
    for g, per_bin in stats.items():
        jam = np.zeros(n_bins, dtype=bool)
        for b, items in per_bin.items():
            ids = {i for i, _ in items}
            speeds = np.array([v for _, v in items])
            jam[b] = (len(ids) >= p["min_vehicles"] and np.median(speeds) < p["crawl_nspeed"]
                      and (speeds < p["crawl_nspeed"]).mean() >= p["min_stopped_frac"])
        t_bins = np.arange(n_bins) * bin_s
        for a, b in intervals(jam, t_bins, min_len=p["min_duration_s"], max_gap=2 * bin_s):
            events.append(Event(a, min(b + bin_s, ctx.duration), "congestion", info={"group": g}))
    return events


# --------------------------------------------------------------------------------------------
# wrong_way
# --------------------------------------------------------------------------------------------
def wrong_way(ctx: Context) -> list[Event]:
    p = ctx.params("wrong_way")
    scene = ctx.scene
    lanes_with_dir = [ln for ln in scene.lanes if "direction" in ln]
    if not lanes_with_dir and scene.flow_field is None:
        return []
    events = []
    for tr in ctx.vehicles:
        head = tr.heading(ctx.heading_min)
        valid = ~np.isnan(head) & (tr.nspeed >= p["min_nspeed"]) & ~scene.in_intersection(tr.gp) & tr.reliable
        if valid.sum() < 3:
            continue
        wrong = np.zeros(len(tr.t), dtype=bool)
        if lanes_with_dir:
            lane = scene.lane_at(tr.gp)
            for k, ln in enumerate(scene.lanes):
                if "direction" not in ln:
                    continue
                d = np.asarray(ln["direction"], dtype=float)
                cos = np.cos(head - np.arctan2(d[1], d[0]))
                wrong |= valid & (lane == k) & (cos < p["lane_cos_max"])
        else:
            prob, count, p_opp = scene.flow_field.query(tr.gp, np.nan_to_num(head))
            wrong = valid & (count >= p["field_min_count"]) & (prob <= p["field_p_max"]) & \
                (p_opp >= p["field_opposite_min"])
        for a, b in intervals(wrong, tr.t, min_len=p["min_s"], max_gap=0.6):
            # still going the wrong way as it runs out of the frame: the event lasts until it is gone
            if tr.edge[tr.t > b].all():
                b = tr.t1
            end = ctx.duration if b >= ctx.duration - 2 * ctx.dt else b
            events.append(Event(a, end, "wrong_way", tracks=(tr.tid,)))
    return events


# --------------------------------------------------------------------------------------------
# turns
# --------------------------------------------------------------------------------------------
def _turn_bounds(t: np.ndarray, uh: np.ndarray, i: int, j: int, settle_deg: float = 12.0) -> tuple[float, float]:
    """Refine a turn found between samples i and j: start when heading leaves its initial value,
    end when it reaches its final value."""
    h0, h1 = uh[i], uh[j]
    start = i
    for k in range(i, j + 1):
        if abs(uh[k] - h0) > np.deg2rad(settle_deg):
            start = max(i, k - 1)
            break
    end = j
    for k in range(j, i - 1, -1):
        if abs(uh[k] - h1) > np.deg2rad(settle_deg):
            end = min(j, k + 1)
            break
    return float(t[start]), float(t[max(end, start + 1)])


def _find_turn(t: np.ndarray, uh: np.ndarray, min_turn: float, max_s: float, min_s: float):
    """Earliest window [i, j] whose heading change reaches ``min_turn`` radians, taking between
    ``min_s`` and ``max_s`` seconds."""
    jmax = np.searchsorted(t, t + max_s, side="right")
    for i in range(len(uh)):
        seg = slice(i + 1, jmax[i])
        ok = (np.abs(uh[seg] - uh[i]) >= min_turn) & (t[seg] - t[i] >= min_s)
        if ok.any():
            return i, i + 1 + int(np.argmax(ok))
    return None


def illegal_u_turn(ctx: Context) -> list[Event]:
    p = ctx.params("illegal_u_turn")
    events = []
    for tr in ctx.vehicles:
        head = tr.heading(ctx.heading_min)
        v = ~np.isnan(head) & tr.reliable
        if v.sum() < 5:
            continue
        t, uh = tr.t[v], unwrap_heading(head[v])
        steps = np.abs(np.diff(uh))
        if len(steps) and steps.max() > np.deg2rad(70):
            continue  # heading jumps: an identity switch between two vehicles, not a turn
        found = _find_turn(t, uh, np.deg2rad(p["min_turn_deg"]), p["max_turn_s"], min_s=2.0)
        if found is None:
            continue
        a, b = _turn_bounds(t, uh, *found)
        # it must drive into the turn: a track that stood still and suddenly "turns" is almost
        # always an identity switch with a passing vehicle (or a car pulling out of a space)
        if ((t >= a - 3.0) & (t < a)).sum() * ctx.dt < p["min_approach_s"]:
            continue
        mid = tr.gp[tr.index_at(0.5 * (a + b))]
        if not ctx.scene.uturn_prohibited(mid[None])[0]:
            continue
        events.append(Event(a, b, "illegal_u_turn", tracks=(tr.tid,)))
    return events


def _mode(values: np.ndarray) -> int:
    values = values[values >= 0]
    if len(values) == 0:
        return -1
    vals, counts = np.unique(values, return_counts=True)
    return int(vals[counts.argmax()])


def illegal_turn(ctx: Context) -> list[Event]:
    p = ctx.params("illegal_turn")
    scene = ctx.scene
    lanes_with_rules = any("allowed_turns" in ln for ln in scene.lanes)
    if not scene.prohibited_movements and not lanes_with_rules:
        return []
    events = []
    for tr in ctx.vehicles:
        head = tr.heading(ctx.heading_min)
        v = ~np.isnan(head) & tr.reliable
        if v.sum() < 5:
            continue
        t, uh = tr.t[v], unwrap_heading(head[v])
        k = max(1, int(round(1.0 / ctx.dt)))
        total = np.median(uh[-k:]) - np.median(uh[:k])
        deg = np.rad2deg(total)
        if abs(deg) < p["min_turn_deg"] or abs(deg) >= 150:
            continue
        # In image coordinates (y down) a clockwise heading change is a right turn.
        movement = "right" if deg > 0 else "left"
        found = _find_turn(t, uh, np.deg2rad(p["min_turn_deg"]), 30.0, min_s=0.5)
        if found is None:
            continue
        a, b = _turn_bounds(t, uh, *found)
        illegal = False
        if scene.prohibited_movements:
            n = max(1, len(tr.t) // 5)
            z_in, z_out = _mode(scene.zone_at(tr.gp[:n])), _mode(scene.zone_at(tr.gp[-n:]))
            if z_in >= 0 and z_out >= 0:
                illegal |= (scene.zone_ids[z_in], scene.zone_ids[z_out]) in scene.prohibited_movements
        if lanes_with_rules:
            lane = int(scene.lane_at(tr.gp[tr.index_at(a)][None])[0])
            if lane >= 0 and "allowed_turns" in scene.lanes[lane]:
                illegal |= movement not in scene.lanes[lane]["allowed_turns"]
        if illegal:
            events.append(Event(a, b, "illegal_turn", tracks=(tr.tid,), info={"movement": movement}))
    return events


# --------------------------------------------------------------------------------------------
# solid_line_crossing
# --------------------------------------------------------------------------------------------
def solid_line_crossing(ctx: Context) -> list[Event]:
    p = ctx.params("solid_line_crossing")
    if not ctx.scene.solid_lines:
        return []
    events = []
    inset = p["wheel_inset"]
    for line in ctx.scene.solid_lines:
        for tr in ctx.vehicles:
            w = tr.box[:, 2] - tr.box[:, 0]
            left = np.stack([tr.box[:, 0] + inset * w, tr.box[:, 3]], axis=1)
            right = np.stack([tr.box[:, 2] - inset * w, tr.box[:, 3]], axis=1)
            s_l, along_l = polyline_side(line, left)
            s_r, along_r = polyline_side(line, right)
            along = along_l & along_r & tr.reliable
            if along.sum() < 3:
                continue
            side_l, side_r = np.sign(s_l), np.sign(s_r)
            both = (side_l == side_r) & along & (np.minimum(np.abs(s_l), np.abs(s_r)) > 2.0)
            idx = np.flatnonzero(both)
            if len(idx) < 2:
                continue
            # Consecutive stable samples on opposite sides => one full crossing in between,
            # provided the vehicle then stays on the new side for at least min_s.
            for n, (i0, i1) in enumerate(zip(idx[:-1], idx[1:])):
                if side_l[i0] == side_l[i1]:
                    continue
                later = idx[n + 1:]
                change = np.flatnonzero(side_l[later] != side_l[i1])
                stay_until = tr.t[later[change[0] - 1]] if len(change) else tr.t1
                if stay_until - tr.t[i1] < p["min_s"] and len(change):
                    continue
                seg = slice(i0, i1 + 1)
                flipped = (side_l[seg] != side_l[i0]) | (side_r[seg] != side_r[i0])
                start = float(tr.t[i0 + int(np.argmax(flipped))])
                end = float(max(tr.t[i1], start + ctx.dt))
                events.append(Event(start, end, "solid_line_crossing", tracks=(tr.tid,)))
    return events
