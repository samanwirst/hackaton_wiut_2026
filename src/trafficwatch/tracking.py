"""Multi-object tracking with ByteTrack (Ultralytics implementation, used directly)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from .detector import ROAD_USERS, Detections


class Tracker:
    """Online ByteTrack over road users. ``update`` returns rows
    ``[x1, y1, x2, y2, track_id, score, cls]`` for the tracks matched in this frame."""

    def __init__(self, fps: float, high: float = 0.3, low: float = 0.1, new: float = 0.4,
                 buffer_s: float = 2.0, match: float = 0.8):
        from ultralytics.trackers.byte_tracker import BYTETracker

        args = SimpleNamespace(
            track_high_thresh=high, track_low_thresh=low, new_track_thresh=new,
            # BYTETracker keeps lost tracks for int(frame_rate / 30 * track_buffer) frames.
            track_buffer=int(round(buffer_s * 30)), match_thresh=match, fuse_score=True,
        )
        self._bt = BYTETracker(args, frame_rate=max(fps, 1.0))

    def update(self, det: Detections) -> np.ndarray:
        det = det.select(ROAD_USERS)
        tracks = self._bt.update(det, None)
        if len(tracks) == 0:
            return np.zeros((0, 7), dtype=np.float32)
        return np.asarray(tracks[:, :7], dtype=np.float32)


def make_tracker(cfg: dict, fps_eff: float) -> Tracker:
    t = cfg.get("tracker", {})
    return Tracker(fps_eff, high=t.get("high", 0.3), low=t.get("low", 0.1), new=t.get("new", 0.4),
                   buffer_s=t.get("buffer_s", 2.0), match=t.get("match", 0.8))
