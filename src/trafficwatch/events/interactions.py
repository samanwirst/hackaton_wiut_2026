"""Pairwise rules: accident (contact) and near miss (conflict + evasive action, no contact).

Distances and speeds are normalised by the pair's mean object size, which makes the thresholds
roughly independent of how far the pair is from the camera.
"""
from __future__ import annotations

import numpy as np

from ..detector import paired_overlap
from ..geometry import angle_diff, lower_box, same_pace
from ..tracks import Track, unwrap_heading
from .common import Context, Event


def _pair(ctx: Context, A: Track, B: Track) -> dict | None:
    ia, ib = ctx.common(A, B)
    if len(ia) < 3:
        return None
    t = A.t[ia]
    s = 0.5 * (A.scale[ia] + B.scale[ib])
    r = (B.gp[ib] - A.gp[ia]) / s[:, None]
    v = (B.vel[ib] - A.vel[ia]) / s[:, None]
    dn = np.hypot(r[:, 0], r[:, 1])
    vv = np.maximum((v ** 2).sum(axis=1), 1e-9)
    tcpa = -(r * v).sum(axis=1) / vv
    dcpa = np.hypot(*(r + v * tcpa[:, None]).T)
    overlap = paired_overlap(lower_box(A.box[ia]), lower_box(B.box[ib]))
    ok = A.reliable[ia] & B.reliable[ib]          # neither is cut off by the frame border
    ha = np.arctan2(A.vel[ia, 1], A.vel[ia, 0])
    hb = np.arctan2(B.vel[ib, 1], B.vel[ib, 0])
    moving = (A.nspeed[ia] >= 0.3) & (B.nspeed[ib] >= 0.3)
    opposite = moving & (angle_diff(ha, hb) > np.deg2rad(135))   # driving towards each other
    pace = same_pace(A.vel[ia], A.scale[ia], B.vel[ib], B.scale[ib])
    return {"t": t, "ia": ia, "ib": ib, "dn": dn, "rel": np.sqrt(vv), "tcpa": tcpa,
            "dcpa": dcpa, "overlap": overlap, "ok": ok, "opposite": opposite, "same_pace": pace}


def _settle_time(tr: Track, t_from: float, settle_nspeed: float, hold_s: float = 0.5) -> tuple[float, bool]:
    """First time after ``t_from`` the object stays slow for ``hold_s``; else when it leaves."""
    after = np.flatnonzero((tr.t >= t_from) & (tr.nspeed < settle_nspeed) & tr.reliable)
    for k in after:
        # A truncated track tail is not a full stop window. Include the first
        # sample at/after the window end, rather than silently accepting less time.
        end = int(np.searchsorted(tr.t, tr.t[k] + hold_s))
        if end >= len(tr.t):
            continue
        hold = slice(k, end + 1)
        if (tr.nspeed[hold] < settle_nspeed).all() and tr.reliable[hold].all():
            return float(tr.t[k]), True
    return tr.t1, False


def _impact(tr: Track, tc: float, p: dict) -> tuple[float, float]:
    """(speed just before tc, fraction of it lost within ``drop_within_s`` after tc). A crash
    stops a vehicle that was still moving at contact; a car braking into a queue has already
    slowed down before its box reaches the one ahead."""
    pre = tr.slice(tc - 1.0, tc - 0.2) & tr.reliable
    post = tr.slice(tc, tc + p["drop_within_s"]) & tr.reliable
    if pre.sum() < 2 or not post.any():
        return 0.0, 0.0
    v_pre = float(np.median(tr.nspeed[pre]))
    if v_pre <= 0:
        return 0.0, 0.0
    return v_pre, float((v_pre - tr.nspeed[post].min()) / v_pre)


def _rest_together(pr: dict, t_rest: float, p: dict) -> bool:
    """Require joint evidence of remaining close; a vanished track is not proof of contact."""
    m = (pr["t"] >= t_rest) & (pr["t"] <= t_rest + p["rest_together_s"]) & pr["ok"]
    return bool(m.any()) and bool((pr["dn"][m] < p["rest_scale"]).all())


