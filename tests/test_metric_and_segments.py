"""Tests for segment post-processing and the official metric (evaluate.py from the starter kit)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import synthetic  # noqa: F401  (adds src/ to the path)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate import evaluate, evaluate_part_a, tiou  # noqa: E402

from trafficwatch.config import load_config  # noqa: E402
from trafficwatch.events.common import Event  # noqa: E402
from trafficwatch.segments import postprocess  # noqa: E402


def test_postprocess_merges_clips_and_drops():
    cfg = load_config()
    raw = [Event(1.0, 3.0, "jaywalking"), Event(3.5, 6.0, "jaywalking"),   # gap 0.5 < 1.5 -> merged
           Event(20.0, 20.3, "jaywalking"),                                 # shorter than 1 s -> dropped
           Event(55.0, 70.0, "wrong_way"),                                   # clipped to duration
           Event(5.0, 9.0, "road_obstacle")]                                 # class not enabled
    out = postprocess(raw, 60.0, cfg, enabled={"jaywalking", "wrong_way"})
    assert out == [[1.0, 6.0, "jaywalking"], [55.0, 60.0, "wrong_way"]]


def test_postprocess_output_contract():
    cfg = load_config()
    rng = np.random.default_rng(0)
    raw = []
    for _ in range(200):
        s = float(rng.uniform(-5, 65))
        raw.append(Event(s, s + float(rng.uniform(0, 8)), str(rng.choice(["accident", "jaywalking", "congestion"]))))
    out = postprocess(raw, 60.0, cfg)
    for s, e, _ in out:
        assert 0.0 <= s < e <= 60.0
    for label in {x[2] for x in out}:
        segs = sorted((s, e) for s, e, lab in out if lab == label)
        assert all(a[1] < b[0] for a, b in zip(segs, segs[1:]))


def test_tiou():
    assert tiou((0, 10), (0, 10)) == 1.0
    assert abs(tiou((0, 10), (5, 15)) - 5 / 15) < 1e-9
    assert tiou((0, 1), (2, 3)) == 0.0


def test_perfect_and_extra_class():
    gt = {"v1.mp4": {"duration": 60.0, "fps": 25.0, "events": [[10, 15, "accident"], [30, 40, "jaywalking"]]}}
    perfect = {"v1.mp4": {"events": [[10, 15, "accident"], [30, 40, "jaywalking"]]}}
    assert evaluate_part_a(gt, perfect)["score_a"] == 1.0
    # predicting a class that never occurs adds a zero to the macro average
    extra = {"v1.mp4": {"events": [[10, 15, "accident"], [30, 40, "jaywalking"], [50, 55, "fire_smoke"]]}}
    assert abs(evaluate_part_a(gt, extra)["score_a"] - 2 / 3) < 1e-9


def test_score_b_alarm_before_accident():
    gt = {"v.mp4": {"duration": 60.0, "fps": 25.0, "events": [[30.0, 34.0, "accident"]]}}
    t = np.arange(0, 60, 0.04)
    score = np.where((t >= 27.0) & (t < 30.0), 0.9, 0.01)
    res = evaluate(gt, {"videos": {"v.mp4": {"events": [], "risk": np.column_stack([t, score]).tolist()}}})
    b = res["part_b"]
    assert b["f1_alarm"] == 1.0 and abs(b["mtta_sec"] - 3.0) < 0.05 and b["ap"] > 0.5
    constant = {"videos": {"v.mp4": {"events": [], "risk": np.column_stack([t, np.ones_like(t)]).tolist()}}}
    assert evaluate(gt, constant)["part_b"]["score_b"] < 0.05
