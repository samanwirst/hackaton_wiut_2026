"""Small 2-D geometry helpers in image coordinates (x right, y down)."""
from __future__ import annotations

import cv2
import numpy as np


def polygon_mask(polygons, width: int, height: int) -> np.ndarray:
    """Rasterise one polygon ``[[x, y], ...]`` or a list of polygons into a bool mask."""
    mask = np.zeros((height, width), dtype=np.uint8)
    if polygons is None or len(polygons) == 0:
        return mask.astype(bool)
    first = np.asarray(polygons[0])
    polys = [polygons] if first.ndim == 1 else polygons
    for poly in polys:
        pts = np.round(np.asarray(poly, dtype=np.float64)).astype(np.int32)
        if len(pts) >= 3:
            cv2.fillPoly(mask, [pts], 1)
    return mask.astype(bool)


def lookup(mask: np.ndarray, pts: np.ndarray, outside: bool = False) -> np.ndarray:
    """Value of a 2-D mask/label map at points (N, 2); points outside the image get ``outside``."""
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    h, w = mask.shape[:2]
    x = np.round(pts[:, 0]).astype(int)
    y = np.round(pts[:, 1]).astype(int)
    inside = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    out = np.full(len(pts), outside, dtype=mask.dtype)
    out[inside] = mask[y[inside], x[inside]]
    return out


def signed_distance_to_line(a, b, pts) -> np.ndarray:
    """Signed perpendicular distance of points to the infinite line a->b (positive = left of a->b
    in image coordinates, i.e. counter-clockwise on screen)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    d = b - a
    n = np.hypot(*d) + 1e-9
    return (d[0] * (pts[:, 1] - a[1]) - d[1] * (pts[:, 0] - a[0])) / n


def projection_param(a, b, pts) -> np.ndarray:
    """Position of the projection of points onto segment a->b (0 at a, 1 at b)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    d = b - a
    # element-wise, not ``@``: numpy's matmul on macOS (Accelerate) raises spurious FP warnings here
    return ((pts[:, 0] - a[0]) * d[0] + (pts[:, 1] - a[1]) * d[1]) / (d[0] ** 2 + d[1] ** 2 + 1e-9)


def polyline_side(polyline, pts) -> tuple[np.ndarray, np.ndarray]:
    """For each point: signed distance to the nearest segment of the polyline, and whether the
    projection falls inside that segment (points beyond the polyline ends are not 'alongside')."""
    poly = np.asarray(polyline, dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    best_d = np.full(len(pts), np.inf)
    best_s = np.zeros(len(pts))
    alongside = np.zeros(len(pts), dtype=bool)
    for a, b in zip(poly[:-1], poly[1:]):
        u = projection_param(a, b, pts)
        uc = np.clip(u, 0.0, 1.0)
        proj = a + uc[:, None] * (b - a)
        dist = np.hypot(*(pts - proj).T)
        better = dist < best_d
        best_d[better] = dist[better]
        best_s[better] = signed_distance_to_line(a, b, pts[better])
        alongside[better] = (u[better] >= 0.0) & (u[better] <= 1.0)
    return best_s, alongside


def angle_diff(a, b) -> np.ndarray:
    """Smallest absolute difference between angles (radians), in [0, pi]."""
    d = np.abs((np.asarray(a) - np.asarray(b) + np.pi) % (2 * np.pi) - np.pi)
    return d


def lower_box(box: np.ndarray, frac: float = 0.4) -> np.ndarray:
    """Bottom part of xyxy boxes - a rough proxy for the ground footprint."""
    box = np.asarray(box, dtype=np.float64).reshape(-1, 4).copy()
    h = box[:, 3] - box[:, 1]
    box[:, 1] = box[:, 3] - frac * h
    return box


def front_point(box: np.ndarray, heading: np.ndarray) -> np.ndarray:
    """Approximate ground position of a vehicle's front given its heading.

    Moving down the image (towards the camera) the front is the bottom edge; moving up, the
    front is roughly half the box height above it; sideways it is the leading side.
    """
    box = np.asarray(box, dtype=np.float64).reshape(-1, 4)
    h = np.nan_to_num(np.asarray(heading, dtype=np.float64).reshape(-1))
    cx = (box[:, 0] + box[:, 2]) / 2
    w = box[:, 2] - box[:, 0]
    bh = box[:, 3] - box[:, 1]
    fx = cx + 0.4 * w * np.cos(h)
    fy = box[:, 3] + 0.5 * bh * np.minimum(np.sin(h), 0.0)
    return np.stack([fx, fy], axis=1)


def same_pace(va, sa, vb, sb, max_ratio: float = 1.4, max_angle_deg: float = 45.0) -> np.ndarray:
    """Whether two road users drive the same way at about the same real speed, judged from image
    velocities (N, 2) and object sizes (N,). Perspective makes a naive comparison fail: sideways
    image motion scales with 1/distance like the object size, but motion along the line of sight
    with 1/distance^2 - so for mostly vertical motion we compare vy / size^2, otherwise |v| / size.
    Two cars following each other away from the camera converge in the image towards the vanishing
    point; a constant-velocity extrapolation in pixels takes that for closing in."""
    va, vb = np.atleast_2d(np.asarray(va, dtype=np.float64)), np.atleast_2d(np.asarray(vb, dtype=np.float64))
    sa, sb = np.maximum(np.atleast_1d(np.asarray(sa, dtype=np.float64)), 1e-6), np.maximum(np.atleast_1d(np.asarray(sb, dtype=np.float64)), 1e-6)
    na, nb = np.hypot(*va.T), np.hypot(*vb.T)
    cos = (va * vb).sum(axis=1) / np.maximum(na * nb, 1e-9)
    along = (np.abs(va[:, 1]) > np.abs(va[:, 0])) & (np.abs(vb[:, 1]) > np.abs(vb[:, 0]))
    pa = np.where(along, np.abs(va[:, 1]) / sa ** 2, na / sa)
    pb = np.where(along, np.abs(vb[:, 1]) / sb ** 2, nb / sb)
    ratio = np.maximum(pa, pb) / np.maximum(np.minimum(pa, pb), 1e-9)
    return (na > 1e-6) & (nb > 1e-6) & (cos > np.cos(np.deg2rad(max_angle_deg))) & (ratio < max_ratio)
