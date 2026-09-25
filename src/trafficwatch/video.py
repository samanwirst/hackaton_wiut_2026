"""Video probing and strided frame reading with a background decoding thread."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np


@dataclass(frozen=True)
class VideoInfo:
    path: str
    fps: float
    n_frames: int
    width: int
    height: int

    @property
    def duration(self) -> float:
        return self.n_frames / self.fps if self.fps > 0 else 0.0

    def with_frames(self, n_frames: int) -> VideoInfo:
        return VideoInfo(self.path, self.fps, n_frames, self.width, self.height)


def probe(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if not np.isfinite(fps) or fps < 1.0:
        fps = 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return VideoInfo(str(path), fps, n, w, h)


_END = object()


class FrameReader:
    """Iterate ``(frame_index, frame)`` for every ``stride``-th frame.

    Frames in between are only grabbed (decoded but not converted), which is the cheapest way
    to skip frames in inter-coded video. Decoding runs in a thread so it overlaps with model
    inference. After iteration ``n_decoded`` holds the true number of frames in the file.
    """

    def __init__(self, path: str, stride: int = 1, prefetch: int = 32):
        self.path = str(path)
        self.stride = max(1, int(stride))
        self.prefetch = prefetch
        self.n_decoded = 0

    def __iter__(self) -> Iterator[tuple[int, np.ndarray]]:
        q: queue.Queue = queue.Queue(maxsize=self.prefetch)
        stop = threading.Event()
        count = [0]

        def put(item) -> bool:
            while not stop.is_set():
                try:
                    q.put(item, timeout=0.1)
                    return True
                except queue.Full:
                    continue
            return False

        def worker() -> None:
            cap = cv2.VideoCapture(self.path)
            idx = 0
            try:
                while not stop.is_set():
                    if idx % self.stride == 0:
                        ok, frame = cap.read()
                        if not ok:
                            break
                        if not put((idx, frame)):
                            break
                    elif not cap.grab():
                        break
                    idx += 1
            finally:
                count[0] = idx
                cap.release()
                put(_END)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                item = q.get()
                if item is _END:
                    break
                yield item
        finally:
            stop.set()
            thread.join(timeout=5)
            self.n_decoded = count[0]
