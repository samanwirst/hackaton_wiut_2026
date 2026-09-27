"""Traffic-light state from a fixed region of interest.

For each configured light we measure, on every processed frame, either the share of bright,
saturated red / amber / green pixels in the whole ROI (colour mode), or - when the lamp positions
are given - which lamp contains its expected hue. The lamp reader accepts dim daylight signals,
but rejects white headlights and differently coloured objects behind an unlit lamp. The sequence is cleaned
with a running mode filter so that single-frame flicker (compression, occlusion, a flashing green)
is ignored.

Signals that cannot be seen are derived from those that can (``derive_signals``): the vehicle
signal of an approach whose lights face away from the camera follows the pedestrian signal of the
parallel crossing, and the crossing phase is the inverse of the main phase.
"""
from __future__ import annotations

from collections import Counter

import cv2
import numpy as np

RED, AMBER, GREEN, UNKNOWN = "red", "amber", "green", "unknown"


def light_scores(frame: np.ndarray, roi) -> dict[str, float]:
    x1, y1, x2, y2 = [int(v) for v in roi]
    h, w = frame.shape[:2]
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return {RED: 0.0, AMBER: 0.0, GREEN: 0.0}
    hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0].astype(int), hsv[..., 1], hsv[..., 2]
    lit = (val >= 170) & (sat >= 90)
    n = float(lit.size)
    red = lit & ((hue <= 8) | (hue >= 165))
    amber = lit & (hue > 8) & (hue <= 30)
    green = lit & (hue >= 45) & (hue <= 100)
    return {RED: red.sum() / n, AMBER: amber.sum() / n, GREEN: green.sum() / n}


def classify(scores: dict[str, float], min_frac: float = 0.01) -> str:
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] >= min_frac else UNKNOWN


def lamp_scores(frame: np.ndarray, lamps: dict) -> dict[str, float]:
    """Share of saturated, colour-consistent pixels in each calibrated lamp box.

    Absolute brightness alone misses dim daylight lamps and mistakes background reflections
    for active lamps. Hue and position must agree; dark or achromatic regions stay unknown.
    """
    h, w = frame.shape[:2]
    out = {}
    for colour, roi in lamps.items():
        x1, y1, x2, y2 = [int(round(v)) for v in roi]
        x1, x2, y1, y2 = max(0, x1), min(w, x2), max(0, y1), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            out[colour] = 0.0
            continue
        hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        if colour == RED:
            expected = (hue <= 15) | (hue >= 165)
        elif colour == AMBER:
            expected = (hue >= 8) & (hue <= 38)
        elif colour == GREEN:
            expected = (hue >= 40) & (hue <= 100)
        else:
            out[colour] = 0.0
            continue
        out[colour] = float(((val >= 70) & (sat >= 80) & expected).mean())
    return out


def read_light(frame: np.ndarray, spec: dict) -> str:
    """State of one configured light: lamp mode when ``lamps`` are given, else colour mode on ``roi``."""
    if spec.get("lamps"):
        return classify(lamp_scores(frame, spec["lamps"]), min_frac=0.04)
    return classify(light_scores(frame, spec["roi"]))


class SignalTimeline:
    """States sampled at ``times``; ``state_at`` answers queries for any time."""

    def __init__(self, times: np.ndarray, states: list[str], smooth_s: float = 1.0):
        self.times = np.asarray(times, dtype=np.float64)
        self.states = self._mode_filter(states, smooth_s)

    def _mode_filter(self, states: list[str], smooth_s: float) -> list[str]:
        if len(states) < 3 or len(self.times) < 2 or smooth_s <= 0:
            return list(states)
        dt = float(np.median(np.diff(self.times)))
        half = max(1, int(round(smooth_s / dt / 2)))
        out = []
        for i in range(len(states)):
            window = [s for s in states[max(0, i - half): i + half + 1] if s != UNKNOWN]
            out.append(Counter(window).most_common(1)[0][0] if window else UNKNOWN)
        return out

    def state_at(self, t: float) -> str:
        if len(self.times) == 0:
            return UNKNOWN
        i = int(np.clip(np.searchsorted(self.times, t, side="right") - 1, 0, len(self.times) - 1))
        return self.states[i]

    def since(self, t: float) -> float:
        """How long the state at time t has been active (seconds)."""
        i = int(np.clip(np.searchsorted(self.times, t, side="right") - 1, 0, len(self.times) - 1))
        s = self.states[i]
        j = i
        while j > 0 and self.states[j - 1] == s:
            j -= 1
        return float(t - self.times[j])

    def next_change_to(self, t: float, state: str) -> float | None:
        i = int(np.searchsorted(self.times, t, side="right"))
        for j in range(i, len(self.times)):
            if self.states[j] == state:
                return float(self.times[j])
        return None

    def to_segments(self) -> list[tuple[float, float, str]]:
        segs: list[tuple[float, float, str]] = []
        for t, s in zip(self.times, self.states):
            if segs and segs[-1][2] == s:
                segs[-1] = (segs[-1][0], float(t), s)
            else:
                segs.append((float(t), float(t), s))
        return segs


