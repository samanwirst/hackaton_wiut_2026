"""One decoding pass over a video: detection, tracking, traffic-light colour and background samples.

Everything the Part A rules need is collected here, so the video is decoded exactly once.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

from .detector import TRAFFIC_LIGHT, get_detector
from .runtime import pick_profile, stride_for
from .scene import Scene
from .signal import SignalTimeline, read_light
from .tracking import make_tracker
from .tracks import Track, build_tracks
from .video import FrameReader, VideoInfo, probe

BG_WIDTH = 256          # background samples are stored at this width
BG_PERIOD_S = 1.0       # ... once per second


@dataclass
class Perception:
    info: VideoInfo
    stride: int
    profile: str
    times: np.ndarray                    # processed frame timestamps
    rows: np.ndarray                     # tracker rows [frame, tid, x1, y1, x2, y2, conf, cls]
    tracks: list[Track]
    light_boxes: np.ndarray              # detected traffic lights [t, x1, y1, x2, y2, conf]
    signals: dict[str, SignalTimeline]
    bg_times: np.ndarray
    bg_frames: np.ndarray                # (N, h, w, 3) uint8, small
    brightness: np.ndarray               # mean luma per processed frame (EDA: lighting)
    detections: list = field(default_factory=list)   # per processed frame (for the demo's Part B)
    timings: dict = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return self.stride / self.info.fps


def run_perception(video_path: str, cfg: dict, scene: Scene, profile_name: str | None = None,
                   progress: Callable[[float], None] | None = None) -> Perception:
    t_start = time.perf_counter()
    info = probe(video_path)
    pname, prof = pick_profile(cfg, profile_name)
    stride = stride_for(info.fps, prof["target_fps"])
    dcfg = cfg.get("detector", {})
    detector = get_detector(prof["weights"], prof["device"], int(prof["imgsz"]), bool(prof["half"]),
                            int(prof["batch"]), float(dcfg.get("conf", 0.1)), float(dcfg.get("iou", 0.6)),
                            float(dcfg.get("vehicle_merge_iou", 0.7)))
    tracker = make_tracker(cfg, info.fps / stride)

    rows: list[np.ndarray] = []
    light_rows: list[list[float]] = []
    frame_dets: list = []
    times: list[float] = []
    brightness: list[float] = []
    light_ids = list(scene.lights.keys())
    light_specs = {lid: scene.light_specs.get(lid) or {"roi": scene.lights[lid]} for lid in light_ids}
    light_states: dict[str, list[str]] = {k: [] for k in light_ids}
    bg_times: list[float] = []
    bg_frames: list[np.ndarray] = []
    next_bg = 0.0
    bg_size = (BG_WIDTH, max(1, int(round(BG_WIDTH * info.height / max(info.width, 1)))))
    batch_frames: list[np.ndarray] = []
    batch_idx: list[int] = []
    t_detect = 0.0

    def flush() -> None:
        nonlocal t_detect
        if not batch_frames:
            return
        t0 = time.perf_counter()
        dets = detector(batch_frames)
        t_detect += time.perf_counter() - t0
        for fidx, det in zip(batch_idx, dets):
            t = fidx / info.fps
            frame_dets.append(det)
            lights = det.select(TRAFFIC_LIGHT)
            for b, c in zip(lights.xyxy, lights.conf):
                light_rows.append([t, *b.tolist(), float(c)])
            tr = tracker.update(det)
            if len(tr):
                rows.append(np.column_stack([np.full(len(tr), fidx), tr[:, 4], tr[:, :4], tr[:, 5], tr[:, 6]]))
        batch_frames.clear()
        batch_idx.clear()

    reader = FrameReader(video_path, stride=stride)
    total = max(info.n_frames, 1)
    for fidx, frame in reader:
        t = fidx / info.fps
        times.append(t)
        small = cv2.resize(frame, bg_size, interpolation=cv2.INTER_AREA)
        brightness.append(float(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean()))
        if t >= next_bg:
            bg_times.append(t)
            bg_frames.append(small)
            next_bg += BG_PERIOD_S
        for lid in light_ids:
            light_states[lid].append(read_light(frame, light_specs[lid]))
        batch_frames.append(frame)
        batch_idx.append(fidx)
        if len(batch_frames) >= detector.batch:
            flush()
            if progress:
                progress(min(fidx / total, 1.0))
    flush()
    info = info.with_frames(reader.n_decoded or info.n_frames)

    kin = cfg.get("kinematics", {})
    all_rows = np.concatenate(rows) if rows else np.zeros((0, 8))
    tracks = build_tracks(all_rows, info.fps, stride, kin.get("smooth_s", 0.8), kin.get("min_track_s", 0.6),
                          frame_size=(info.width, info.height))
    times_arr = np.asarray(times)
    signals = {lid: SignalTimeline(times_arr, states) for lid, states in light_states.items()}
    return Perception(
        info=info, stride=stride, profile=pname, times=times_arr, rows=all_rows, tracks=tracks,
        light_boxes=np.asarray(light_rows).reshape(-1, 6), signals=signals,
        bg_times=np.asarray(bg_times),
        bg_frames=np.stack(bg_frames) if bg_frames else np.zeros((0, bg_size[1], bg_size[0], 3), np.uint8),
        brightness=np.asarray(brightness),
        detections=frame_dets,
        timings={"total_s": time.perf_counter() - t_start, "detect_s": t_detect},
    )
