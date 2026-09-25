"""Submission interface. The organisers' harness (run_submission.py) imports this module.

Part A: detect_events(video_path) -> [[start_sec, end_sec, label], ...]
Part B: RiskEstimator.reset(meta) / step(frame, t_sec) -> P(accident starts within 5 s)
The implementation lives in src/trafficwatch; all thresholds are in configs/pipeline.yaml.

Neither part ever raises: a video that cannot be read (truncated file, unknown codec) yields no
events and a flat risk curve instead of stopping the harness and costing the other videos.
"""
from __future__ import annotations

import math
import os
import sys
import traceback

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from trafficwatch.pipeline import detect_events as _detect_events  # noqa: E402
from trafficwatch.risk import CausalRisk  # noqa: E402

CLASSES = ["accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn",
           "stopped_vehicle", "jaywalking", "failure_to_yield", "illegal_turn",
           "solid_line_crossing", "stop_line", "congestion", "road_obstacle", "fire_smoke"]


def _warn(what: str) -> None:
    print(f"[trafficwatch] {what}:\n{traceback.format_exc()}", file=sys.stderr)


def detect_events(video_path: str) -> list[list]:
    """Part A. Return [[start_sec, end_sec, label], ...] for one .mp4."""
    try:
        return _detect_events(video_path)
    except Exception:
        _warn(f"detect_events failed on {video_path}")
        return []


class RiskEstimator:
    """Part B. Causal: step() sees frames in order and nothing else."""

    def __init__(self) -> None:
        self._impl = CausalRisk()

    def reset(self, meta: dict) -> None:
        # meta = {"video_id", "fps", "width", "height", "n_frames"}
        try:
            self._impl.reset(meta)
        except Exception:
            _warn(f"RiskEstimator.reset failed for {meta}")
            self._impl.reset({"fps": 25.0})

    def step(self, frame: np.ndarray, t_sec: float) -> float:
        # frame: BGR uint8 (H, W, 3). Return P(accident starts within 5 s) in [0, 1].
        try:
            p = float(self._impl.step(frame, t_sec))
        except Exception:
            _warn(f"RiskEstimator.step failed at t={t_sec}")
            p = float(getattr(self._impl, "score", 0.0))
        return min(max(p, 0.0), 1.0) if math.isfinite(p) else 0.0
