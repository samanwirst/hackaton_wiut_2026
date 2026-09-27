"""Reproduce the scoped lamp-state review from original samples; never imported by inference.

python tools/review_signals.py --videos data/samples --out reports/scene_review
The historical baseline uses the fixed layout and V>=150/S>=80 lamp-box reader.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from common import ROOT

from trafficwatch.config import load_config
from trafficwatch.scene import load_scene, load_video_scene
from trafficwatch.signal import classify, read_light


def historical_read(frame, spec):
    scores = {}
    h, w = frame.shape[:2]
    for colour, box in spec["lamps"].items():
        x1, y1, x2, y2 = map(round, box)
        crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if not crop.size:
            scores[colour] = 0.0
            continue
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        scores[colour] = float(((hsv[..., 2] >= 150) & (hsv[..., 1] >= 80)).mean())
    return classify(scores, min_frac=.04)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--labels", type=Path, default=ROOT / "data/labels/signal_spotchecks.json")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    labels = json.loads(args.labels.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    records, registrations = [], {}
    for name, samples in labels["videos"].items():
        path = args.videos / name
        cap = cv2.VideoCapture(str(path))
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cfg = load_config()
        baseline = load_scene(cfg, width, height)
        scene = load_video_scene(cfg, str(path), width, height)
        registrations[name] = scene.raw.get("_registration")
        sheet = np.zeros((600, 220 * len(samples), 3), np.uint8)
        try:
            for column, (timestamp, expected) in enumerate(samples):
                frame_index = round(timestamp * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError(f"Cannot read {name} frame {frame_index}")
                for row, light in enumerate(labels["lights"]):
                    spec = scene.light_specs[light]
                    before = historical_read(frame, baseline.light_specs[light])
                    geometry_only = historical_read(frame, spec)
                    after = read_light(frame, spec)
                    records.append({"video": name, "frame": frame_index, "time": frame_index / fps,
                                    "light": light, "reviewed_state": expected,
                                    "fixed_layout_brightness": before, "registered_brightness": geometry_only,
                                    "registered_hue": after})
                    x1, y1, x2, y2 = spec["roi"]
                    crop = frame[max(0, y1-15):min(height, y2+15), max(0, x1-15):min(width, x2+15)]
                    scale = min(200 / crop.shape[1], 190 / crop.shape[0])
                    resized = cv2.resize(crop, (round(crop.shape[1]*scale), round(crop.shape[0]*scale)),
                                         interpolation=cv2.INTER_NEAREST)
                    ox, oy = column*220+10, row*300+32
                    sheet[oy:oy+resized.shape[0], ox:ox+resized.shape[1]] = resized
                    for dy, text in ((20, f"{light} @ {timestamp}s"), (242, f"review: {expected}"),
                                     (264, f"baseline: {before}"), (286, f"current: {after}")):
                        cv2.putText(sheet, text, (column*220+7, row*300+dy), cv2.FONT_HERSHEY_SIMPLEX,
                                    .43, (255, 255, 255), 1, cv2.LINE_AA)
        finally:
            cap.release()
        if not cv2.imwrite(str(args.out / f"{path.stem}_signals.png"), sheet):
            raise RuntimeError("Failed to write review sheet")
        print(name, "reviewed", flush=True)
    modes = ("fixed_layout_brightness", "registered_brightness", "registered_hue")
    counts = {mode: {"matches_review": sum(r[mode] == r["reviewed_state"] for r in records),
                     "unknown": sum(r[mode] == "unknown" for r in records), "total": len(records)} for mode in modes}
    report = {"scope": labels["scope"], "notes": labels["notes"], "counts": counts,
              "registrations": registrations, "observations": records}
    (args.out / "signal_review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
