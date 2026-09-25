"""Segment post-processing: turn raw rule firings into clean, valid, non-overlapping segments.

Boundaries matter at IoU 0.7, so fragments of one event are merged, blips are dropped, and the
result always satisfies the output contract: 0 <= start < end <= duration, one class per
segment, no overlap within a class (simultaneous events of one class become one segment).
"""
from __future__ import annotations

from .config import postprocess_params
from .events.common import Event


def merge_intervals(items: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for s, e in sorted(items):
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def postprocess(events: list[Event], duration: float, cfg: dict, enabled: set[str] | None = None) -> list[list]:
    by_label: dict[str, list[tuple[float, float]]] = {}
    for ev in events:
        if enabled is not None and ev.label not in enabled:
            continue
        by_label.setdefault(ev.label, []).append((float(ev.start), float(ev.end)))
    result: list[list] = []
    for label, items in sorted(by_label.items()):
        p = postprocess_params(cfg, label)
        padded = [(s - p.get("pad_start_s", 0.0), e + p.get("pad_end_s", 0.0)) for s, e in items]
        for s, e in merge_intervals(padded, p.get("merge_gap_s", 0.0)):
            s, e = max(0.0, s), min(duration, e)
            if e - s < p.get("min_len_s", 0.0):
                continue
            s, e = round(s, 2), round(e, 2)
            if e > duration:
                e = round(duration - 0.005, 2)
            if e > s:
                result.append([s, e, label])
    result.sort(key=lambda x: (x[0], x[2]))
    return result
