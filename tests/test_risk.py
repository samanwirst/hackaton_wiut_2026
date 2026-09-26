"""Part B: the causal risk rises before a collision and stays low in normal traffic."""
from __future__ import annotations

import numpy as np
import synthetic  # noqa: F401  (adds src/ to the path)
from types import SimpleNamespace

from trafficwatch.config import load_config
from trafficwatch.detector import Detections
from trafficwatch.risk import CausalRisk, risk_curve_from_perception
from trafficwatch.video import VideoInfo

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


def _approaching_detections(t):
    boxes = [[60 + 200 * t, 450, 140 + 200 * t, 500],
             [1140 - 200 * t, 450, 1220 - 200 * t, 500]]
    return Detections(np.asarray(boxes), np.full(2, 0.9), np.full(2, 2))


def test_step_uses_only_the_supplied_prefix_and_resets(monkeypatch):
    """The harness streams frames; a future frame or file must never affect an earlier score."""
    import cv2
    import trafficwatch.risk as risk

    def no_video_file(*args, **kwargs):
        raise AssertionError("Part B opened a video file")

    def detector(frames):
        return [_approaching_detections(float(frame[0, 0, 0]) / 25) for frame in frames]

    monkeypatch.setenv("TRAFFICWATCH_PROFILE", "cpu")
    monkeypatch.setattr(risk, "get_detector", lambda *args: detector)
    monkeypatch.setattr(cv2, "VideoCapture", no_video_file)
    cfg = load_config(overrides={"scene": {"cameras": []}, "risk": {"target_fps_cpu": 25}})
    est = CausalRisk(cfg)
    meta = {"video_id": "not-a-file.mp4", "fps": 25, "width": 1280, "height": 720}

    def stream(length):
        est.reset({**meta, "n_frames": length})
        return [est.step(np.full((2, 2, 3), i, dtype=np.uint8), i / 25) for i in range(length)]

    prefix = stream(50)
    longer = stream(65)
    assert longer[:50] == prefix
    assert stream(50) == prefix
    assert max(prefix) >= 0.5  # Compare a meaningful curve, not a constant fallback.


def test_reused_detections_need_no_model_and_ignore_future_tracks(monkeypatch):
    """CPU Space exports must work even on a CUDA host with only nano weights packaged."""
    import trafficwatch.risk as risk

    def no_model(*args, **kwargs):
        raise AssertionError("Export unnecessarily loaded a detector")

    monkeypatch.setenv("TRAFFICWATCH_PROFILE", "gpu")
    monkeypatch.setattr(risk, "get_detector", no_model)
    times = np.arange(50) / 25
    cfg = load_config(overrides={"scene": {"cameras": []}})
    perception = SimpleNamespace(
        info=VideoInfo("unavailable.mp4", 25, 50, 1280, 720), stride=1,
        times=times, detections=[_approaching_detections(t) for t in times],
        tracks=None,  # Smoothed Part A tracks are deliberately unavailable.
    )
    rt, scores = risk_curve_from_perception(perception, cfg)
    np.testing.assert_array_equal(rt, times)
    perception.times, perception.detections = times[:35], perception.detections[:35]
    _, prefix = risk_curve_from_perception(perception, cfg)
    np.testing.assert_array_equal(prefix, scores[:35])
    assert scores.max() >= 0.5
