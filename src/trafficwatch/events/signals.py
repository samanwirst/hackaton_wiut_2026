"""Signal rules: red-light running and stop-line violations. Need stop lines linked to a light."""
from __future__ import annotations

import numpy as np

from ..geometry import front_point, projection_param, signed_distance_to_line
from ..signal import GREEN, RED
from ..tracks import Track, filled_heading, hysteresis, intervals
from .common import Context, Event


def _past_line(sl, pts: np.ndarray) -> np.ndarray:
    """Signed distance beyond the stop line, positive on the junction side."""
    s = signed_distance_to_line(sl.a, sl.b, pts)
    ahead = signed_distance_to_line(sl.a, sl.b, (sl.a + sl.b) / 2 + sl.forward * 10.0)[0]
    return s * np.sign(ahead)


def _lines_with_signal(ctx: Context):
    for sl in ctx.scene.stop_lines:
        if sl.light and sl.light in ctx.signals:
            yield sl, ctx.signals[sl.light]


def _front(ctx: Context, tr: Track, sl) -> tuple[np.ndarray, np.ndarray]:
    """Front of the vehicle and its heading. A vehicle waiting at the line keeps the heading it
    arrived with (before it ever moved: the direction of travel over the line)."""
    head = filled_heading(tr, ctx.heading_min, default=float(np.arctan2(sl.forward[1], sl.forward[0])))
    return front_point(tr.box, head), head


def _junction_entry_exit(ctx: Context, tr: Track, t_from: float) -> tuple[float | None, float]:
    """When the vehicle enters the junction box after ``t_from`` (None if it never does) and when
    it leaves it again (end of the track if it does not, or if no junction is drawn)."""
    if ctx.scene.intersection_mask is None:
        return None, tr.t1
    inside = ctx.scene.in_intersection(tr.gp) & tr.reliable
    entered = np.flatnonzero((tr.t > t_from) & inside)
    if not len(entered):
        return None, tr.t1
    t_in = float(tr.t[entered[0]])
    left = np.flatnonzero((tr.t > t_in) & ~inside)
    return t_in, float(tr.t[left[0]]) if len(left) else tr.t1


def red_light(ctx: Context) -> list[Event]:
    p = ctx.params("red_light")
    stop_p = ctx.params("stop_line")
    events = []
    for sl, sig in _lines_with_signal(ctx):
        fwd_angle = np.arctan2(sl.forward[1], sl.forward[0])
        for tr in ctx.vehicles:
            fp, head = _front(ctx, tr, sl)
            past = _past_line(sl, fp)
            u = projection_param(sl.a, sl.b, fp)
            cos = np.cos(head - fwd_angle)
            ok = tr.reliable
            cross = np.flatnonzero((past[:-1] < 0) & (past[1:] >= 0) & ok[:-1] & ok[1:])
            for i in cross:
                if not (-0.1 <= u[i + 1] <= 1.1) or cos[i + 1] < 0.3:
                    continue
                # sub-step crossing time by linear interpolation
                frac = -past[i] / max(past[i + 1] - past[i], 1e-6)
                t_cross = float(tr.t[i] + frac * (tr.t[i + 1] - tr.t[i]))
                if sig.state_at(t_cross) != RED or sig.since(t_cross) < p["red_grace_s"]:
                    continue
                t_in, t_out = _junction_entry_exit(ctx, tr, t_cross)
                # stopped over the line and only went on at green (or never): a stop-line case
                slow = np.flatnonzero((tr.t > t_cross) & (tr.nspeed < stop_p["stop_nspeed"]) & ok)
                t_stop = float(tr.t[slow[0]]) if len(slow) else None
                if t_stop is not None and (t_in is None or t_stop < t_in) and \
                        (t_in is None or sig.state_at(t_in) == GREEN):
                    continue
                end = min(t_out, t_cross + p["max_event_s"])
                events.append(Event(t_cross, max(end, t_cross + ctx.dt), "red_light", tracks=(tr.tid,)))
    return events


def stop_line(ctx: Context) -> list[Event]:
    p = ctx.params("stop_line")
    events = []
    for sl, sig in _lines_with_signal(ctx):
        for tr in ctx.vehicles:
            fp, _ = _front(ctx, tr, sl)
            past = _past_line(sl, fp)
            u = projection_param(sl.a, sl.b, tr.gp)
            beyond = (past > 0) & (past < p["max_overshoot_scale"] * tr.scale) & (u >= -0.1) & (u <= 1.1)
            beyond &= ~ctx.scene.in_intersection(tr.gp) & tr.reliable
            still = hysteresis(tr.nspeed, p["stop_nspeed"], 2 * p["stop_nspeed"], below=True)
            for a, _ in intervals(beyond & still, tr.t, min_len=p["min_stop_s"]):
                if sig.state_at(a) != RED:
                    continue
                green = sig.next_change_to(a, GREEN)
                end = green if green is not None else ctx.duration
                events.append(Event(a, max(end, a + ctx.dt), "stop_line", tracks=(tr.tid,)))
    return events
