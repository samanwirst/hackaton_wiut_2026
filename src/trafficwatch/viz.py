"""Annotated video rendering: boxes, track trails, scene layout, active events and a timeline band
with the risk curve under the picture. Written as browser-friendly H.264 through ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
from typing import Callable

import cv2
import numpy as np

from . import CLASSES
from .detector import category_of
from .perception import Perception
from .scene import Scene
from .signal import derive_signals
from .video import FrameReader

# Road-user boxes use the first four categorical slots (blue, orange, aqua, yellow), in BGR.
CATEGORY_BGR = {"vehicle": (214, 120, 42), "two_wheeler": (52, 104, 235), "person": (122, 175, 27),
                "animal": (0, 161, 237)}
EVENT_BGR = (72, 73, 227)      # involved objects and event labels: one accent; the text names the class
BAR_BGR = (214, 120, 42)       # timeline bars: one hue, the row label carries the class
RISK_BGR = (229, 135, 57)
BAND_H = 96
LABEL_W = 132


def ffmpeg_exe() -> str:
    """ffmpeg on the PATH, else the static binary shipped with imageio-ffmpeg if installed."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("ffmpeg not found: install it (apt-get install ffmpeg / brew install ffmpeg) "
                           "or pip install imageio-ffmpeg") from e


def _ffmpeg_writer(path: str, width: int, height: int, fps: float) -> subprocess.Popen:
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{width}x{height}", "-r", f"{fps:.3f}", "-i", "-", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


SIGNAL_BGR = {"red": (60, 60, 230), "amber": (40, 170, 240), "green": (90, 200, 60)}


