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

Root predictions and website media still belong to the previous revision. This
directory deliberately preserves the new first-pass evidence separately until the
matching media and repeat are verified. No public release or final submission is
authorised by this checkpoint.
