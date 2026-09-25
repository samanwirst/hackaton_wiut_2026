"""Build synthetic tracks / perception results so every rule can be tested without video."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trafficwatch.config import load_config  # noqa: E402
from trafficwatch.events.common import Context  # noqa: E402
from trafficwatch.perception import Perception  # noqa: E402
from trafficwatch.scene import Scene  # noqa: E402
from trafficwatch.tracks import build_tracks  # noqa: E402
from trafficwatch.video import VideoInfo  # noqa: E402

FPS = 25.0
STRIDE = 2
W, H = 1280, 720
CAR, PERSON, MOTORBIKE = 2, 0, 3


def path_rows(tid: int, cls_id: int, keyframes: list[tuple[float, float, float]], size=(80, 50),
              fps: float = FPS, stride: int = STRIDE) -> np.ndarray:
    """Rows for one object moving through (t, x_center, y_bottom) keyframes (linear in between)."""
    kt = np.array([k[0] for k in keyframes])
    frames = np.arange(int(np.ceil(kt[0] * fps / stride)) * stride, int(kt[-1] * fps) + 1, stride)
    t = frames / fps
    x = np.interp(t, kt, [k[1] for k in keyframes])
    y = np.interp(t, kt, [k[2] for k in keyframes])
    w, h = size
    return np.column_stack([frames, np.full(len(t), tid), x - w / 2, y - h, x + w / 2, y,
                            np.full(len(t), 0.9), np.full(len(t), cls_id)])


def make_context(rows_list: list[np.ndarray], duration: float, scene: Scene | None = None,
                 cfg: dict | None = None, signals: dict | None = None) -> Context:
    cfg = cfg or load_config()
    rows = np.concatenate(rows_list) if rows_list else np.zeros((0, 8))
    tracks = build_tracks(rows, FPS, STRIDE, 0.8, 0.6, frame_size=(W, H))
    n_frames = int(duration * FPS)
    times = np.arange(0, n_frames, STRIDE) / FPS
    perception = Perception(
        info=VideoInfo("synthetic.mp4", FPS, n_frames, W, H), stride=STRIDE, profile="test",
        times=times, rows=rows, tracks=tracks, light_boxes=np.zeros((0, 6)), signals=signals or {},
        bg_times=np.zeros(0), bg_frames=np.zeros((0, 9, 16, 3), np.uint8), brightness=np.zeros(len(times)),
    )
    return Context(perception, scene or Scene(W, H), cfg)
