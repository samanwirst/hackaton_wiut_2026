# Initial CPU preview run

This is the preserved run **before** the pedestrian-class corrections to match the organiser's
definitions. It is evidence for runtime and the previous predictions, not the final submission.
The updated provisional output is at the repository root in `predictions_samples.json`.

The unchanged organiser harness processed two official Drive preview transcodes on 2026-09-26:

```bash
TRAFFICWATCH_PROFILE=cpu python run_submission.py --videos samples_preview \
  --out reports/preview_cpu/predictions.json --team trafficwatch
```

The command above records the original run. Following the repository reorganisation,
the same preview files are stored in `data/previews/`.

| Clip | Duration | Part A | Part B | Total | Budget | Events | Risk samples |
|---|---:|---:|---:|---:|---:|---:|---:|
| C3902.MP4 | 317.82 s | 118.4 s | 131.1 s | 249.6 s | 953.5 s | 20 | 9,525 |
| C3905.MP4 | 127.63 s | 48.6 s | 60.8 s | 109.4 s | 382.9 s | 14 | 3,825 |

Both logs contain no errors; the official validator reported no errors or warnings.
There are no dev labels, so these event counts are not accuracy measurements.
The measurements include both passes; C3902 overlapped a short demo upload test.

Environment: Intel Core i5-11400H (6 cores / 12 threads), Linux x86_64, Python 3.11.14,
torch 2.6.0+cpu, torchvision 0.21.0+cpu, Ultralytics 8.3.253, OpenCV 4.14.0.94,
NumPy 2.2.6, SciPy 1.17.1, lap 0.5.13. YOLO11n/640, stride 5 in both passes.

Input SHA-256 (1920×1080 at 29.97 fps):

```text
f861d2d0e3320b2464d0331159c70c428e0f03b1e5274a9125e7b0927082206c  C3902.MP4
08b6a68098df568bf9987c57f38390bbd898827180865a2d2dd8f048ea8741cc  C3905.MP4
```

Pre-correction pipeline configuration SHA-256:
`665ddb14e60478d65ccc94c6441704a2d09099fda00c702ceca6737cc8e4273c`.
The original 4K files and T4 evaluation profile still require a separate benchmark.
