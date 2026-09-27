"""Extract a reproducible grayscale first-frame reference for the annotated camera.

    python tools/build_scene_reference.py --video data/samples/C3905.MP4 \
        --out configs/scene_reference_tashkent.png

The input must be the organiser-provided original used to draw the scene layout.
This is scene calibration, not a prediction or a runtime download.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"Refusing to overwrite {args.out}; choose a new output path")
    if args.width < 64:
        parser.error("--width must be at least 64")
    cap = cv2.VideoCapture(str(args.video))
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read {args.video}")
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, (args.width, round(h * args.width / w)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.out), gray):
        raise RuntimeError(f"Cannot write {args.out}")
    print(f"Saved frame 0 from {args.video}: {args.out} ({gray.shape[1]}×{gray.shape[0]})")


if __name__ == "__main__":
    main()
