# Development history

Branch: **`feat/trafficwatch-submission`**, based on `main` at `712d80a`.
The original `project init` and `gitignore added` commits are preserved.
The subsequent work is grouped into the reviewable stages below; this is a reading order,
not a claim that every experiment was originally performed in that order.

## Review the work stage by stage

| Stage | Commit | What changed | Where to look |
|---|---|---|---|
| 01 · Repository structure | [b5dc9db](https://github.com/samanwirst/hackaton_wiut_2026/commit/b5dc9db4e2777c1e83ee3f18134d339330a9caf3) | Separate runtime profiles; organise local datasets and annotation tools; keep the official root interface intact | `requirements/`, `data/`, `tools/annotation/`, `pyproject.toml`, Docker context |
| 02 · Inference contract | [3da079c](https://github.com/samanwirst/hackaton_wiut_2026/commit/3da079c0c42c2639bd39f185c2fc7af3c6476728) | Match official class definitions, require local weights and test past-only risk behaviour | `src/trafficwatch/`, rule/signal/risk/offline tests |
| 03 · Accident evidence | [53dc142](https://github.com/samanwirst/hackaton_wiut_2026/commit/53dc14283e9aa133c61b449a4dad18d730ff7528) | Correct parked-car/pedestrian and incomplete-observation false positives; retain positive regression cases | `events/interactions.py`, `tests/test_accident_evidence.py`, `reports/accident_review/` |
| 04 · Reproduction tools | [9b1e3c0](https://github.com/samanwirst/hackaton_wiut_2026/commit/9b1e3c0687a857943c73fb289c58ad4ffbb6bb11) | Add input/source provenance, original-versus-preview exports, package audits and range-aware local serving | `tools/record_run.py`, `tools/check_submission.py`, EDA/export tools |
| 05 · Upload demo | [3659b89](https://github.com/samanwirst/hackaton_wiut_2026/commit/3659b89d5b558d930f201f5ef5fc009a2aa174d8) | Package the CPU app with progress, upload limits, managed output caches and cleanup tests | `demo/`, `tests/test_demo.py` |
| 06 · Original-video results | [9f3bd38](https://github.com/samanwirst/hackaton_wiut_2026/commit/9f3bd38c1547d67d733bf2b2eeb7acda22db70ec) | Include the verified four-original run, weights, matching annotated videos and EDA; preserve earlier experiments separately | `predictions_samples.json`, `reports/`, `website/data/`, `website/media/` |
| 07 · Interactive website | [e0818cf](https://github.com/samanwirst/hackaton_wiut_2026/commit/e0818cf510edbd20bff4fa317ec7676ebed41a9c) | Present the pipeline, responsive charts, seekable results and honest failures; protect against stale video-selection responses | `website/index.html`, `website/assets/`, `website/data/site.json` |
| 08 · Continuous checks | [1d87d08](https://github.com/samanwirst/hackaton_wiut_2026/commit/1d87d08b88af306aa0f2c9abbb0635c9717ceb1b) | Validate tests, format, weights and provenance; pin deployment actions and scope permissions | `.github/workflows/` |
| 09 · Handoff documentation | [e37d00e](https://github.com/samanwirst/hackaton_wiut_2026/commit/e37d00eb6643e854719c7a700623b37ba4d29a08) | Explain reproduction, measured evidence, publication steps and remaining gates; make generated artefacts easier to review | [README](../README.md), [readiness](submission-readiness.md), [deployment](deployment.md), `.gitattributes` |

Each implementation commit has a focused subject and a body explaining its purpose. No
existing history is rewritten, no artificial dates are used, and `main` is not merged or
force-pushed as part of preparing this branch.

Generated predictions, run manifests, EDA and playback assets remain in Git. `.gitattributes`
marks them as generated so GitHub can collapse them by default; reviewers can expand them
when checking evidence. Source code, configuration, manual review notes and documentation
remain ordinary diffs. This follows
[GitHub's generated-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github).

## Evidence available at the branch checkpoint

- **72 tests pass**, including offline-weight, causal-risk, event-rule, accident-evidence,
  demo-lifecycle and export/provenance checks. Six warnings concern future Gradio 6 deprecations;
  the package currently pins Gradio 5.50.0.
- Ruff, JavaScript syntax, `actionlint` and `git diff --check` pass locally.
- The unchanged official evaluator accepts **4 videos / 165 events**, with no format errors
  or warnings. The package audit reports **77 passes / 3 warnings / 0 failures**.
- All four original inputs have matching EDA and annotated results. Browser checks cover
  desktop/mobile playback, event/risk seeking and the delayed-selection regression.
- Full-run measurements and source/input hashes are in [the original-GPU report](../reports/original_gpu/README.md).

These were local checks at the nine-stage checkpoint; the remote CI result is recorded below.
They do not establish public hosting or hidden-set accuracy. The complete repeat was interrupted
by a host restart before its final output was written, so full-set determinism was still an open
verification gate at that checkpoint.

## Post-push verification

The [first GitHub CI run](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36298715111)
installed the dependencies and passed Ruff, but reported 71 passing tests and one failed
synthetic learned-direction test. The failure was reproduced locally by selecting Nehalem,
Sandybridge and Haswell OpenBLAS kernels; package versions were the same.

The fixture used exactly horizontal tracks on an angular-bin boundary. Tiny signed vertical
velocities from smoothing changed the normal-traffic heading bin from 0 to 11, so evidence in
the bin opposite the rogue vehicle fell from about 0.4945 to 0.2473, just below the 0.25 rule
threshold. The corrected fixture uses slightly sloped parallel lanes, retains the exact
one-event/track-id/duration assertions, and adds a legal vehicle in the opposite lane. It does
not change inference code, thresholds, model weights or the submitted sample outputs.
The complete 72-test suite passes locally with automatic kernel selection and separately with
each of Nehalem, Sandybridge and Haswell. The correction is preserved in
[e02faf2](https://github.com/samanwirst/hackaton_wiut_2026/commit/e02faf2d4a327384c5445363d6cfa9114279e154).
The [subsequent GitHub CI run](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36299069627)
**completed successfully** on Ubuntu 24.04 with Python 3.11: all 72 tests passed, Ruff passed,
the official validator accepted all four videos / 165 events without errors or warnings,
all three weight checksums matched, and the package audit reported 77 passes / 3 warnings /
0 failures. This is remote CI evidence, not a GPU benchmark or a public deployment.
Follow the current
[branch checks](https://github.com/samanwirst/hackaton_wiut_2026/actions?query=branch%3Afeat%2Ftrafficwatch-submission)
for later verification results.

This follow-up is a new commit rather than a rewrite of the nine-stage checkpoint. It makes
the scenario test portable; it does not claim that angular-bin boundary decisions are
identical across machines. The required same-machine full-original repeat is separate.

## Full-original reproducibility follow-up

A checkpointed offline repeat subsequently completed all four originals with one fresh
official-harness process per video. Every event and all 33,075 risk timestamp/value pairs
are exactly equal to the reviewed original batch. Individual outputs, input/source manifests,
the aggregate and equality hashes are preserved in [the original-GPU report](../reports/original_gpu/README.md).
All four runs stayed below their time budgets on the local GPU. This confirms same-host
reproducibility for that model revision, not accuracy, T4 runtime or a later revision.

## Registration, team and evidence follow-up

These are new commits after the initial nine-stage checkpoint, not rewritten history:

| Stage | Commit | Change and evidence |
|---|---|---|
| 10 · Camera alignment and dim lamps | [08d2336](https://github.com/samanwirst/hackaton_wiut_2026/commit/08d2336bd235c9f69f6c999825f401bd5328a243) | SIFT/RANSAC layout registration and hue-aware lamp reading; registration rejection/determinism and pixel regressions |
| 11 · Unresolved candidate review | [b4cc157](https://github.com/samanwirst/hackaton_wiut_2026/commit/b4cc1573990432c461fac5dab6cbba96263a2364) | Preserve visual evidence and explicitly leave the nine remaining accident candidates unconfirmed |
| 12 · Verified dependencies | [971cfca](https://github.com/samanwirst/hackaton_wiut_2026/commit/971cfcaea1178b6af4878a0a18927f6e998f7111) | Pin the numerical/tracking/demo versions used in actual checks |
| 13 · Full-original first pass and repeat | [c75a192](https://github.com/samanwirst/hackaton_wiut_2026/commit/c75a192e5de91a06e992f115b74eb94ce169b690), [3e82098](https://github.com/samanwirst/hackaton_wiut_2026/commit/3e820989316fc6a55ddc7fdece4e70fa54f77ead) | Eight offline original-video runs; exact equality of 163 events and 33,075 per-frame risk outputs |
| 14 · Confirmed Zero Context roster | [4084d03](https://github.com/samanwirst/hackaton_wiut_2026/commit/4084d034c91589ebafc688fe983d8e3cb66d8cdd) | Official participant names, captain-confirmed equal core contribution credit and repeatable website QA |
| 15 · Inspectable analytical evidence | [8d86392](https://github.com/samanwirst/hackaton_wiut_2026/commit/8d86392daf7dd4873b40fbe1dc1118942f2910b0) | Four signal contact sheets, all 46 tuning observations and an executed notebook; clearly no held-out accuracy claim |
| 16 · Upload boundary tests | [346dc66](https://github.com/samanwirst/hackaton_wiut_2026/commit/346dc666976f19642aa39ab965ab06eb7fe18b3a) | Invalid files, size/duration rejection, accepted boundary/tolerance and uppercase MP4; complete suite reaches 102 passing tests |
| 17 · Coherent current results | [d0583f7](https://github.com/samanwirst/hackaton_wiut_2026/commit/d0583f7e8d8770f444d535829eb3c052144c250d) | Promote root output/provenance with matching media/EDA; browser-check desktop/mobile and delayed-selection behaviour; retain old evidence separately |

The current package audit has 79 passes, 3 readiness warnings and no failures. The
website's runtime tile spans both completed passes (1.24–1.69× duration), rather than
showing only the faster one. The default whole-folder command subsequently matched all
outputs exactly (1.37–1.48× duration), with unchanged input/source/configuration/package
provenance; the executed notebook now checks this third pass too.

Remote [CI run 36314791805](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36314791805)
passed on `d0583f7`: 102 tests, Ruff, official prediction format, all weight checksums,
79 package checks and top-to-bottom notebook execution. A clean export of the 177 tracked
files also passed the package audit. This is not a target-GPU benchmark or public deployment.
Publication remains a separate final action.

## Work still outside the current checkpoint

Public repository/website/demo availability, a real upload to the public demo, remaining
profile/previous-project links, labelled accuracy and target-hardware/clean-host
verification remain tracked in [submission readiness](submission-readiness.md).
The user deferred team details until the final stage. Do not replace missing information with
invented profiles or convert candidate-review notes into a claimed accuracy score.
The user also explicitly deferred public publication: keep the repository private and prepare
changes in this branch. Making the repository public, merging to `main` and enabling the public
website/demo are final actions requiring a later confirmation.

Later verification or publication work should be added as new focused commits so its evidence
and remaining limitations stay visible in the branch history.