def _draw_scene(img: np.ndarray, scene: Scene, s: float, t: float = 0.0, signals: dict | None = None) -> None:
    """Crossings, stop lines and solid lines; crossings and stop lines take the colour of their
    signal at time t (white / grey while it is unknown)."""
    signals = signals or {}

    def colour(sid, default):
        sig = signals.get(sid) if sid else None
        return SIGNAL_BGR.get(sig.state_at(t), default) if sig is not None else default

    for i, cw in enumerate(scene.raw.get("crosswalks", [])):
        sid = scene.crosswalk_signals[i] if i < len(scene.crosswalk_signals) else None
        cv2.polylines(img, [np.int32(np.asarray(cw["polygon"]) * s)], True, colour(sid, (255, 255, 255)), 1)
    for sl in scene.stop_lines:
        cv2.line(img, tuple(np.int32(sl.a * s)), tuple(np.int32(sl.b * s)), colour(sl.light, (0, 0, 255)), 2)
    for line in scene.solid_lines:
        cv2.polylines(img, [np.int32(line * s)], False, (0, 255, 255), 1)
    y = img.shape[0] - 8
    for sid in reversed(list(scene.lights) + [sp["id"] for sp in scene.signal_specs]):
        sig = signals.get(sid)
        if sig is None:
            continue
        state = sig.state_at(t)
        cv2.putText(img, f"{sid}: {state}", (img.shape[1] - 230, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    SIGNAL_BGR.get(state, (200, 200, 200)), 1, cv2.LINE_AA)
        y -= 18


def _draw_band(band: np.ndarray, t: float, duration: float, events: list[list],
               risk: tuple[np.ndarray, np.ndarray] | None) -> None:
    """Timeline under the picture: one labelled row per event class, the risk curve below."""
    h, w = band.shape[:2]
    band[:] = (26, 26, 25)
    labels = sorted({e[2] for e in events}, key=CLASSES.index)
    plot_w = w - LABEL_W - 8
    x_of = lambda sec: LABEL_W + int(round(sec / max(duration, 1e-6) * (plot_w - 1)))  # noqa: E731
    risk_h = 24
    top, bottom = 4, h - risk_h - 8
    row_h = max(6, min(14, (bottom - top) // max(len(labels), 1)))
    for k, label in enumerate(labels[: max(1, (bottom - top) // row_h)]):
        y = top + k * row_h
        cv2.putText(band, label, (6, y + row_h - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (195, 194, 183), 1, cv2.LINE_AA)
        for s, e, lab in events:
            if lab == label:
                cv2.rectangle(band, (x_of(s), y + 1), (max(x_of(e), x_of(s) + 2), y + row_h - 2), BAR_BGR, -1)
    base = h - 4
    cv2.putText(band, "accident risk", (6, base - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (195, 194, 183), 1, cv2.LINE_AA)
    cv2.line(band, (LABEL_W, base - risk_h // 2), (w - 8, base - risk_h // 2), (56, 56, 53), 1)   # 0.5
    if risk is not None and len(risk[0]):
        rt, rs = risk
        pts = np.stack([np.array([x_of(v) for v in rt]), np.int32(base - np.clip(rs, 0, 1) * risk_h)], axis=1)
        cv2.polylines(band, [pts.astype(np.int32)], False, RISK_BGR, 1, cv2.LINE_AA)
    cv2.line(band, (x_of(t), 0), (x_of(t), h - 1), (255, 255, 255), 1)


def render_video(video_path: str, perception: Perception, scene: Scene, events: list[list],
                 raw_events, out_path: str, risk: tuple[np.ndarray, np.ndarray] | None = None,
                 max_width: int = 960, every: int = 1, progress: Callable[[float], None] | None = None) -> str:
    info = perception.info
    s = min(1.0, max_width / info.width)
    w, h = int(info.width * s) // 2 * 2, int(info.height * s) // 2 * 2
    step = perception.stride * max(1, every)
    writer = _ffmpeg_writer(out_path, w, h + BAND_H, info.fps / step)
    rows = perception.rows
    by_frame: dict[int, np.ndarray] = {}
    if len(rows):
        order = np.argsort(rows[:, 0], kind="stable")
        frames, starts = np.unique(rows[order, 0].astype(int), return_index=True)
        for f, a, b in zip(frames, starts, list(starts[1:]) + [len(order)]):
            by_frame[int(f)] = rows[order[a:b]]
    trails: dict[int, list[tuple[int, int]]] = {}
    band = np.zeros((BAND_H, w, 3), np.uint8)
    signals = derive_signals(scene.signal_specs, perception.signals)
    for fidx, frame in FrameReader(video_path, stride=step):
        t = fidx / info.fps
        img = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        _draw_scene(img, scene, s, t, signals)
        now = [e for e in events if e[0] <= t <= e[1]]
        flagged = {tid for ev in raw_events if ev.start <= t <= ev.end for tid in ev.tracks}
        for r in by_frame.get(fidx, []):
            tid, cls_id = int(r[1]), int(r[7])
            x1, y1, x2, y2 = (r[2:6] * s).astype(int)
            color = EVENT_BGR if tid in flagged else CATEGORY_BGR.get(category_of(cls_id), (200, 200, 200))
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2 if tid in flagged else 1)
            cv2.putText(img, str(tid), (x1, max(10, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
            trail = trails.setdefault(tid, [])
            trail.append(((x1 + x2) // 2, y2))
            del trail[:-25]
            if len(trail) > 1:
                cv2.polylines(img, [np.int32(trail)], False, color, 1)
        y = 18
        for _, _, label in now:
            cv2.rectangle(img, (6, y - 13), (16 + 8 * len(label), y + 4), EVENT_BGR, -1)
            cv2.putText(img, label, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            y += 20
        cv2.putText(img, f"{t:6.1f}s", (w - 70, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        _draw_band(band, t, info.duration, events, risk)
        writer.stdin.write(np.vstack([img, band]).tobytes())
        if progress and info.n_frames:
            progress(min(fidx / info.n_frames, 1.0))
    writer.stdin.close()
    returncode = writer.wait()
    if returncode:
        raise RuntimeError(f"ffmpeg could not render the annotated video (exit status {returncode}).")
    return out_path
