"""Object detection with a pretrained YOLO model (COCO classes)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import resolve

# COCO class ids we care about.
PERSON = {0}
TWO_WHEELER = {1, 3}           # bicycle, motorcycle
VEHICLE = {2, 5, 7}            # car, bus, truck
ANIMAL = {15, 16, 17, 18, 19, 20, 21, 22, 23}
TRAFFIC_LIGHT = {9}
ROAD_USERS = PERSON | TWO_WHEELER | VEHICLE | ANIMAL
DETECT_CLASSES = sorted(ROAD_USERS | TRAFFIC_LIGHT)


def category_of(cls_id: int) -> str:
    c = int(cls_id)
    if c in VEHICLE:
        return "vehicle"
    if c in TWO_WHEELER:
        return "two_wheeler"
    if c in PERSON:
        return "person"
    if c in ANIMAL:
        return "animal"
    if c in TRAFFIC_LIGHT:
        return "traffic_light"
    return "other"


class Detections:
    """Minimal box container with the attributes ByteTrack reads (conf, cls, xywh, indexing)."""

    def __init__(self, xyxy: np.ndarray, conf: np.ndarray, cls: np.ndarray):
        self.xyxy = np.asarray(xyxy, dtype=np.float32).reshape(-1, 4)
        self.conf = np.asarray(conf, dtype=np.float32).reshape(-1)
        self.cls = np.asarray(cls, dtype=np.float32).reshape(-1)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, idx) -> Detections:
        return Detections(self.xyxy[idx], self.conf[idx], self.cls[idx])

    @property
    def xywh(self) -> np.ndarray:
        x1, y1, x2, y2 = self.xyxy.T
        return np.stack([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], axis=1)

    def select(self, class_ids) -> Detections:
        return self[np.isin(self.cls.astype(int), list(class_ids))]


def box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between (N,4) and (M,4) xyxy boxes."""
    a = np.asarray(a, dtype=np.float32).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float32).reshape(-1, 4)
    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(rb - lt, 0, None)
    inter = wh[..., 0] * wh[..., 1]
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-6)


def paired_overlap(a: np.ndarray, b: np.ndarray, mode: str = "iou") -> np.ndarray:
    """Element-wise overlap of two equally long (N,4) box arrays.
    ``mode="iou"``: intersection over union; ``mode="min"``: intersection over the smaller box."""
    a = np.asarray(a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 4)
    w = np.clip(np.minimum(a[:, 2], b[:, 2]) - np.maximum(a[:, 0], b[:, 0]), 0, None)
    h = np.clip(np.minimum(a[:, 3], b[:, 3]) - np.maximum(a[:, 1], b[:, 1]), 0, None)
    inter = w * h
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    denom = np.minimum(area_a, area_b) if mode == "min" else area_a + area_b - inter
    return inter / np.maximum(denom, 1e-6)


def merge_vehicle_duplicates(det: Detections, iou_thr: float) -> Detections:
    """Class-agnostic NMS among car/bus/truck so one vehicle never becomes two tracks."""
    is_veh = np.isin(det.cls.astype(int), list(VEHICLE))
    idx = np.flatnonzero(is_veh)
    if len(idx) < 2:
        return det
    order = idx[np.argsort(-det.conf[idx], kind="stable")]
    ious = box_iou(det.xyxy[order], det.xyxy[order])
    keep_mask = np.ones(len(order), dtype=bool)
    for i in range(len(order)):
        if keep_mask[i]:
            keep_mask[i + 1:] &= ious[i, i + 1:] < iou_thr
    drop = set(order[~keep_mask].tolist())
    keep = np.array([i for i in range(len(det)) if i not in drop], dtype=int)
    return det[keep]


class Detector:
    def __init__(self, weights: str, device: str = "cpu", imgsz: int = 640, conf: float = 0.1,
                 iou: float = 0.6, half: bool = False, batch: int = 8, vehicle_merge_iou: float = 0.7):
        from ultralytics import YOLO

        self.model = YOLO(str(resolve(weights)))
        self.device = device
        self.imgsz = imgsz
        self.conf = conf
        self.iou = iou
        self.half = half
        self.batch = batch
        self.vehicle_merge_iou = vehicle_merge_iou

    def __call__(self, frames: list[np.ndarray]) -> list[Detections]:
        out: list[Detections] = []
        for i in range(0, len(frames), self.batch):
            results = self.model.predict(
                frames[i:i + self.batch], imgsz=self.imgsz, conf=self.conf, iou=self.iou,
                device=self.device, half=self.half, classes=DETECT_CLASSES, verbose=False,
            )
            for r in results:
                b = r.boxes
                det = Detections(b.xyxy.cpu().numpy(), b.conf.cpu().numpy(), b.cls.cpu().numpy())
                out.append(merge_vehicle_duplicates(det, self.vehicle_merge_iou))
        return out


@lru_cache(maxsize=4)
def get_detector(weights: str, device: str, imgsz: int, half: bool, batch: int,
                 conf: float, iou: float, vehicle_merge_iou: float) -> Detector:
    """Load each model once per process; the harness calls us once per video."""
    return Detector(weights, device, imgsz, conf, iou, half, batch, vehicle_merge_iou)
