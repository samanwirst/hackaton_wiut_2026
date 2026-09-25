# TrafficWatch — WIUT Hackathon 2026, Computer Vision track

TrafficWatch watches a fixed road camera, reports every traffic event as a time segment with a
class (Part A), and outputs, frame by frame, the probability that an accident starts within the
next 5 seconds (Part B).

- **Website:** `TODO: link` (team, approach, EDA, results, live demo, report)
- **Live demo:** `TODO: Hugging Face Space link`
- **Predictions on the sample videos:** [`predictions_samples.json`](predictions_samples.json)

## Quick start (what the organisers run)

```bash
pip install -r requirements.txt            # Python 3.10–3.13; or: docker build -t team .
bash weights/download.sh                   # once, with internet: fetches missing weights, checks SHA-256
python run_submission.py --videos /data/test --out predictions.json
```

The model weights are three public Ultralytics YOLO11 files (≈ 64 MB in total, far below the 5 GB
limit) in [`weights/`](weights). `weights/download.sh` downloads any that are missing from the
Ultralytics release page and verifies all checksums; after that the run is fully offline.

Check the output format before submitting:

```bash
python evaluate.py --pred predictions.json --validate-only
```

## How it works

```
 video ──► decode every k-th frame (threaded) ──► YOLO11 detector ──► ByteTrack ──► tracks
                                                                                  │
  scene layout (configs/scene_tashkent.json) + learned model (configs/scene_model_tashkent.npz)
                                                                                  │
            14 event rules on trajectories ◄──────────────────────────────────────┘
                          │
             segment post-processing (merge / drop blips / clip / no same-class overlap)
                          │
                 [[start_sec, end_sec, label], ...]                         (Part A)

 frames one by one ──► light YOLO11 + ByteTrack (every k-th frame) ──► closest-approach
 conflicts, hard braking, wrong-way motion ──► evidence fusion ──► hold/decay ──► logistic
 calibration ──► P(accident within 5 s)                                     (Part B)
```

**Learned vs rule-based.** The only learned components are the pretrained COCO detectors
(YOLO11m for Part A and YOLO11s for Part B on GPU; YOLO11n for both on the CPU fallback) and the statistics we learn from
the sample videos (the drivable-area mask and the per-cell direction field). Everything that
turns detections into events is an explicit, tunable rule on trajectories and scene geometry, with
all thresholds in [`configs/pipeline.yaml`](configs/pipeline.yaml).

| Stage | What it does | Where |
|---|---|---|
| Frame reading | decodes in a background thread; skipped frames are only grabbed | `src/trafficwatch/video.py` |
| Detection | YOLO11 on batches of frames; car/bus/truck duplicates merged | `detector.py` |
| Tracking | ByteTrack (low-score second association), ids kept through 2 s occlusions | `tracking.py` |
| Kinematics | per-track resampling, Savitzky–Golay smoothing, size-normalised speed | `tracks.py` |
| Scene | hand-drawn layout + learned road mask and direction field | `scene.py`, `direction_field.py` |
| Signals | state of each visible head from which lamp is lit, mode-filtered; heads that face away from the camera derived from visible ones by phase logic | `signal.py` |
| Events | one rule per class | `events/` |
| Post-processing | merge fragments, drop short blips, clip, no same-class overlap | `segments.py` |
| Part B | causal risk from tracks | `risk.py` |

Speeds and distances are divided by the object's size (`sqrt(box_w × box_h)`), so thresholds
read as "object lengths per second" and hold at any distance from the camera for sideways motion.
Motion along the line of sight is foreshortened (image speed falls with distance², size only with
distance), which is why "same pace" comparisons use `vy / size²` there (`geometry.same_pace`).

Boxes that touch the frame border are flagged (`Track.edge`) and never trusted: a car leaving at
the bottom of the frame has its box clipped there, so it seems to stop - which used to turn every
exiting car into a stopped vehicle, a crash with the car behind it, or a U-turn.

### Event rules (summary)

| Class | Rule |
|---|---|
| `stopped_vehicle` | vehicle still ≥ 10 s on the carriageway while traffic in its direction drives past it in a neighbouring lane (so a signal queue, or the car ahead driving off at green, does not count); stationary fragments of one vehicle are joined across track ids. A vehicle that stopped behind a signalised stop line on red and drives off within 20 s of green is queueing, however long the red |
| `congestion` | per direction of travel: ≥ 4 vehicles, median speed crawling, most of them stopped, for ≥ 30 s; vehicles waiting behind a stop line on red (and the queue driving off after green) do not count |
| `wrong_way` | heading that the learned direction field says is (almost) never seen at that place while the opposite heading is common, for ≥ 1.5 s — or against a hand-drawn lane direction |
| `illegal_u_turn` | heading turns ≥ 150° within 20 s outside zones where U-turns are allowed |
| `illegal_turn` | turn into a prohibited entry→exit movement, or a turn not allowed from the entry lane |
| `solid_line_crossing` | both approximate wheel points change side of a solid marking |
| `red_light` | the vehicle's front crosses a stop line while its signal has been red for ≥ 0.3 s; ends when it has entered and left the junction box (or the frame). A vehicle that halts over the line and only goes on at green is a `stop_line` case |
| `stop_line` | vehicle stops past the stop line on red without entering the junction; ends at green |
| `jaywalking` | pedestrian (not a rider) walking on the carriageway outside a crossing for ≥ 1 s; or stepping from a kerb or island onto a crossing whose pedestrian signal has been red ≥ 2 s (not within 2 s of its green) and walking on over it |
| `failure_to_yield` | vehicle drives through a crossing while a pedestrian walks on it near its path (someone waiting at the kerb edge does not count) |
| `accident` | two road users come within contact range (normalised distance < 1 / lower-box overlap) after a fast approach; the striker was still moving at contact, loses ≥ 60 % of its speed within 1 s, comes to rest and stays next to the other (a queue closing up or a car driving past a stopped bus is not) |
| `near_miss` | closest-approach analysis predicts contact within 2 s (road users driving towards each other only on a nearly head-on course; followers at the same pace never), a moving vehicle is involved, one of them brakes sharply or swerves (averaged over 0.5 s), and they never touch. **Off by default**: none of its 15 firings on the samples and C3905 was right |
| `road_obstacle` | animal on the carriageway, or a static foreign object that differs from the long-term background where no tracked road user is |
| `fire_smoke` | flickering saturated flame-coloured regions (off by default until validated) |

