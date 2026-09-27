# TrafficWatch — WIUT Hackathon 2026, Computer Vision track

TrafficWatch analyses a fixed road camera and returns candidate traffic events as labelled
time segments (Part A), plus a causal accident-risk score for the next 5 seconds at every
frame (Part B). The risk output follows the probability interface but is not empirically calibrated.

- **Website source:** [`website/`](website) · deployment target:
  `https://samanwirst.github.io/hackaton_wiut_2026/`
- **Live demo source:** [`demo/`](demo) (Hugging Face Space package; public URL is added at deployment)
- **Predictions on the sample videos:** [`predictions_samples.json`](predictions_samples.json)
- **Development history:** [reviewable stages and verification follow-ups](docs/development-history.md)

Local website preview: `python tools/serve_website.py`, then open `http://127.0.0.1:8765`.
This server supports MP4 range requests, which are needed for clicks on the event timeline to seek.

## Quick start (what the organisers run)

```bash
pip install -r requirements.txt            # Python 3.11–3.13 (tested: 3.11); or use Docker
python run_submission.py --videos /data/test --out predictions.json
```

`requirements.txt` selects the [official PyTorch 2.6 CUDA 12.4 wheels](https://docs.pytorch.org/get-started/previous-versions/#v260)
used by the evaluation profile. For a smaller CPU-only local environment, use
`pip install -r requirements/cpu.txt`; the public demo has its own self-contained CPU
requirements in `demo/requirements.txt`.

The numerical/tracking runtime is pinned to the versions actually used in verification:
OpenCV 4.14.0.94, NumPy 2.2.6, SciPy 1.17.1 and LAP 0.5.13. Use Python 3.11 for the
recorded environment; the pinned SciPy version requires Python ≥3.11. Pinning these installed
versions does not alter the completed runs. Transitive packages and platform details are
recorded separately where relevant; this is not a claim of cross-hardware bitwise equality.

All three public Ultralytics YOLO11 weights are already included in [`weights/`](weights)
(62.6 MiB total, far below 5 GB), so the two commands above need no weight-download step.
Optional integrity/repair command: `bash weights/download.sh` verifies all checksums and
downloads missing files from the Ultralytics release page. Run any repair before offline
evaluation; inference itself never downloads weights.

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
| Scene | Part A registers hand-drawn geometry to the clip with SIFT/RANSAC; the learned direction field remains independent | `scene.py`, `registration.py`, `direction_field.py` |
| Signals | calibrated lamp position + expected hue, including dim daylight signals; mode-filtered; hidden heads inferred by phase logic | `signal.py` |
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
| `illegal_u_turn` | heading turns ≥ 150° within 20 s inside an explicitly annotated prohibited zone; allowed areas override the prohibition |
| `illegal_turn` | turn into a prohibited entry→exit movement, or a turn not allowed from the entry lane |
| `solid_line_crossing` | both approximate wheel points change side of a solid marking |
| `red_light` | the vehicle's front crosses a stop line while its signal has been red for ≥ 0.3 s; ends when it has entered and left the junction box (or the frame). A vehicle that halts over the line and only goes on at green is a `stop_line` case |
| `stop_line` | vehicle stops past the stop line on red without entering the junction; ends at green |
| `jaywalking` | pedestrian (not a rider) walking on the carriageway outside a crossing for ≥ 1 s; crossing on red is not a separate official class |
| `failure_to_yield` | vehicle drives through a crossing while a pedestrian walks on it near its path (someone waiting at the kerb edge does not count) |
| `accident` | two road users come within contact range (normalised distance < 1 / lower-box overlap) after a fast approach; the striker loses ≥ 60 % of its speed within 1 s and has a complete half-second settling window. Joint track evidence of remaining close is required; for a pedestrian/vehicle pair the vehicle must have been moving, so walking up to a parked car is insufficient |
| `near_miss` | closest-approach analysis predicts contact within 2 s (road users driving towards each other only on a nearly head-on course; followers at the same pace never), a moving vehicle is involved, one of them brakes sharply or swerves (averaged over 0.5 s), and they never touch. **Off by default**: none of its 15 firings on the samples and C3905 was right |
| `road_obstacle` | animal on the carriageway, or a static foreign object that differs from the long-term background where no tracked road user is |
| `fire_smoke` | flickering saturated flame-coloured regions (off by default until validated) |

Rules requiring missing scene geometry stay silent. Such a class still contributes false negatives
and a zero F1 if it occurs in the hidden ground truth; only classes absent from both ground truth
and predictions are excluded from the macro average. The current scene has no verified U-turn
prohibitions, solid-line annotations or prohibited turn movements.

## Reproducing our results

1. Put the organisers' sample videos (C3896, C3897, C3902, C3905) in `data/samples/`, or fetch the
   public files from the organiser-provided Drive ids with `python tools/download_samples.py`.
   For quicker EDA and website generation, `python tools/download_samples.py --preview
   --out data/previews` downloads Drive's 1080p transcodes; exact benchmarking must use the
   original 4K files.
2. The camera's layout is [`configs/scene_tashkent.json`](configs/scene_tashkent.json): crossings, the
   stop line before the crossing, the two visible signal heads and the signals derived from them. It
   was drawn with [`tools/annotation/scene_editor.html`](tools/annotation/scene_editor.html) and is picked automatically
   for 3840×2160 video, then registered to a representative middle frame using the shipped
   grayscale reference. Part A permits this random access; Part B does not use it — see
   [`docs/scene.md`](docs/scene.md). No sample filenames or event answers enter inference.
3. Learn the road mask and direction field: `python tools/learn_scene.py --videos data/samples/`
4. Run the harness on the samples: `python run_submission.py --videos data/samples/ --out predictions_samples.json`
   On a machine with CUDA this uses the GPU profile, as on the evaluation machine. Without CUDA the
   CPU profile (a smaller model) would be picked instead. To get the evaluation machine's output
   there, force the GPU profile on another device:
   `TRAFFICWATCH_PROFILE=gpu TRAFFICWATCH_DEVICE=mps python run_submission.py --videos data/samples/ --out predictions_samples.json`
   (`mps` on Apple silicon, `cpu` elsewhere). Floating-point differences across devices can change
   threshold decisions and tracker associations; exact reproduction is checked on the same machine.
   The current `predictions_samples.json` is the validated GPU run on all four original 4K
   samples: 163 events and 33,075 per-frame risk scores. `reports/submission_run.json` records
   input/source/configuration hashes and package versions. The website's EDA, annotated videos,
   event segments and risk charts use the same original inputs and output.
   Immediately after any new run, record its inputs and source hashes:
   `python tools/record_run.py --videos data/samples/ --source-kind original --profile gpu`.
   Use `--videos data/previews --source-kind preview --profile cpu` only for a separate preview run.
5. Dev labels: annotate the samples with [`tools/annotation/label_tool.html`](tools/annotation/label_tool.html)
   ([`docs/labeling.md`](docs/labeling.md)) into `data/labels/dev_labels.json`, then
   `python evaluate.py --pred predictions_samples.json --gt data/labels/dev_labels.json`
6. Website data, in the CUDA environment: `python tools/eda.py --videos data/samples/ --profile gpu --source-kind original` and
   `python tools/export_results.py --videos data/samples/ --profile gpu --pred predictions_samples.json --source-kind original`.
   For a separate preview experiment use `--videos data/previews --profile cpu --source-kind preview`
   and a separately generated preview prediction file. Do not mix preview assets with the original-run submission.

Tests: `pytest -q` (102 tests with the development/demo dependencies installed, covering
trajectory rules, robustness cases, the official class definitions, signal phases,
post-processing, offline weights, prefix-causal Part B, demo input limits and output/cache cleanup,
website risk-curve/input-metadata consistency with the submitted output, camera-registration
rejection/determinism, and dim-lamp/reflection pixel regressions).
The 16 demo tests are skipped in inference-only environments without Gradio/Plotly.
CI also validates `predictions_samples.json`
and all committed weight checksums.

Browser verification: start `python tools/serve_website.py`, then in a second terminal run
`python tools/verify_website.py` (development dependencies and Chromium required). It checks
all four original playbacks, event/timeline/risk seeking, HTTP range requests and every EDA
image on desktop and mobile, including delayed video-selection responses, and saves screenshots
under `.cache/browser-qa/`.
Use `--base-url https://your-site/` to repeat it against the eventual public deployment.

The executed [evidence audit](notebooks/evidence_audit.ipynb) independently recomputes
run counts, runtime ratios, exact repeat equality and the scoped lamp-reader comparison.
See [notebook setup](notebooks/README.md) for the optional, separate authoring environment.
The [signal review](reports/scene_review/README.md) distinguishes tuning agreement from
held-out accuracy; no official event F1 is claimed without independent labels.

The [prepared-demo verification](reports/demo_verification/README.md) records actual two-minute
uploads on desktop/mobile, offline processing, progress, playback, chart/table/download and
over-length rejection. Run `python tools/verify_demo.py --video <test.mp4>` against a separately
started local demo; public testing is deferred until hosting and publication are authorised.

Run `python tools/check_submission.py` for a package audit, or add `--strict --online` before
creating the final tag to require all four sample visualisations, complete team profiles,
matching run provenance and reachable public URLs. Runtime on T4, visual correctness and an
actual public demo upload still require direct verification beyond this static audit.

The requirement-by-requirement status and remaining external prerequisites are tracked in
[`docs/submission-readiness.md`](docs/submission-readiness.md).
The publication steps and public-upload checklist are in
[`docs/deployment.md`](docs/deployment.md); preparing files locally does not publish them.

## Determinism

`seed: 0` in the config seeds Python, NumPy and PyTorch; cuDNN runs in deterministic mode and
benchmark mode is off. The pipeline has no sampling or learned randomness at inference, frame
subsampling is fixed per device profile (never adapted to wall-clock time), and tracking is
deterministic. All four original samples have been repeated offline on the same host: every
event and all 33,075 risk timestamp/value pairs match exactly. Both current-model passes
used one fresh process per video, serially. The harness's timing
logs naturally differ, so complete JSON file hashes are not expected to match.
The additional default command with all four originals in a single fresh process also
matches exactly, checking that cross-video process state does not change these results.
Evidence and execution limits are in [`reports/original_gpu/calibrated/`](reports/original_gpu/calibrated/).

## Runtime

GPU profile: YOLO11m at 960 px for Part A (target 12.5 processed fps), YOLO11s at 640 px for
Part B (target 8.34 fps). CPU: YOLO11n at 640 px for both parts (target 6.25 fps).
Stride is `round(source_fps / target_fps)`: for 29.97 fps samples it is 2/4 on GPU and 5/5
on CPU; at 25 fps it is 2/3 and 4/4. It never adapts to wall-clock time.

The current registered-layout / hue-aware revision passed two complete offline original-video
passes on an **RTX 3050 Laptop (4 GB VRAM)**. Timings include Part A and Part B:

| Original | First pass | Repeat | Allowed | Event segments |
|---|---:|---:|---:|---:|
| C3896 | 452.1 s | 574.4 s | 1021.0 s | 41 |
| C3897 | 436.4 s | 434.5 s | 953.5 s | 54 |
| C3902 | 449.7 s | 516.6 s | 953.5 s | 48 |
| C3905 | 158.0 s | 203.0 s | 382.9 s | 20 |

Runtime was **1.24–1.41× duration on the first pass** and **1.37–1.69× on the repeat**,
below the 3× budget in every run. These are observed desktop-host measurements, not an
isolated benchmark or a T4 result. The documented host sleep during the repeat is excluded
by the harness's monotonic timer; see [complete evidence](reports/original_gpu/calibrated/).
The additional one-process whole-folder run took 487.2 / 463.4 / 470.0 / 174.9 seconds
(1.37–1.48× duration), with the same event/risk output and unchanged inference sources.

`predictions_samples.json` and `reports/submission_run.json` are the first pass, with matching
four H.264 annotated videos, timelines/risk curves and 20 original EDA images. There are
163 segments and 33,075 per-frame risk scores; these counts and repeat equality do not
establish detection accuracy. **T4-class verification remains outstanding.**

Earlier [CPU previews](reports/preview_cpu/), [GPU previews](reports/gpu_preview/) and
[original-run baselines](reports/original_gpu/) are preserved separately. The
[accident review](reports/accident_review/) and [signal review](reports/scene_review/)
explain the model changes and their limited visual evidence.

## Data and models

| Item | Licence | Use |
|---|---|---|
| Organisers' sample videos | provided for the hackathon | EDA, rule development and scoped visual-review notes (`data/labels/`); a complete dev-label set is not yet included |
| YOLO11 n/s/m COCO weights (Ultralytics) | AGPL-3.0 | detection |
| ByteTrack (Ultralytics implementation) | AGPL-3.0 (orig. MIT) | tracking |
| COCO (indirectly through pretrained weights) | annotations: CC BY 4.0; images: their respective Flickr terms ([official terms](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/termsofuse.htm)) | no COCO images redistributed or fine-tuning performed here |

No other dataset is used for training. Because Ultralytics is AGPL-3.0, this repository is
released under AGPL-3.0 as well (see [`LICENSE`](LICENSE)).

## Repository layout

```text
.
├── solution.py                 public interface imported by the harness
├── run_submission.py           organisers' harness, unchanged
├── evaluate.py                 organisers' metric, unchanged
├── predictions_samples.json    sample submission output
├── requirements.txt            evaluation (GPU) entry point
├── requirements/
│   ├── base.txt                shared runtime dependencies
│   ├── cpu.txt                 CPU environment and CI
│   └── dev.txt                 local tools, tests and demo dependencies
├── src/trafficwatch/            inference pipeline and event rules
├── configs/                     pipeline settings and scene models
├── weights/                     model weights and download script
├── data/
│   ├── samples/                original videos (local, ignored by Git)
│   ├── previews/               smaller preview videos (local, ignored by Git)
│   └── labels/                 dev annotations, when available
├── tools/
│   ├── annotation/             standalone HTML labelling and scene editors
│   └── *.py                    downloads, EDA, exports and package checks
├── tests/                       automated tests
├── reports/                     run provenance and preserved results
├── notebooks/                   executed, reproducible evidence audit
├── docs/
│   └── references/             organiser PDFs/archives (local, ignored by Git)
├── demo/                        self-contained Hugging Face / Gradio app
├── website/                     static website, its data and media
├── .github/workflows/           tests and website deployment
├── pyproject.toml               test and lint settings
├── Dockerfile                  evaluation container
├── README.md
└── LICENSE
```

Run commands from the repository root. `requirements.txt`, the organiser scripts,
`solution.py` and `weights/` stay at their submission-compatible paths. Generated
`.cache/`, `runs/` and `space/` directories are local artefacts and stay out of Git.

## Team

Registered team: **Zero Context**, WIUT, Computer Vision track. The captain's official
participant portal confirms this name and a submission deadline of **27 September 2026,
23:59 Asia/Tashkent (UTC+5)**. TrafficWatch is the project name; existing experiment
outputs use the project identifier `trafficwatch` in their non-scoring `team` metadata.

| Member | Role | Contributions | Links |
|---|---|---|---|
| Mukhammadiev Samandar Shavkatovich | Captain · Core development & engineering | Equal core contributor: substantially refactored and re-engineered the basic implementation into a professional-grade codebase | [GitHub](https://github.com/samanwirst) |
| Muxiddinov Shohruxxo’ja Usmonxo’ja o’g’li | Polish & debugging | Polished the project and debugged implementation issues | Links pending |
| Doniyorbek Raximov Mehriddinovich | Core development & foundation | Equal core contributor: created the project foundation and initial baseline implementation | Links pending |

All three names and the captain designation are verified against the official participant portal;
the captain confirmed this contribution breakdown. Samandar and Doniyorbek share equal core
development credit; refactoring and engineering are substantial development work, not a
supporting role. The remaining profile/portfolio links and
previous projects still need to be supplied before publication. Private registration contact
details are intentionally excluded.

Code, website and report were written with the help of AI assistants, which the rules allow; no
hosted model is called at inference.
