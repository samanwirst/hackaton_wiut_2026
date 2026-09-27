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

These are local checks, not evidence that remote CI, public hosting or hidden-set accuracy
has been verified. The complete repeat was interrupted by a host restart before its final
output was written, so full-set determinism remains an open verification gate.

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
each of Nehalem, Sandybridge and Haswell. Follow the current
[branch checks](https://github.com/samanwirst/hackaton_wiut_2026/actions?query=branch%3Afeat%2Ftrafficwatch-submission)
for the remote verification results.

This follow-up is a new commit rather than a rewrite of the nine-stage checkpoint. It makes
the scenario test portable; it does not claim that angular-bin boundary decisions are
identical across machines. The required same-machine full-original repeat remains separate.

## Work still outside this checkpoint

Public repository/website/demo availability, a real upload to the public demo, the final
three-person team details, the complete identical-source repeat and target-hardware/clean-host
verification remain tracked in [submission readiness](submission-readiness.md).
The user deferred team details until the final stage. Do not replace missing information with
invented profiles or convert candidate-review notes into a claimed accuracy score.

Later verification or publication work should be added as new focused commits so its evidence
and remaining limitations stay visible in the branch history.