Classes whose rule needs scene geometry that has not been drawn yet stay silent, which keeps them
out of the macro-F1 average instead of adding a zero.

## Reproducing our results

1. Put the organisers' sample videos (C3896, C3897, C3902, C3905) in `samples/`.
2. The camera's layout is [`configs/scene_tashkent.json`](configs/scene_tashkent.json): crossings, the
   stop line before the crossing, the two visible signal heads and the signals derived from them. It
   was drawn with [`tools/scene_editor.html`](tools/scene_editor.html) and is picked automatically
   for 3840×2160 video — see [`docs/scene.md`](docs/scene.md).
3. Learn the road mask and direction field: `python tools/learn_scene.py --videos samples/`
4. Run the harness on the samples: `python run_submission.py --videos samples/ --out predictions_samples.json`
   On a machine with CUDA this uses the GPU profile, as on the evaluation machine. Without CUDA the
   CPU profile (a smaller model) would be picked instead. To get the evaluation machine's output
   there, force the GPU profile on another device:
   `TRAFFICWATCH_PROFILE=gpu TRAFFICWATCH_DEVICE=mps python run_submission.py --videos samples/ --out predictions_samples.json`
   (`mps` on Apple silicon, `cpu` elsewhere; only fp16 rounding differs from a T4). `predictions_samples.json`
   was made this way.
5. Dev labels: annotate the samples with [`tools/label_tool.html`](tools/label_tool.html)
   ([`docs/labeling.md`](docs/labeling.md)) into `labels/dev_labels.json`, then
   `python evaluate.py --pred predictions_samples.json --gt labels/dev_labels.json`
6. Website data: `python tools/eda.py --videos samples/` and
   `python tools/export_results.py --videos samples/ --pred predictions_samples.json`

Tests: `pytest -q` (rules on trajectories generated in code, derived signals, post-processing, the
official metric, Part B).

## Determinism

`seed: 0` in the config seeds Python, NumPy and PyTorch; cuDNN runs in deterministic mode and
benchmark mode is off. The pipeline has no sampling or learned randomness at inference, frame
subsampling is fixed per device profile (never adapted to wall-clock time), and tracking is
deterministic, so two runs on the same machine give the same `predictions.json` (floating-point
noise aside).

## Runtime

GPU profile (used when CUDA is available): YOLO11m at 960 px on every 2nd frame for Part A, YOLO11s
at 640 px on every 3rd frame for Part B. CPU fallback: YOLO11n at 640 px on every 4th frame for both
parts, which stays inside the budget even on a 2-core machine. Measured with the official harness
on C3905 (127.6 s of 4K video): GPU profile on an Apple M5 (MPS) 245 s, CPU profile 150 s, against a
budget of 383 s; a T4 is faster than the M5 for this model. The limit is 3× the video duration; frame subsampling is fixed per profile, never
adapted to wall-clock time, so results stay deterministic.

## Data and models

| Item | Licence | Use |
|---|---|---|
| Organisers' sample videos | provided for the hackathon | EDA, rule tuning, our dev labels (`labels/`) |
| YOLO11 n/s/m COCO weights (Ultralytics) | AGPL-3.0 | detection |
| ByteTrack (Ultralytics implementation) | AGPL-3.0 (orig. MIT) | tracking |
| COCO dataset (via the pretrained weights) | CC BY 4.0 | — |

No other dataset is used for training. Because Ultralytics is AGPL-3.0, this repository is
released under AGPL-3.0 as well (see [`LICENSE`](LICENSE)).

## Repository layout

```
solution.py              interface imported by the harness (thin wrapper)
run_submission.py        organisers' harness, unchanged
evaluate.py              organisers' metric, unchanged
configs/                 pipeline.yaml (all thresholds), scene_tashkent.json, scene_model_tashkent.npz
src/trafficwatch/        detector, tracking, kinematics, scene, rules, post-processing, Part B, rendering
tools/                   labeling + scene tools (HTML), EDA, scene learning, result export
tests/                   unit tests on trajectories generated in code
docs/                    scene layout and labelling conventions
demo/                    Hugging Face Space (Gradio) for the live demo
website/                 static team website (GitHub Pages)
weights/                 YOLO11 weights + download.sh
```

## Team

| Member | Role | Contributions | Links |
|---|---|---|---|
| TODO | TODO | TODO | GitHub · LinkedIn · portfolio |
| TODO | TODO | TODO | GitHub · LinkedIn · portfolio |
| TODO | TODO | TODO | GitHub · LinkedIn · portfolio |

Code, website and report were written with the help of AI assistants, which the rules allow; no
hosted model is called at inference.
