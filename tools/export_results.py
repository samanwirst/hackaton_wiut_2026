"""Export per-video results for the website: annotated video, events, risk curve, dev labels.

Events and the risk curve are taken from a predictions file produced by the harness
(predictions_samples.json), so the website shows exactly what we submit. If the file has no
risk curve, Part B is recomputed with the same causal estimator.

    python tools/export_results.py --videos samples/ --pred predictions_samples.json \
        [--labels labels/dev_labels.json] --out website
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from common import ROOT, list_videos, perceive_cached

from trafficwatch.events import RULES, Context
from trafficwatch.pipeline import enabled_rules
from trafficwatch.risk import risk_curve_from_perception
from trafficwatch.segments import postprocess
from trafficwatch.viz import render_video


def export_video(video: Path, pred: dict | None, labels: dict | None, out: Path, profile: str | None) -> dict:
    P, scene, cfg = perceive_cached(video, profile)
    ctx = Context(P, scene, cfg)
    raw = [ev for label in enabled_rules(cfg) for ev in RULES[label](ctx)]
    entry = (pred or {}).get(video.name)
    events = entry["events"] if entry else postprocess(raw, P.info.duration, cfg, set(enabled_rules(cfg)))
    if entry and entry.get("risk"):
        r = np.asarray(entry["risk"], dtype=float)
        rt, rs = r[:, 0], r[:, 1]
    else:
        rt, rs = risk_curve_from_perception(P, cfg)
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    mp4 = media / f"{video.stem}_annotated.mp4"
    render_video(str(video), P, scene, events, raw, str(mp4), risk=(rt, rs))
    keep = np.linspace(0, len(rt) - 1, min(len(rt), 1500)).astype(int) if len(rt) else []
    doc = {
        "video": video.name, "duration": round(P.info.duration, 2), "fps": P.info.fps,
        "annotated": mp4.relative_to(out).as_posix(),
        "events": events,
        "labels": (labels or {}).get(video.name, {}).get("events"),
        "risk": [[round(float(rt[i]), 2), round(float(rs[i]), 3)] for i in keep],
        "details": [{"start": round(e.start, 2), "end": round(e.end, 2), "label": e.label,
                     "score": round(e.score, 3), "tracks": list(e.tracks)} for e in raw],
    }
    data = out / "data" / "results"
    data.mkdir(parents=True, exist_ok=True)
    with open(data / f"{video.stem}.json", "w") as f:
        json.dump(doc, f)
    return {"video": video.name, "file": f"data/results/{video.stem}.json", "events": len(events)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", required=True)
    ap.add_argument("--pred", default=None)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--out", default=str(ROOT / "website"))
    args = ap.parse_args()
    pred = labels = None
    if args.pred:
        with open(args.pred) as f:
            pred = json.load(f).get("videos")
    if args.labels:
        with open(args.labels) as f:
            labels = json.load(f)
    out = Path(args.out)
    index = [export_video(v, pred, labels, out, args.profile) for v in list_videos(args.videos)]
    with open(out / "data" / "results_index.json", "w") as f:
        json.dump(index, f)
    print(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
