# Clean Python environment: offline GPU verification

This is a **local GPU check on one official 1080p preview**, not the final four-sample
submission and not a benchmark on the organisers' original 4K footage or T4 machine.
The root `predictions_samples.json` remains the separately documented CPU/preview run.
Both runs below were performed on 2026-09-26.

## Environment and method

- A new Python 3.11.14 virtual environment was created under the ignored `.cache/` directory.
- Only `pip install -r requirements.txt` was needed to install the inference dependencies;
  `pip check` found no broken requirements. The existing CPU `.venv` was not modified.
- The host is Linux x86_64, Intel Core i5-11400H (6 cores / 12 threads), about 7.4 GiB RAM,
  NVIDIA GeForce RTX 3050 Laptop GPU (4 GiB), driver 610.57.04.
- PyTorch 2.6.0+cu124 and torchvision 0.21.0+cu124 imported successfully and detected CUDA.
- The default `auto` setting selected the unchanged `gpu` profile: YOLO11m/960/FP16,
  batch 16 for Part A; YOLO11s/640 for Part B. No smaller model or lower batch was substituted.
- Each harness process ran inside `unshare --user --map-root-user --net`. An outbound socket
  check in that namespace failed with `ENETUNREACH`, so no internet was available during inference.
- `TRAFFICWATCH_CACHE`, `TRAFFICWATCH_PROFILE` and `TRAFFICWATCH_DEVICE` were unset for the run.

The unchanged organiser command was:

```bash
unshare --user --map-root-user --net \
  env -u TRAFFICWATCH_CACHE -u TRAFFICWATCH_PROFILE -u TRAFFICWATCH_DEVICE \
  "$GPU_CHECK_PYTHON" -u run_submission.py \
  --videos data/previews/C3905.MP4 \
  --out reports/gpu_preview/predictions-first.json --team trafficwatch
```

`GPU_CHECK_PYTHON` denotes the new environment's Python executable. The namespace command
requires Linux with unprivileged user namespaces enabled. Other systems need an equivalent
network-isolation mechanism. Installation itself used the network, as allowed by the task.

## Results and repeatability

| Run (C3905.MP4) | Video duration | Part A | Part B | Total | Budget | Events | Risk scores |
|---|---:|---:|---:|---:|---:|---:|---:|
| First | 127.63 s | 57.7 s | 20.0 s | 77.8 s | 382.9 s | 22 | 3,825 |
| Repeat, fresh process | 127.63 s | 59.2 s | 20.2 s | 79.4 s | 382.9 s | 22 | 3,825 |

The official harness logged no errors in either run. The official evaluator reported zero
format errors and zero warnings for both outputs. Risk was non-constant, ranging from
0.0100 to 0.9167.

The second process used the same command with `--out reports/gpu_preview/predictions-repeat.json`.
All 22 event segments and all 3,825 frame timestamps/scores are **exactly equal** between the
two `videos` objects. The whole files differ because the harness records measured timing in `log`.
This verifies repeatability for this full clip on this machine, not for every possible input.

Canonical `videos` JSON (`sort_keys=True`, `separators=(",", ":")`) has SHA-256:
`eb50d3cd38162c450a37189f4f7c8f9232c4d20c6e067c0c749d0085bf257736`.

`run.json` records the input checksum, dimensions, exact frame count, key package versions,
and source/configuration hashes. The input is the official Drive preview, not other footage
collected from the same camera.

Installation input SHA-256 values:

```text
0acb98cf52a0b12f76e116f25ce0a75fb00f064d98fc43c874976609ccea59ed  requirements.txt
29899d3571cb3c6dfaa4e26e018c92fa9802482dc4f0de6bd640e35600aad61b  requirements/base.txt
```

## Limits of this evidence

This proves that the checked source runs with the root CUDA dependencies in a fresh Python
environment on this host, without internet during inference. It does not prove installation
on a fresh operating system: the host's system libraries and NVIDIA driver were already installed.
It also does not establish hidden-set accuracy, accident-risk calibration, all-sample coverage,
or the runtime of original 4K recordings on the organisers' specified hardware.
