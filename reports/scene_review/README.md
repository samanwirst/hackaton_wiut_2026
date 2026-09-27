# Scene registration and lamp-reader development review

## Finding and scope

On 27 September 2026, the revised reader matched **45 of 46 selected lamp states**,
compared with 11/46 for the original fixed-layout brightness reader. These are
AI-assisted **tuning observations**, not held-out accuracy, event labels or F1.
Both visible heads were reviewed in 23 frames across the four organiser originals.
The two heads in a frame are correlated; 46 is not a count of independent trials.

| Reader variant | Matches / all selected lamps | Agreement | Unknown, included in denominator |
|---|---:|---:|---:|
| Fixed layout, brightness threshold V ≥ 150 | 11 / 46 | 23.9% | 29 |
| Registered layout, same brightness reader | 27 / 46 | 58.7% | 18 |
| Registered layout, hue-aware reader (V ≥ 70) | 45 / 46 | 97.8% | 1 |

The final step changes both the brightness threshold and hue filtering; this table
does **not** isolate their separate effects. No detector weights were changed.
The selected observations contain 26 red and 20 green states. C3896, C3897 and
C3902 contribute 12 observations each; C3905 contributes 10.

The remaining mismatch is C3896, frame 0, `ped_diag`: the crop shows red but the
reader returns `unknown`. All four saved contact sheets were visually inspected.
Registration reduces the misalignment from small framing changes; the lower
threshold admits dim daylight lamps, while the expected-hue gate rejects bright
background pixels. The sample supports this narrow development finding only.

## Evidence and reproduction

- [`signal_review.json`](signal_review.json): every `(video, frame, head)` observation,
  registration diagnostics and aggregate counts.
- Contact sheets: [C3896](C3896_signals.png), [C3897](C3897_signals.png),
  [C3902](C3902_signals.png), [C3905](C3905_signals.png).
- Input review: [`signal_spotchecks.json`](../../data/labels/signal_spotchecks.json).
- Executed checks: [`evidence_audit.ipynb`](../../notebooks/evidence_audit.ipynb).
- Model hashes and complete offline runs: [`calibrated/`](../original_gpu/calibrated/).

```bash
python tools/review_signals.py --videos data/samples --out reports/scene_review
```

The notebook reconciles all expected keys, uniqueness, states, decoded frame times,
denominators and saved counts. No selected observation is dropped. Its separate
run checks verify exact repeat equality of 163 event segments and 33,075 per-frame
risk values, not their correctness against ground truth.

## Confidence and remaining work

**Share with caveats:** the counts and provenance are reproducible, but the same
observations informed the fix. Selection bias is material if these percentages
are presented as general accuracy. No amber/flashing states, transitions, hidden
signal phases or event boundaries are validated here. Continuous camera movement,
new views and occlusions remain limitations.

Event counts changed from 165 to 163, including changes to red-light, stop-line,
queue-related and pedestrian events. Lower counts are not automatically better.
Nine accident candidates remain unconfirmed. Add independent event annotations
and transition checks before claiming improvements in the official metric; measure
risk calibration and runtime on the organisers' target hardware separately.
