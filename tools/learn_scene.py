"""Learn the scene model from the sample videos: drivable-area mask and direction field.

The carriageway is where moving vehicles put their wheels; the direction field is the histogram
of vehicle headings per image cell. Both are saved to configs/scene_model_tashkent.npz and a preview image
is written so the result can be checked by eye.

    python tools/learn_scene.py --videos data/samples/ [--profile cpu]
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np
from common import ROOT, list_videos, perceive_cached

from trafficwatch.direction_field import DirectionField

DOWN = 4   # road mask is stored at 1/4 resolution


def footprint_map(tracks_per_video, width: int, height: int, min_nspeed: float = 0.3) -> np.ndarray:
    """Number of distinct moving-vehicle tracks whose wheels touched each (downscaled) pixel."""
    h, w = height // DOWN, width // DOWN
    hits = np.zeros((h, w), np.float32)
    for tracks in tracks_per_video:
        for tr in tracks:
            if not tr.is_vehicle:
                continue
            layer = np.zeros((h, w), np.uint8)
            for box, v, ok in zip(tr.box, tr.nspeed, tr.reliable):
                if v < min_nspeed or not ok:
                    continue
                x1, y1, x2, y2 = box / DOWN
                bw, bh = x2 - x1, y2 - y1
                cv2.rectangle(layer, (int(x1 + 0.1 * bw), int(y2 - 0.25 * bh)), (int(x2 - 0.1 * bw), int(y2)), 1, -1)
            hits += layer
    return hits


def road_from_footprints(hits: np.ndarray, min_tracks: int) -> np.ndarray:
    road = (hits >= min_tracks).astype(np.uint8)
    k = np.ones((5, 5), np.uint8)
    road = cv2.morphologyEx(road, cv2.MORPH_CLOSE, k, iterations=2)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(road)
    keep = np.zeros_like(road)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= 0.002 * road.size:
            keep[labels == i] = 1
    return keep.astype(bool)


def preview(frame: np.ndarray, road: np.ndarray, field: DirectionField, out_path) -> None:
    h, w = frame.shape[:2]
    img = frame.copy()
    mask = cv2.resize(road.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    img[mask] = (0.6 * img[mask] + 0.4 * np.array([0, 180, 0])).astype(np.uint8)
    for cy in range(field.gy):
        for cx in range(field.gx):
            if field.total[cy, cx] < 20:
                continue
            x, y = (cx + 0.5) * w / field.gx, (cy + 0.5) * h / field.gy
            ang, strength = field.dominant(np.array([[x, y]]))
            if strength[0] < 0.15:
                continue
            L = 0.4 * w / field.gx
            end = (int(x + L * np.cos(ang[0])), int(y + L * np.sin(ang[0])))
            cv2.arrowedLine(img, (int(x), int(y)), end, (0, 255, 255), 2, tipLength=0.4)
    cv2.imwrite(str(out_path), img)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", required=True)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--out", default=str(ROOT / "configs" / "scene_model_tashkent.npz"))
    ap.add_argument("--min-tracks", type=int, default=3)
    ap.add_argument("--preview", default=str(ROOT / "docs" / "scene_model_tashkent_preview.jpg"))
    args = ap.parse_args()
    videos = list_videos(args.videos)
    per_video, info = [], None
    for v in videos:
        perception, _, _ = perceive_cached(v, args.profile)
        per_video.append(perception.tracks)
        info = perception.info
        print(f"{v.name}: {len(perception.tracks)} tracks")
    hits = footprint_map(per_video, info.width, info.height)
    road = road_from_footprints(hits, args.min_tracks)
    field = DirectionField.learn(per_video, info.width, info.height)
    np.savez_compressed(args.out, road_mask=road, counts=field.counts, width=info.width, height=info.height,
                        footprints=hits)
    cap = cv2.VideoCapture(str(videos[0]))
    ok, frame = cap.read()
    cap.release()
    if ok:
        preview(frame, road, field, args.preview)
    print(f"saved {args.out}; road covers {road.mean():.1%} of the frame")


if __name__ == "__main__":
    main()