def accident(ctx: Context) -> list[Event]:
    p = ctx.params("accident")
    events = []
    for (ka, kb) in ctx.close_pairs(max_dist_scale=max(1.5, p["contact_scale"] + 0.5)):
        A, B = ctx.tracks[ka], ctx.tracks[kb]
        pr = _pair(ctx, A, B)
        if pr is None:
            continue
        contact = ((pr["dn"] < p["contact_scale"]) | (pr["overlap"] > 0.1)) & pr["ok"]
        onsets = np.flatnonzero(contact & ~np.concatenate([[False], contact[:-1]]))
        for c in onsets:
            tc = float(pr["t"][c])
            pre = (pr["t"] >= tc - 1.0) & (pr["t"] <= tc) & pr["ok"]
            if pre.sum() < 3:
                continue  # already touching when first seen together: no observable approach
            closing = float(np.max(-np.gradient(pr["dn"][pre], pr["t"][pre])))
            if closing < p["min_closing_nspeed"]:
                continue
            impacts = [_impact(tr, tc, p) for tr in (A, B)]
            if any(tr.category == "person" for tr in (A, B)) and not any(
                tr.is_vehicle and speed > p["settle_nspeed"]
                for tr, (speed, _) in zip((A, B), impacts)
            ):
                # Walking up to a parked vehicle and stopping/being occluded is
                # common at the kerb. Pedestrian-only motion is not crash evidence.
                continue
            # the striker: moving fast enough at contact and stopped short by it
            strikers = []
            for tr, (v_pre, drop) in zip((A, B), impacts):
                if v_pre >= p["min_impact_nspeed"] and drop >= p["min_speed_drop"]:
                    t_rest, ok = _settle_time(tr, tc, p["settle_nspeed"])
                    if ok and t_rest - tc <= p["max_settle_s"] and _rest_together(pr, t_rest, p):
                        strikers.append((drop, t_rest))
            if not strikers:
                continue
            drop = max(d for d, _ in strikers)
            score = (0.4 * min(closing / p["min_closing_nspeed"], 1.0) + 0.4 * min(drop / p["min_speed_drop"], 1.0)
                     + 0.2)
            if score < p["min_score"]:
                continue
            others = [_settle_time(tr, tc, p["settle_nspeed"]) for tr in (A, B)]
            end = max([t for _, t in strikers] + [t for t, ok in others if ok])
            events.append(Event(tc, max(end, tc + 1.0), "accident", score=score, tracks=(A.tid, B.tid),
                                info={"closing": round(closing, 2), "drop": round(drop, 2)}))
            break
    return events


def _evasive_onset(tr: Track, t0: float, p: dict) -> float | None:
    """Onset of sharp braking or swerving near time t0, if any. Both are judged as averages over
    at least ``evasive_span_s`` so that detection jitter on one frame does not look like braking."""
    w = tr.slice(t0 - 0.5, t0 + 2.0) & tr.reliable
    if w.sum() < 3:
        return None
    t = tr.t[w]
    v = tr.nspeed[w]
    head = unwrap_heading(np.arctan2(tr.vel[w, 1], tr.vel[w, 0]))
    span = p["evasive_span_s"]
    for i in range(len(t)):
        j = int(np.searchsorted(t, t[i] + span))
        if j >= len(t):
            break
        dt = t[j] - t[i]
        braking = v[i] >= p["min_evasive_nspeed"] and (v[i] - v[j]) / dt >= p["min_decel"]
        moving = (v[i: j + 1] >= p["min_evasive_nspeed"]).all()
        swerving = moving and abs(head[j] - head[i]) / dt >= np.deg2rad(p["min_yaw_rate_deg"])
        if braking or swerving:
            return float(t[i])
    return None


def near_miss(ctx: Context) -> list[Event]:
    p = ctx.params("near_miss")
    events = []
    for (ka, kb) in ctx.close_pairs(max_dist_scale=4.0):
        A, B = ctx.tracks[ka], ctx.tracks[kb]
        pr = _pair(ctx, A, B)
        if pr is None:
            continue
        # opposite directions pass close to each other in neighbouring lanes all the time (and
        # perspective squeezes the gap): only a nearly head-on course is a conflict there
        miss = np.where(pr["opposite"], p["head_on_miss_scale"], p["miss_scale"])
        conflict = ((pr["tcpa"] > 0) & (pr["tcpa"] < p["horizon_s"]) & (pr["dcpa"] < miss)
                    & (pr["rel"] > p["min_rel_nspeed"]) & pr["ok"] & ~pr["same_pace"])
        if not conflict.any():
            continue
        if (pr["dn"][pr["ok"]] < p["touch_scale"]).any():
            continue  # they (visually) touch: that is an accident candidate or an occlusion
        t0 = float(pr["t"][int(np.argmax(conflict))])
        # a vehicle standing still cannot nearly hit anyone (a pedestrian walking past a parked car)
        if not any(tr.is_vehicle and tr.nspeed[tr.index_at(t0)] >= p["min_vehicle_nspeed"] for tr in (A, B)):
            continue
        onsets = [o for o in (_evasive_onset(A, t0, p), _evasive_onset(B, t0, p)) if o is not None]
        if not onsets:
            continue
        start = min(onsets)
        after = pr["t"] > t0
        clear = after & (pr["dn"] > p["clear_scale"]) & (pr["tcpa"] <= 0)
        end = float(pr["t"][int(np.argmax(clear))]) if clear.any() else float(min(pr["t"][-1], t0 + 3.0))
        score = float(np.clip(1.0 - pr["dcpa"][conflict].min() / p["miss_scale"], 0, 1))
        if 0.5 + 0.5 * score < p["min_score"]:
            continue
        events.append(Event(start, max(end, start + 0.5), "near_miss", score=score, tracks=(A.tid, B.tid)))
    return events
