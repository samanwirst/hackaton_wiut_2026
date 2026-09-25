"""Exploratory data analysis of the sample videos, exported for the website.

Per video: resolution, fps, duration, lighting over time, object counts over time by class,
speed distribution, where vehicles / pedestrians move and stop (heatmaps), trajectories coloured
by direction, and detected traffic-light positions (used to set up configs/scene_tashkent.json).

    python tools/eda.py --videos samples/ --out website/data
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from common import ROOT, list_videos, perceive_cached

CATS = ("vehicle", "two_wheeler", "person", "animal")


def first_frame(video: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 10)
    ok, frame = cap.read()
    cap.release()
    return frame


def heat_overlay(frame: np.ndarray, pts: np.ndarray, sigma: float = 12.0) -> np.ndarray:
    h, w = frame.shape[:2]
    acc = np.zeros((h, w), np.float32)
    if len(pts):
        x = np.clip(pts[:, 0].astype(int), 0, w - 1)
        y = np.clip(pts[:, 1].astype(int), 0, h - 1)
        np.add.at(acc, (y, x), 1.0)
    acc = cv2.GaussianBlur(acc, (0, 0), sigma)
    if acc.max() > 0:
        acc = np.sqrt(acc / acc.max())
    color = cv2.applyColorMap((acc * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    alpha = (acc[..., None] * 0.85).astype(np.float32)
    base = (frame * 0.55).astype(np.float32)
    return (base * (1 - alpha) + color * alpha).astype(np.uint8)


def trajectories(frame: np.ndarray, tracks) -> np.ndarray:
    img = (frame * 0.45).astype(np.uint8)
    for tr in tracks:
        if not tr.is_vehicle or len(tr.t) < 3:
            continue
        d = tr.gp[-1] - tr.gp[0]
        hue = int((np.degrees(np.arctan2(d[1], d[0])) % 360) / 2)
        color = tuple(int(v) for v in cv2.cvtColor(np.uint8([[[hue, 230, 255]]]), cv2.COLOR_HSV2BGR)[0, 0])
        cv2.polylines(img, [np.int32(tr.gp)], False, color, 1, cv2.LINE_AA)
        cv2.circle(img, tuple(np.int32(tr.gp[-1])), 2, color, -1)
    return img


def light_clusters(boxes: np.ndarray, min_hits: int = 10) -> list[dict]:
    """Traffic lights seen repeatedly at the same place -> candidate ROIs for scene.json."""
    clusters: list[dict] = []
    for _t, x1, y1, x2, y2, _conf in boxes:
        c = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
        for cl in clusters:
            if np.hypot(*(cl["c"] - c)) < max(x2 - x1, 8):
                cl["n"] += 1
                cl["boxes"].append([x1, y1, x2, y2])
                break
        else:
            clusters.append({"c": c, "n": 1, "boxes": [[x1, y1, x2, y2]]})
    out = []
    for cl in clusters:
        if cl["n"] >= min_hits:
            b = np.median(np.array(cl["boxes"]), axis=0)
            out.append({"roi": [round(float(v), 1) for v in b], "hits": cl["n"]})
    return sorted(out, key=lambda d: -d["hits"])


def analyse(video: Path, profile: str | None, img_dir: Path, site_root: Path) -> dict:
    P, _, _ = perceive_cached(video, profile)
    info = P.info
    frame = first_frame(video)
    stem = video.stem
    sec = np.arange(int(np.floor(info.duration)) + 1)
    counts = {c: np.zeros(len(sec), int) for c in CATS}
    for tr in P.tracks:
        if tr.category in counts:
            s0, s1 = int(tr.t0), int(tr.t1)
            counts[tr.category][s0:s1 + 1] += 1
    veh_pts = np.concatenate([tr.gp[tr.nspeed > 0.3] for tr in P.tracks if tr.is_vehicle] or [np.zeros((0, 2))])
    stop_pts = np.concatenate([tr.gp[tr.nspeed < 0.08] for tr in P.tracks if tr.is_vehicle] or [np.zeros((0, 2))])
    ped_pts = np.concatenate([tr.gp for tr in P.tracks if tr.category == "person"] or [np.zeros((0, 2))])
    images = {
        "frame": frame,
        "heat_vehicles": heat_overlay(frame, veh_pts),
        "heat_stops": heat_overlay(frame, stop_pts),
        "heat_pedestrians": heat_overlay(frame, ped_pts),
        "trajectories": trajectories(frame, P.tracks),
    }
    paths = {}
    for name, img in images.items():
        p = img_dir / f"{stem}_{name}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        paths[name] = p.relative_to(site_root).as_posix()
    vspeeds = np.concatenate([tr.nspeed for tr in P.tracks if tr.is_vehicle] or [np.zeros(0)])
    hist, edges = np.histogram(np.clip(vspeeds, 0, 8), bins=32, range=(0, 8))
    bright = P.brightness
    per_sec = np.interp(sec, P.times, bright) if len(bright) else np.zeros(len(sec))
    return {
        "video": video.name, "width": info.width, "height": info.height, "fps": round(info.fps, 3),
        "duration": round(info.duration, 2), "n_frames": info.n_frames,
        "brightness": {"mean": round(float(bright.mean()), 1) if len(bright) else None,
                       "per_second": [round(float(v), 1) for v in per_sec]},
        "tracks_by_class": dict(Counter(tr.category for tr in P.tracks)),
        "counts_per_second": {c: v.tolist() for c, v in counts.items()},
        "vehicle_speed_hist": {"counts": hist.tolist(), "edges": edges.round(2).tolist()},
        "stopped_share": round(float((vspeeds < 0.08).mean()), 3) if len(vspeeds) else None,
        "traffic_lights": light_clusters(P.light_boxes),
        "images": paths,
        "perception_s": round(P.timings.get("total_s", 0.0), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", required=True)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--out", default=str(ROOT / "website" / "data"))
    args = ap.parse_args()
    out = Path(args.out)
    img_dir = out / "eda"
    img_dir.mkdir(parents=True, exist_ok=True)
    report = [analyse(v, args.profile, img_dir, out.parent) for v in list_videos(args.videos)]
    with open(out / "eda.json", "w") as f:
        json.dump({"videos": report}, f)
    for r in report:
        print(f"{r['video']}: {r['width']}x{r['height']} @ {r['fps']} fps, {r['duration']} s, "
              f"brightness {r['brightness']['mean']}, tracks {r['tracks_by_class']}, lights {len(r['traffic_lights'])}")


if __name__ == "__main__":
    main()