def _runs(states: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """For every sample: index of the first and of the last sample of its run of equal states."""
    n = len(states)
    first, last = np.zeros(n, dtype=int), np.zeros(n, dtype=int)
    for i in range(1, n):
        first[i] = first[i - 1] if states[i] == states[i - 1] else i
    last[n - 1:] = n - 1
    for i in range(n - 2, -1, -1):
        last[i] = last[i + 1] if states[i] == states[i + 1] else i
    return first, last


def _via(src: SignalTimeline, spec: dict) -> list[str]:
    """States of a signal read through one source light (see ``derive_signals``)."""
    times, states = src.times, list(src.states)
    if spec.get("invert"):
        states = [{GREEN: RED, AMBER: RED, RED: GREEN}.get(s, UNKNOWN) for s in states]
    delay = float(spec.get("red_delay_s", 0.0))
    if delay <= 0 or not len(times):
        return states
    amber = float(spec.get("amber_s", 0.0))
    first, _ = _runs(states)
    out = []
    for i, s in enumerate(states):
        if s == RED:
            if first[i] == 0:
                s = UNKNOWN            # red since the video started: onset unknown, so is the delay
            else:
                since = times[i] - times[first[i]]
                if since < delay:
                    s = AMBER if since >= delay - amber else GREEN
        out.append(s)
    return out


def _inverse(src: SignalTimeline, spec: dict) -> list[str]:
    """The conflicting phase: red while ``src`` is green or amber; green while ``src`` is red, but
    only ``green_after_s`` after its red began and up to ``red_before_s`` before its next green
    (the clearance times at both ends are unknown and left out)."""
    times, states = src.times, src.states
    first, last = _runs(states)
    after, before = float(spec.get("green_after_s", 0.0)), float(spec.get("red_before_s", 0.0))
    out = []
    for i, s in enumerate(states):
        if s in (GREEN, AMBER):
            out.append(RED)
        elif s == RED:
            since = np.inf if first[i] == 0 else times[i] - times[first[i]]
            j = last[i] + 1            # first sample after this red run
            until = times[j] - times[i] if j < len(states) and states[j] in (GREEN, AMBER) else np.inf
            out.append(GREEN if since >= after and until >= before else UNKNOWN)
        else:
            out.append(UNKNOWN)
    return out


def derive_signals(specs: list[dict], signals: dict[str, SignalTimeline]) -> dict[str, SignalTimeline]:
    """Add the derived signals of the scene (``signals`` in scene.json) to the measured ones.

    Each spec is either
      ``{"id", "sources": [{"light", "invert"?, "red_delay_s"?, "amber_s"?}, ...]}`` - read through
      the first source whose state is known at that moment; ``red_delay_s`` keeps the derived signal
      green (the last ``amber_s`` of it amber) for that long after the source turned red, e.g. a
      vehicle signal that follows the pedestrian signal of the parallel crossing, or
      ``{"id", "inverse_of", "green_after_s"?, "red_before_s"?}`` - the conflicting phase.
    Specs may use signals derived by earlier specs."""
    out = dict(signals)
    for spec in specs:
        if "inverse_of" in spec:
            src = out.get(spec["inverse_of"])
            if src is None:
                continue
            out[spec["id"]] = SignalTimeline(src.times, _inverse(src, spec), smooth_s=0)
            continue
        sources = [(out[s["light"]], s) for s in spec.get("sources", []) if s.get("light") in out]
        if not sources:
            continue
        times = sources[0][0].times
        read = [_via(tl, s) for tl, s in sources]
        states = []
        for i in range(len(times)):
            known = [r[i] for r in read if r[i] != UNKNOWN]
            states.append(known[0] if known else UNKNOWN)
        out[spec["id"]] = SignalTimeline(times, states, smooth_s=0)
    return out
