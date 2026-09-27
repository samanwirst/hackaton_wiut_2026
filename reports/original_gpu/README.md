# Original 4K samples: offline GPU verification

The latest validated full run is **`predictions-reviewed.json`**, with source/input provenance
in **`run-reviewed.json`**. It includes the accident-evidence correction described in
[`reports/accident_review/`](../accident_review). Older runs are preserved as the pre-correction
baseline; their source hashes identify the old rule.

All four original videos supplied by the user were checked on 2026-09-27 (Asia/Samarkand),
after two independent checks of `C3905.MP4`. This is original footage, **not** the 1080p Drive previews.
The root `predictions_samples.json` now equals the reviewed full original run, and
`reports/submission_run.json` equals its manifest. Matching original EDA, annotated media,
events and risk curves have been validated and promoted to `website/` together. Older preview
artefacts were backed up locally before replacement; the baseline results below are preserved.

## Current-rule complete-set run

The unchanged organiser harness ran offline in a fresh process with all developer-cache and
device/profile overrides unset. The command was the one below with `--videos data/samples/`
and `--out reports/original_gpu/predictions-reviewed.json`.

| Input | Duration | Part A | Part B | Combined | Allowed | Events | Risk scores |
|---|---:|---:|---:|---:|---:|---:|---:|
| C3896 | 340.34 s | 200.3 s | 203.4 s | 403.7 s | 1021.0 s | 42 | 10,200 |
| C3897 | 317.82 s | 192.6 s | 193.9 s | 386.5 s | 953.5 s | 55 | 9,525 |
| C3902 | 317.82 s | 192.9 s | 187.8 s | 380.7 s | 953.5 s | 48 | 9,525 |
| C3905 | 127.63 s | 84.8 s | 76.7 s | 161.5 s | 382.9 s | 20 | 3,825 |

Official validation reports **4 videos, 165 events, zero errors and zero warnings**. Every
frame has one risk score at the expected rounded frame timestamp, every score is within [0, 1],
all event boundaries lie within the input duration, and all four logs are error-free. Combined
runtime is **1.186–1.265× input duration**, below the 3× limit on this host, not a T4 measurement.

All 33,075 risk timestamp/value pairs and every non-accident event are exactly equal to the
pre-correction full run. Accident segments exactly match the separately recorded cached-rule
comparison: fourteen candidates become nine; only the reviewed parked-car/pedestrian pair is
labelled a false positive. The nine remaining segments are not visually confirmed collisions.
This checks the intended change, not whole-dataset accuracy or a second identical-source
full-set determinism run. C3905's complete event/risk output also equals its earlier repeats.

The manifest was recorded immediately afterwards in the same CUDA environment. Its input
checksums match the baseline, and all recorded source/configuration hashes match the current
worktree. Prediction SHA-256:
`0dc5d20efae4991999e142486820a500ad3c798a9927afa4593643f40f41404d`.

## Input and execution

- Input: `data/samples/C3905.MP4`, 2,348,992,759 bytes, 3840×2160, 30000/1001 fps,
  3,825 frames, 127.6275 seconds.
- Input SHA-256: `e99072464be42627d7cc83b5a7f6c5149352326e95503338ac289fbb6b537aad`.
- Host: RTX 3050 Laptop GPU, 4 GiB VRAM; Intel Core i5-11400H; approximately 7.4 GiB RAM.
  Other desktop applications were running and the host used swap during inference.
  The complete-set run also overlapped lightweight tests and short CPU/browser demo checks;
  these are observed local wall-clock timings, not isolated benchmark measurements.
- Environment: the isolated Python 3.11.14 environment installed from the root CUDA
  requirements for the earlier GPU checks; torch 2.6.0+cu124, torchvision 0.21.0+cu124.
- Profile: default `auto` selected `gpu`, unchanged YOLO11m/960/FP16/batch 16 for Part A
  and YOLO11s/640 for Part B. No source/configuration or sampling changes were made for this run.
- The unchanged official harness ran in a network namespace with no internet access.
  Developer perception caching and device/profile overrides were unset.

