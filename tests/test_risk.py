"""Part B: the causal risk rises before a collision and stays low in normal traffic."""
from __future__ import annotations

import numpy as np
import synthetic  # noqa: F401  (adds src/ to the path)

from trafficwatch.detector import Detections
from trafficwatch.risk import CausalRisk

FPS, STRIDE = 25.0, 2


def run(paths, duration):
    """paths: list of functions t -> (x_center, y_bottom). Returns times and scores."""
    est = CausalRisk()
    est.reset({"fps": FPS, "width": 1280, "height": 720, "n_frames": int(duration * FPS)})
    times, scores = [], []
    for i in range(0, int(duration * FPS), STRIDE):
        t = i / FPS
        boxes = []
        for f in paths:
            pos = f(t)
            if pos is not None:
                x, y = pos
                boxes.append([x - 40, y - 50, x + 40, y])
        det = Detections(np.array(boxes).reshape(-1, 4), np.full(len(boxes), 0.9), np.full(len(boxes), 2.0))
        times.append(t)
        scores.append(est.update(det, t))
    return np.array(times), np.array(scores)


def test_risk_rises_before_head_on_collision():
    # two cars on the same line at 200 px/s towards each other; contact at t = 2.5 s
    a = lambda t: (100 + 200 * t, 500) if t <= 2.5 else (600, 500)          # noqa: E731
    b = lambda t: (1180 - 200 * t, 500) if t <= 2.5 else (680, 500)         # noqa: E731
    t, s = run([a, b], 5.0)
    assert s[t < 0.8].max() < 0.2
    assert s[(t > 1.3) & (t < 2.5)].max() >= 0.5


def test_risk_low_in_parallel_traffic():
    a = lambda t: (100 + 200 * t, 400)     # noqa: E731
    b = lambda t: (100 + 200 * t, 560)     # noqa: E731
    c = lambda t: (1180 - 200 * t, 480)    # noqa: E731  (opposite lane)
    t, s = run([a, b, c], 5.0)
    assert s.max() < 0.3
