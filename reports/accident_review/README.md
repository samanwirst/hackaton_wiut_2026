# Accident-candidate review and regression correction

The baseline full original GPU run reported 14 accident candidates. This review uses only
the organiser-provided samples; its structured notes are in
[`candidate_reviews.json`](../../data/labels/candidate_reviews.json).
They are **not exhaustive ground truth** and must not be used to report F1.

A [later scoped review of the remaining candidates](followup.md) records queueing,
perspective overlap and occlusion cases without promoting them to confirmed collisions
or to exhaustive negative labels.

## Visual evidence

- C3896, 216.02–217.62 s, tracks 1013/1163: the car remains parked while pedestrians
  stand/walk nearby. This pair is a false positive in the reviewed sequence.
  [Contact sheet, 214–222 s](C3896_214-222.jpg).
- C3896, 274.74–276.01 s, tracks 1248/1501: dense traffic closes up and stops;
  no clear impact is visible in the sampled crop. Keep this candidate **unconfirmed**,
  rather than treating ordinary proximity as proof of a crash.
  [Contact sheet, 272–280 s](C3896_272-280.jpg).

The sheets sample at 2 fps. Their timestamp labels start at zero relative to each reviewed
window, not the full video. Crops and input/prediction checksums are recorded in the JSON.
Sampling can miss brief contact; a full-rate review is still needed for ambiguous cases.
The website technical report includes the first contact sheet and a scoped explanation of the
failure and correction; its copied image is `website/data/reviews/C3896_214-222.jpg`.

## General rule corrections

No filenames, timestamps or scene locations are used in the rule changes.

1. A pedestrian's movement next to a stationary vehicle is no longer sufficient: a vehicle
   in that pair must have been moving before the proposed contact, using the existing
   stationary-speed threshold.
2. The settling check requires a complete half-second window, not a truncated track tail.
3. A missing joint observation after settling is not accepted as evidence of remaining
   together; a track disappearing can be ordinary occlusion or an identity change.

Seven regression tests cover these cases and retain moving-car/person and two-wheeler/parked-car
collisions. Before the correction three of the tests failed; afterwards all seven pass, along
with the existing head-on and rear-end collision tests. The complete suite has 72 passing tests.

Re-evaluating the unchanged cached GPU tracks gives the following comparison; full intervals
and rule/prediction hashes are in [`rule_comparison.json`](rule_comparison.json).

| Original | Baseline accident segments | Revised accident segments |
|---|---:|---:|
| C3896 | 6 | 2 |
| C3897 | 4 | 3 |
| C3902 | 4 | 4 |
| C3905 | 0 | 0 |

All other classes' segments are unchanged. The first C3902 accident candidate starts at 1.47 s
instead of 1.20 s; counts alone do not show that boundary change. This is an **event-rule
comparison**, not a new timed harness run or an accuracy score; only the specifically reviewed
pair above is labelled a false positive. The remaining nine accident segments are unconfirmed.

The trade-off is deliberate but limited: crashes hidden immediately by occlusion, very short
track tails, or pedestrian-only contact with a stationary object may be missed. The rule is
still a heuristic, not visual confirmation of physical impact.

## Revalidation

The original `reports/original_gpu/predictions-all.json` and its manifest are preserved as
the pre-correction baseline. A fresh offline run of the unchanged official harness has now
completed over all four originals: `predictions-reviewed.json` passes official validation with
165 events, 33,075 per-frame risk scores and no errors or warnings. `run-reviewed.json` binds
the output to the current source, configuration and original inputs.

The full harness's accident segments exactly match the cached comparison above. Every other
event and the complete risk curves are unchanged from the baseline. Runtime is 1.186–1.265×
input duration on the local RTX 3050 Laptop, below the 3× limit; T4 hardware is not verified.
Matching annotated website exports have passed metadata, frame-count, codec and event/risk
consistency checks. The reviewed output, its manifest and all four original website results
have now been promoted together; the pre-correction baseline remains separate.
