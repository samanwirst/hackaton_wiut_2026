"""Register hand-drawn scene geometry to a representative frame of the current clip.

Only static image correspondences are used: there are no video-name or timestamp rules.
The independently learned direction field is not transformed by this module.
"""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


def _features(gray: np.ndarray):
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.SIFT_create(nfeatures=5000, contrastThreshold=0.02).detectAndCompute(gray, None)


@lru_cache(maxsize=4)
def _reference(path: str, mtime_ns: int):
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Scene registration reference is missing or unreadable: {path}")
    points, descriptors = _features(image)
    return image.shape, points, descriptors


def estimate_registration(reference_path: Path, frame: np.ndarray) -> tuple[np.ndarray | None, dict]:
    """Return reference-to-frame affine geometry only when broad, consistent support exists."""
    (rh, rw), keypoints, descriptors = _reference(str(reference_path), reference_path.stat().st_mtime_ns)
    height, width = frame.shape[:2]
    target = cv2.resize(frame, (rw, rh), interpolation=cv2.INTER_AREA)
    if target.ndim == 3:
        target = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    other, other_descriptors = _features(target)
    evidence = {"status": "rejected", "matches": 0, "inliers": 0}
    if descriptors is None or other_descriptors is None or len(other_descriptors) < 2:
        evidence["reason"] = "insufficient image features"
        return None, evidence
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(descriptors, other_descriptors, k=2)
    matches = [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < .75 * n.distance]
    evidence["matches"] = len(matches)
    if len(matches) < 40:
        evidence["reason"] = "too few distinctive matches"
        return None, evidence
    source = np.float32([keypoints[m.queryIdx].pt for m in matches])
    dest = np.float32([other[m.trainIdx].pt for m in matches])
    cv2.setRNGSeed(0)
    matrix, mask = cv2.estimateAffinePartial2D(source, dest, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.0, maxIters=4000,
                                             confidence=.999, refineIters=10)
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        evidence["reason"] = "no stable transform"
        return None, evidence
    keep = mask.ravel().astype(bool)
    inliers = int(keep.sum())
    if not inliers:
        evidence["reason"] = "no geometric inliers"
        return None, evidence
    residual = np.linalg.norm(source @ matrix[:, :2].T + matrix[:, 2] - dest, axis=1)
    span = np.ptp(source[keep], axis=0) / [rw, rh]
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    rotation = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    error = float(np.median(residual[keep]))
    evidence.update(inliers=inliers, inlier_ratio=float(keep.mean()),
                    median_error_px=error, span_fraction=span.tolist(),
                    scale=scale, rotation_deg=rotation)
    if (inliers < 40 or keep.mean() < .45 or error > 1.5 or
            span[0] < .4 or span[1] < .35 or not .95 <= scale <= 1.05 or
            abs(rotation) > 3 or np.any(np.abs(matrix[:, 2]) / [rw, rh] > .08)):
        evidence["reason"] = "transform lacks broad support or exceeds small-camera-motion bounds"
        return None, evidence
    # The layout has already been scaled to frame dimensions by load_scene().
    full = np.diag([width / rw, height / rh, 1.0]) @ np.vstack([matrix, [0, 0, 1]])
    full = full @ np.diag([rw / width, rh / height, 1.0])
    evidence.update(status="accepted", matrix=full[:2].tolist())
    return full[:2], evidence


def transform_layout(raw: dict, matrix: np.ndarray) -> dict:
    """Transform only geometric fields; signal timing and registration metadata stay intact."""
    out = copy.deepcopy(raw)

    def points(value):
        if len(value) == 2 and all(np.isscalar(v) for v in value):
            return (matrix[:, :2] @ np.asarray(value, dtype=float) + matrix[:, 2]).tolist()
        return [points(item) for item in value]

    def vector(value):
        v = matrix[:, :2] @ np.asarray(value, dtype=float)
        return (v / max(float(np.linalg.norm(v)), 1e-9)).tolist()

    def box(value):
        x1, y1, x2, y2 = value
        corners = np.asarray(points([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]))
        return [*corners.min(axis=0).tolist(), *corners.max(axis=0).tolist()]

    for key in ("road", "road_exclude", "intersection", "parking", "ignore",
                "u_turn_allowed", "u_turn_prohibited"):
        if out.get(key):
            out[key] = points(out[key])
    for key in ("crosswalks", "zones", "lanes", "direction_groups"):
        for item in out.get(key, []):
            item["polygon"] = points(item["polygon"])
            if "direction" in item:
                item["direction"] = vector(item["direction"])
    for item in out.get("stop_lines", []):
        item["line"] = points(item["line"])
        item["forward"] = vector(item.get("forward", [0, -1]))
    for item in out.get("solid_lines", []):
        item["polyline"] = points(item["polyline"])
    for item in out.get("traffic_lights", []):
        item["roi"] = box(item["roi"])
        for colour, value in item.get("lamps", {}).items():
            item["lamps"][colour] = box(value)
    return out