```bash
unshare --user --map-root-user --net \
  env -u TRAFFICWATCH_CACHE -u TRAFFICWATCH_PROFILE -u TRAFFICWATCH_DEVICE \
  "$GPU_CHECK_PYTHON" -u run_submission.py \
  --videos data/samples/C3905.MP4 \
  --out reports/original_gpu/predictions-first.json --team trafficwatch
```

`GPU_CHECK_PYTHON` is the CUDA environment's Python executable. Linux user/network
namespaces are a verification mechanism, not an additional requirement of the solution.

## Baseline: two independent C3905 runs

The repeat used the same command in a fresh process, with only the output filename changed
to `predictions-repeat.json`.

| Run | Part A | Part B | Combined | Allowed | Events | Risk scores |
|---|---:|---:|---:|---:|---:|---:|
| First | 101.5 s | 84.8 s | 186.3 s | 382.9 s | 20 | 3,825 |
| Repeat | 90.6 s | 79.8 s | 170.5 s | 382.9 s | 20 | 3,825 |

The official harness logged no errors in either run; `evaluate.py --validate-only` reported
zero errors and zero warnings. Combined runtime was 1.46× and 1.34× video duration,
below the 3× limit on this host.
There is one risk score for every frame, with values ranging from 0.0100 to 0.9167.

The `videos` objects in both JSON files are exactly equal, including every event boundary
and risk timestamp/value. Their canonical JSON SHA-256 (sorted keys, compact separators) is
`3f23492d33c628fa22d8595503851665c425b5dc1fcd1d71c73913ed3e8f1cab`.
The complete files differ because their wall-clock timing logs differ.

`run.json` and `run-repeat.json` bind each output to the original input, source and
configuration hashes, and key package versions. The recorded source/configuration hashes
were checked against the worktree after the repeat. No claim about event-detection accuracy
follows from a valid format, determinism or the number of predicted events.

## Baseline: complete-set run

The same offline harness command was run with `--videos data/samples/` and
`--out reports/original_gpu/predictions-all.json`. No source/configuration, GPU-profile or
frame-sampling changes were made. `run-all.json` records every input checksum, metadata,
package version and source/configuration checksum.

| Input | Duration | Part A | Part B | Combined | Allowed | Events | Risk scores |
|---|---:|---:|---:|---:|---:|---:|---:|
| C3896 | 340.34 s | 222.3 s | 217.8 s | 440.2 s | 1021.0 s | 46 | 10,200 |
| C3897 | 317.82 s | 215.4 s | 200.3 s | 415.7 s | 953.5 s | 56 | 9,525 |
| C3902 | 317.82 s | 209.8 s | 212.5 s | 422.3 s | 953.5 s | 48 | 9,525 |
| C3905 | 127.63 s | 85.4 s | 73.6 s | 159.0 s | 382.9 s | 20 | 3,825 |

All four logs have no errors. The official validator reports **4 videos, 170 events,
zero errors and zero warnings**. All 33,075 risk timestamps match the input frame indices,
all scores are in [0, 1], and every event lies within its input duration. Runtime is
1.246–1.329× video duration, below the 3× limit for every input on this host.

The C3905 event/risk output is exactly equal to both independent runs, including after the
other three videos have been processed in the same Python process. This checks that earlier
videos did not alter that clip's results; it is not a second full-set determinism run.

Complete prediction file SHA-256:
`4c1b4eac12615298640f0077696f3bd8f16c95b3ec7610a7b4d3c4ec55018509`.

The output contains 14 `accident` candidates across C3896/C3897/C3902. These are model
predictions, **not visually confirmed collisions** or an accuracy measurement; inspect their
overlays and temporal boundaries before making quality claims.

## Remaining scope

These completed runs are not a T4 benchmark, a clean-container test or a measurement against
human ground truth. An identical-source full-set repeat, public hosting and confirmed team
profiles are still required before final handoff. A repeat overlapping rendering was deliberately
stopped without a result when local RAM became constrained; it is not counted as evidence.
The subsequent serialized repeat logged successful processing of C3896, C3897 and C3902,
but its process/session disappeared across a host restart before the final JSON was saved.
Those progress messages are not an event/risk equality check. No complete repeat artefact
was produced; this gate remains open and the validated first run is preserved unchanged.
