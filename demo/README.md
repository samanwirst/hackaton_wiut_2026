---
title: TrafficWatch Live Demo
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 5.50.0
python_version: "3.11"
app_file: app.py
pinned: false
license: agpl-3.0
---

Live demo of TrafficWatch (WIUT Hackathon 2026, Computer Vision track): upload a clip from the
road camera and get the detected traffic events, an annotated video and the accident-risk curve.
The code, weights and documentation are in the team repository linked from the website.

This Space package includes its source code and the repository's `LICENSE` (AGPL-3.0).
Detection uses the open YOLO11n COCO weights and ByteTrack from Ultralytics.

The public demo accepts MP4 clips up to 2 minutes and 500 MB. It reports progress during detection,
risk estimation and rendering, then provides the annotated video, interactive timeline and
downloadable `events.json`.

These are model predictions, not verified labels. The CPU demo uses YOLO11n and
sampled risk points; the GPU evaluation profile uses larger models and different
sampling. Their outputs need not match. Risk scores are heuristic and have not
been empirically calibrated; this research demo is not a safety guarantee.

The HTTP upload limit is enforced with Gradio's `max_file_size`; cached uploads/results are
eligible for removal after six hours, checked hourly (`delete_cache=(3600, 21600)`).
Rendering workspaces are removed immediately on success or failure; successful outputs are
first registered in the components' managed caches so playback/downloads remain available.
The six-hour age also avoids the pinned Gradio 5.50 cleanup implementation's modulo-24-hour
age comparison, which never expires a threshold of 86400 seconds. See the official
[file-access](https://www.gradio.app/guides/file-access) and
[resource-cleanup](https://www.gradio.app/guides/resource-cleanup) guides.
