# Submission readiness

**Prepared locally; not ready for final public handoff.** The repository remains private,
`main` is unchanged, and no final tag, public website/demo or portal submission is authorised.
This checklist follows the organisers' task; passing tests is not proof of detection accuracy.

Official participant-portal deadline: **27 September 2026, 23:59 Asia/Tashkent (UTC+5)**.
The captain's three-hour working window is separate from that deadline.
Registered team: **Zero Context**; project: **TrafficWatch**.

## Current evidence

The registered-layout / hue-aware model revision has completed two offline passes of all
four original 4K videos, one fresh official-harness process per video in each pass.
Every one of **163 event segments and 33,075 per-frame risk timestamp/value pairs matches
exactly**. The unchanged official validator reports zero errors and zero warnings.

- First-pass Part A + B: **452.1 / 436.4 / 449.7 / 158.0 seconds**, or 1.24–1.41× duration.
- Repeat: **574.4 / 434.5 / 516.6 / 203.0 seconds**, or 1.37–1.69×.
- All runs respect their 3× budgets on the RTX 3050 Laptop; **T4 remains unverified**.
- `predictions_samples.json` and `reports/submission_run.json` equal the calibrated first
  pass; website media, EDA, event timelines and risk charts now match that same run.
- The complete old asset/output set is recoverable from
  `.cache/before-calibrated-promotion.xwkmxG/`; original videos were not changed.
- A further standard-command run of the entire folder in one process also passed:
  **487.2 / 463.4 / 470.0 / 174.9 seconds**, with exact event/risk equality and matching
  provenance. All twelve current-model video runs satisfy their local runtime budgets.
- The local suite has 102 passing tests after dependency pinning and upload-guard coverage;
  Ruff passes. The 32 warnings are two future Gradio deprecations repeated across 16 demo tests.
  The post-promotion package audit reports **79 passes / 3 warnings / 0 failures**.
- Current-version desktop/mobile site checks pass for all playback/seek paths, 20 EDA images,
  report images and team content; no page errors or horizontal overflow were found.
  The delayed-selection regression also passes. The current prepared demo passed offline
  direct calls and actual two-minute desktop/mobile uploads; public URL and public upload
  checks remain deliberately pending.

See [full run evidence](../reports/original_gpu/calibrated/),
[scoped signal review](../reports/scene_review/) and the
[executed audit notebook](../notebooks/evidence_audit.ipynb).
Historical runs remain in [original GPU reports](../reports/original_gpu/),
[preview reports](../reports/preview_cpu/) and [development history](development-history.md).

## Requirement-by-requirement checklist

| Requirement | Evidence | Remaining work or limitation |
|---|---|---|
| Root interface and 14 official class IDs | `solution.py`; package audit | Interface coverage does not imply class accuracy |
| Unchanged organiser harness/evaluator | Both starter SHA-256 values match | Keep unchanged |
| Valid Part A segments | Official format, bounds and rule tests pass | Independent event identity/boundary labels are missing |
| Causal Part B, one score per frame | Prefix-causality/no-video-opening tests; 33,075 verified frame timestamps | No empirical risk calibration or measured anticipation score |
| Local open weights ≤ 5 GB | Three YOLO11 hashes pass; 62.6 MiB | Preserve weights/licences in final package |
| Offline inference without downloads | All twelve current-model original-video runs used loopback-only network namespaces | Preserve local-weight behaviour |
| Two-command installation/run | Fresh Python 3.11 CUDA environment used for original runs | Fresh OS/container and target T4 still unverified |
| Runtime ≤ 3× input duration | All twelve completed current-model video runs pass locally | Same-host observations, not an isolated T4 benchmark |
| Same-machine determinism | Exact event/risk equality across all four originals | Reverify after any source/config/weight change |
| All sample predictions and provenance | Current root output bound to source/config/input hashes and package versions | Keep output and manifest together |
| Team names, roles, contributions and links | Three official names; captain-confirmed equal core credit for Samandar/Doniyorbek and polish/debugging for Shohruxxo’ja | Remaining profile links and previous projects are deferred by the user |
| Approach diagram and technical report | Learned/rule-based paths, failure cases and scoped visual evidence | Final review against the released revision |
| EDA for every sample | Four original GPU entries and 20 JPEGs; metadata/profile checks pass | Repeat rendering checks at eventual public URL |
| Annotated playback, timelines and risk | Four full-decode H.264 files; all events/curves match root output; current desktop/mobile browser checks pass | Verify again at the eventual public deployment |
| Live upload demo | Self-contained current-source package passed offline 6 s / 120 s clips, actual desktop/mobile uploads, progress, playback, chart/table/download and over-length rejection | Publish only when authorised, then verify a real public upload |
| Public repo, website, weights, predictions | Links and Pages workflow prepared | Publication intentionally deferred; private authenticated access is not public availability |
| Final tag or full commit hash | Reviewable feature branch; original history preserved | Final immutable reference only after release gates pass |
| Availability through judging | Deployment runbook present | Confirm demo host/account and availability arrangements |

