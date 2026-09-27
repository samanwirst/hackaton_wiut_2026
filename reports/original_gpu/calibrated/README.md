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

An additional default official-command check (the whole folder in one fresh process)
is running separately; it is not yet counted as a pass here. No public release or
final submission is authorised by this checkpoint.
