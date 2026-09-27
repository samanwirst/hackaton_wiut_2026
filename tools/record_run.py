"""Record inputs and the environment of a completed organiser-harness run.

Run immediately after inference in the same environment, before changing source/configuration:
    python tools/record_run.py --videos data/samples --source-kind original --profile gpu
This records provenance; it does not establish accuracy, determinism or T4 runtime by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, list_videos

from trafficwatch.video import probe


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", required=True)
    ap.add_argument("--source-kind", choices=("original", "preview"), required=True)
    ap.add_argument("--profile", choices=("cpu", "gpu"), required=True)
    ap.add_argument("--pred", type=Path, default=ROOT / "predictions_samples.json")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/submission_run.json")
    args = ap.parse_args()
    predictions = json.loads(args.pred.read_text(encoding="utf-8"))
    inputs = {}
    for video in list_videos(args.videos):
        if video.name not in predictions.get("videos", {}):
            raise ValueError(f"No predictions for {video.name}")
        log = predictions.get("log", {}).get(video.name, {})
        if not log or log.get("errors") or log.get("total_sec", float("inf")) > log.get("budget_sec", 0):
            raise ValueError(f"Missing or failed harness run for {video.name}")
        info = probe(str(video))
        risk = predictions["videos"][video.name].get("risk", [])
        if len(risk) != info.n_frames:
            raise ValueError(f"{video.name}: expected {info.n_frames} risk samples, got {len(risk)}")
        inputs[video.name] = {
            "sha256": sha256(video), "bytes": video.stat().st_size,
            "width": info.width, "height": info.height, "fps": info.fps,
            "n_frames": info.n_frames, "duration": info.duration,
        }
    if set(inputs) != set(predictions.get("videos", {})):
        raise ValueError("Input folder does not match the videos in the prediction file")
    sources = [ROOT / "solution.py", *sorted((ROOT / "src").rglob("*.py"))]
    configs = sorted(p for p in (ROOT / "configs").iterdir() if p.is_file())
    packages = ("torch", "torchvision", "ultralytics", "opencv-python", "numpy", "scipy", "lap")
    doc = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input_kind": args.source_kind, "profile": args.profile,
        "predictions_sha256": sha256(args.pred), "inputs": inputs,
        "platform": platform.platform(), "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in packages},
        "config_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in configs},
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources},
        "limitations": [
            "Recorded after the run; source/config files must remain unchanged between inference and recording.",
            "No ground-truth accuracy measurement or T4 benchmark is implied.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(inputs)} input(s), {args.source_kind}/{args.profile}: {args.out}")


if __name__ == "__main__":
    main()
