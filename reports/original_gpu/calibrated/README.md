# Registered scene / hue-aware signal verification

The first complete offline pass of commit `08d2336` is preserved in `first/`.
The unchanged official harness ran once per original in a fresh process, serially,
with only the loopback network interface. No inference cache, profile or device
override was supplied. `frozen.json` records the inference inputs; `first/run.json`
binds the aggregate predictions to source, configuration, weights and originals.

| Original | Events | Per-frame risk scores | Part A + B (s) | Budget (s) |
|---|---:|---:|---:|---:|
| C3896 | 41 | 10,200 | 452.1 | 1,021.0 |
| C3897 | 54 | 9,525 | 436.4 | 953.5 |
| C3902 | 48 | 9,525 | 449.7 | 953.5 |
| C3905 | 20 | 3,825 | 158.0 | 382.9 |

The official validator reports 163 events, zero errors and zero warnings. All
33,075 causal risk outputs match the preceding model revision exactly. These
counts and the observed RTX 3050 Laptop timings do not measure accuracy or prove
performance on the organisers' T4 hardware.

## Complete repeat

The second complete pass is preserved in `repeat/`. `equality.json` confirms exact
equality of all 163 event segments and all 33,075 risk timestamp/value pairs, with
unchanged source, configuration, inputs and package versions. Repeat wall-clock
times measured by the official harness were 574.4 / 434.5 / 516.6 / 203.0 seconds;
each remained below its video's budget. Log timings are deliberately not compared
for equality. Neither pass used a runtime inference cache.

The host suspended from 13:13:05 to 14:53:18 Asia/Tashkent on 27 September 2026
during C3897 (`systemd-suspend.service`). The same process resumed and completed
successfully without restarting. The harness uses `time.perf_counter()`, which
does not count suspended time on this host; its measured runtime is not elapsed
civil time across that sleep interval.

## Promotion status

The first export guard stopped at C3897 because it compared raw list order: the
postprocessor sorts by `(start, label)`, whereas the unchanged official harness
sorts `[start, end, label]`. All 54 complete event tuples were identical, including
boundaries and multiplicity. Canonical sorting resolved the comparison without
changing inference, thresholds or predictions. C3896's completed export was kept;
export resumed from C3897. This is an export-check correction, not a model rerun.

The first pass is now promoted to root predictions and the run manifest, together
with matching original EDA and all four annotated videos. Complete tuple/risk
comparison, input/profile metadata, 20 images, H.264/yuv420p encoding, durations,
fast-start indexes and full video decoding passed before promotion. The old complete
set is preserved locally at `.cache/before-calibrated-promotion.xwkmxG/`.

The [executed notebook](../../../notebooks/evidence_audit.ipynb) independently checks
coverage, hashes, repeats, counts and runtime denominators. First-pass runtime is
1.24–1.41× clip duration; repeat runtime is 1.37–1.69×. The separate
[lamp review](../../scene_review/) covers selected tuning frames, not held-out accuracy.

## Default whole-folder command

An additional run in `batch/` processed all four originals in **one fresh process**:

```bash
python run_submission.py --videos data/samples --out predictions.json
```

It ran in a loopback-only network namespace, with no runtime cache, profile or
device overrides and unchanged source/configuration/weights. The default non-scoring
team metadata differs from the first pass; every event and risk timestamp/value matches
exactly. `batch/comparison.json` binds both output hashes. Input hashes, Python,
packages, profile and source/configuration provenance also match the first pass.

| Original | Whole-folder Part A + B | Runtime / duration | Budget |
|---|---:|---:|---:|
| C3896 | 487.2 s | 1.43× | 1,021.0 s |
| C3897 | 463.4 s | 1.46× | 953.5 s |
| C3902 | 470.0 s | 1.48× | 953.5 s |
| C3905 | 174.9 s | 1.37× | 382.9 s |

The official validator again reports 163 events, zero errors and zero warnings.
These are observed desktop-host timings: short static-browser/unit checks and Git
packaging overlapped this pass, but no second inference/export job did. This is not
an isolated benchmark or a T4 result. The executed notebook checks this batch too.
No public release or final submission is authorised by this checkpoint.