Warnings deliberately make `python tools/check_submission.py --strict` fail. The current
three warnings concern incomplete profile fields, an absent live-demo URL and unchecked
public links. A non-strict green audit is not submission completeness.

## What the model evidence does and does not support

**Share the measured engineering evidence with caveats.** The executed notebook checks
expected video/frame keys, uniqueness, bounds, finite scores, runtime denominators,
input/source identities, repeat equality and all 46 selected lamp observations.
Its 11/46 → 27/46 → 45/46 lamp comparison is a tuning review, not held-out accuracy.
Unknown readings remain in the denominator; the final step changes brightness and hue
together. Two heads in one frame are correlated. No amber/transition timing is validated.

- `near_miss`, `fire_smoke` and generic static-obstacle detection remain disabled.
- No verified prohibited U-turn zones, prohibited turns or solid-line annotations are supplied.
- Nine accident candidates remain unconfirmed, including C3902 at 1.47–3.47 s.
  See [accident review](../reports/accident_review/); proximity alone is not proof of contact.
- Event counts changing from 165 to 163 do not establish better precision, recall or F1.
- No complete independently labelled event dev set or empirical probability calibration exists.
- Small camera shifts are addressed in Part A; continuous motion/new viewpoints remain limitations.
- The host slept from 13:13 to 14:53 during the repeat. The same process resumed successfully;
  the harness's monotonic timer excludes suspended time on this host. Civil elapsed time differs.

Dev labels, ablations and calibration are encouraged quality work, not extra mandatory
artefacts. Their absence limits accuracy claims separately from incomplete publication/team items.

## Packaging and local verification notes

All original videos are already on the second SSD in ignored `data/samples/`; their byte sizes,
4K resolution, 30000/1001 fps, frame counts and distinct SHA-256 identities are recorded.
Incomplete downloads and earlier preview inputs were preserved, not deleted.

All four website videos use H.264/yuv420p, 960×636 (including timeline), 14.985 fps,
fast-start indexing and full decoding. Their frame counts are 5,100 / 4,763 / 4,763 / 1,913;
durations stay within one sampled-frame period and each file is below 100 MB.
The exporter used a two-frame read-ahead queue to limit rendering memory; submitted inference
and sampled frame content were unchanged. A C3897 export-order guard was corrected by sorting
complete event tuples, not by changing or dropping predictions.

The demo's temporary rendering workspace is removed after successful cache handoff or failure.
Managed outputs expire on a six-hour TTL, checked hourly. Three lifecycle tests cover success,
scheduled expiry and error cleanup; 13 further tests cover invalid inputs, size/duration limits,
the duration tolerance and uppercase MP4 extensions. Earlier-version real browser/offline checks remain historical
evidence; they are not substituted for the current-version or public checks.

The current package's 34 files are hash-bound in [demo verification](../reports/demo_verification/).
Its real two-minute 720p/30 fps input produced 17 candidates and 720 sampled risk points:
about 47 s offline, 49 s in the desktop browser and 48 s in the mobile browser. Full video
decoding, managed-cache handoff, visible progress, playback/seeking, Plotly, table and JSON
download passed. A 124-second clip is rejected; the error toast was visually inspected after
its fade-in. The UI states the lightweight profile difference and uncalibrated-risk limits.
These checks are local, not evidence of public availability or model accuracy.

CI uses pinned action commits and read-only repository permissions. [Run 36314791805](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36314791805)
passed on promoted commit `d0583f7`: 102 tests, Ruff, official format, weight checksums,
79 package checks and clean-kernel notebook execution. Later commits must be checked again.
The subsequent [run 36319693756](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36319693756)
also passed on `a63bb081b4f37608853cac6416fc423d5b797e90`; its log confirms the same 102 tests,
79 package passes / 3 warnings / 0 failures and notebook execution.
A clean export of `d0583f7`'s 177 tracked files also passes the same package audit;
this export is not a fresh OS/container or a separate GPU inference environment.
No inference cache, original/preview inputs, virtual environment or private registration
contacts are intended for Git. The optional notebook environment is not a runtime dependency.

## External prerequisites and final release gates

1. Add the deferred GitHub/LinkedIn/portfolio/previous-project details without inventing them.
   The user has confirmed names and contributions; these are already in README/site.
2. Supply three T-shirt sizes in portal order: Samandar, Shohruxxo’ja, Doniyorbek.
3. The captain confirms that neither he nor the team has an existing Space/server/host.
   Choose and provision an approved demo host/account and confirm operational availability.
   Do not purchase hosting or
   substitute a different execution platform without approval.
4. Wait for explicit publication confirmation before making the repository public, merging
   to `main`, enabling Pages, publishing the demo or creating a final release tag.
5. After authorised publication, run strict online/package checks, desktop/mobile website
   checks and a real public demo upload. Record the exact public commit/tag and URLs.
6. Final portal submission is a separate action; no form has been submitted.

The [publication runbook](deployment.md) lists the portal fields, deployment steps and final
public-upload checklist. Preparing files and pushing to the private feature branch is not
public release or acceptance by the organisers.
