# Submission readiness

The submission is **not ready for a final tag or handoff**. This checklist follows the
organisers' task, not just the checks currently implemented in the repository.

**Current model revision:** the accident-evidence correction has passed a fresh complete offline
GPU run. `reports/original_gpu/predictions-reviewed.json` and `run-reviewed.json` are validated:
all four originals, 165 events and 33,075 risk scores, with current source/input hashes.
The reviewed output and manifest are now promoted to `predictions_samples.json` and
`reports/submission_run.json`, together with matching original EDA and all four annotated
website results. The previous preview assets were backed up first. Publication, team profiles
and the remaining verification gates below still prevent final handoff.
See `reports/accident_review/` for scoped visual evidence.

## Requirements and evidence

| Requirement | Current evidence | Remaining verification or work |
|---|---|---|
| Root interface and official class IDs | `solution.py`; package audit checks the 14 IDs | Hidden-set quality is not established by exposing the interface |
| Unchanged organiser harness and evaluator | Both SHA-256 values match the starter archive | Preserve these files unchanged |
| Valid Part A segments | Official validator accepts `predictions_samples.json`; segment/rule tests pass | Obtain labels and check actual event identity and temporal boundaries |
| Causal Part B, one score per frame | Prefix-invariance and no-video-opening tests; the complete original run has 33,075 scores with verified per-frame timestamps | Accident probability calibration has not been measured on labelled pre-crash windows |
| Shipped open model weights, at most 5 GB | All three YOLO11 checksums pass; 62.6 MiB total | Keep the weight files in the public submission |
| No hosted inference or runtime downloads | Local-weight checks, CPU smoke runs, and all four original GPU runs inside a network namespace | Preserve offline behaviour and shipped weights in the final package |
| Two-command clean installation and run | Root requirements installed in a fresh Python environment; the unchanged harness processed all four originals on CUDA without errors (`reports/original_gpu/`) | A fresh operating system/container and the target hardware remain unverified |
| Runtime at most 3× video duration | Current-rule run passes all four originals on RTX 3050 Laptop: 403.7 / 386.5 / 380.7 / 161.5 s (1.19–1.27× duration) | T4-class hardware (16 GB VRAM, 8 CPU cores, 32 GB RAM) remains unverified |
| Same-machine determinism | All four current-rule originals repeated offline in separate fresh processes: every event and all 33,075 risk timestamp/value pairs match the original batch exactly (`reports/original_gpu/equality-reviewed-repeat.json`) | Preserve source/configuration; repeat after model changes; wall-clock log fields naturally differ |
| Predictions for all supplied samples | Root output covers all four originals: 165 events, official validation with no errors/warnings, current provenance and matching website assets; baseline preserved separately | Preserve the verified set when preparing the public tag |
| Sample-result reproducibility | Root manifest binds predictions to inputs, source/configuration and package versions; the complete-set repeat is saved with individual per-video checkpoints and aggregate provenance | Revalidate and regenerate outputs after any inference changes |
| README: installation, approach, data licences and seeds | Sections and commands are present in `README.md` | Confirm all team contributions; retain limitations alongside measured results |
| Team: three members, roles, contributions and links | One profile is present; LinkedIn and portfolio fields are empty | Confirm names and contributions; supply all three profiles and previous-project links |
| Approach diagram and technical report | Diagram shows independent Part A/Part B paths sharing fixed scene configuration; report distinguishes learned/rule-based components and includes the original parked-car/pedestrian contact sheet with sampling limits | Final review against the actual submitted model |
| EDA of every sample | All four original GPU EDA entries and 20 verified JPEGs are packaged; metadata/profile match the run manifest | Verify rendering again after public deployment |
| Annotated playback, timelines and risk curves for every sample | Four complete H.264 videos pass decoding and metadata checks; all events/risk curves match the root output; desktop/mobile browser checks cover each video's playback and timeline/table/risk seeking | Repeat at the public URL; model labels remain unconfirmed |
| Live upload demo with limits, progress and visualised results | Updated app passes a real browser upload: annotated playback, chart, table and HTTP 200 JSON download; a refreshed current-rule Space also passes the offline direct-call check; cleanup tests pass and earlier over-length checks reject long clips | Publish the refreshed demo package and repeat an actual upload at its public URL |
| Public repository, website, weights and predictions | Source and Pages workflow are present | Configured public URLs return HTTP 404; publication has not been verified |
| Public final tag or commit hash | No final tag has been created | Publish only after the remaining gates pass, then record the immutable commit/tag |
| Website remains available through judging | Not established | Confirm hosting ownership and availability arrangements with the team |

The current local package audit reports **77 passes, 3 warnings and no failures**. The original
output, source manifest, EDA and website results now agree. Remaining local audit warnings concern
team profiles, the missing public demo URL and the unchecked public links. The last public-link
check reports **77 passes, 7 warnings and no failures**: the configured repository, website,
weight and prediction URLs still return HTTP 404, and the demo URL is missing. Readiness warnings
deliberately make `--strict` fail. A green non-strict audit
does not establish submission completeness, detection accuracy or T4 runtime.

Website checks now compare the downsampled risk values, timestamps, full-curve peak and input
source kind with the submitted run, in addition to comparing event segments. EDA resolution,
frame count, rounded FPS/duration and processing profile must also match the input manifest.
Twenty-one focused tests cover these metadata checks and matching/changed/missing/unsorted
risk curves. The full suite has 72 tests
with the demo dependencies installed.

## Known model limitations

Dev labels, ablations and empirical calibration are quality improvements encouraged by the
task, not additional mandatory submission artefacts. Their absence must not be mistaken for
evidence of accuracy, but it is separate from the missing publication/team deliverables.

- `near_miss` and `fire_smoke` are disabled. Generic static-obstacle detection is disabled.
- There are no verified prohibited U-turn zones, prohibited turns or solid-line annotations.
- An accident candidate at the start of C3902 has no visually confirmed collision.
- The baseline original GPU run contains 14 accident candidates. Scoped review identified a
  parked-car/pedestrian false positive and prompted general rule corrections. The new full run
  contains nine accident segments, exactly matching the cached-rule comparison; these remaining
  candidates must not be presented as confirmed collisions without further review.
- No complete manually labelled dev set is included. Event counts and valid JSON are not
  accuracy measurements, and heuristic risk scores are not empirically calibrated probabilities.

## Demo lifecycle verification

The demo now renders inside a temporary workspace, copies successful outputs into the output
components' managed caches, and removes the workspace on success or error. Cleanup is checked
hourly with a six-hour age: the pinned Gradio 5.50 implementation uses a modulo-24-hour age
comparison, so the previous 86400-second threshold never expired during normal operation.

Three lifecycle tests cover successful output handoff, scheduled expiry, and cleanup after
rendering/cache-copy errors; they pass as part of the full suite. CI installs
the pinned demo dependencies so these tests are not skipped there. Ruff also passes.

A freshly assembled self-contained Space package processed the real six-second sample clip
with networking disabled and returned all outputs in 12 seconds on CPU, while the GPU batch
was running. Its managed MP4 and JSON also passed the Gradio components' post-processing.
Rendered playback contains 36 sampled frames at 5.994 fps (6.006 seconds), not the input's
180 frames; the demo intentionally renders at its perception stride. This is a local direct-call
check, not a public upload test.

The updated repository app was also started on a separate loopback port and tested through
Chromium: a real MP4 upload returned both playable six-second videos, the rendered Plotly
timeline/risk chart, the event table and a downloadable `events.json` (HTTP 200; one event,
36 demo risk samples), with no page JavaScript errors. Plot readiness was awaited separately
from video readiness. The temporary verification server and browser were closed afterwards.
Public hosting remains unverified. Previously generated `space/` folders must be refreshed from
the current source before deployment; the latest checked package is an ignored local artefact.

After the accident-rule correction, a new self-contained Space package was assembled and all
copied source/configuration files were hash-checked against the current worktree. With networking
disabled it processed the same six-second input in 9 seconds on CPU, returned one event and
36 risk samples, and passed output-component post-processing. This refresh was a direct-call
check; it does not replace the final public browser-upload check.

The report's new visual error-review card also passes desktop/light and mobile/dark browser
checks (1440 px and 390 px): the full-size evidence image loads, no horizontal overflow occurs,
and no page JavaScript errors were observed. The case explicitly separates sampled review from
exhaustive labels or measured accuracy.

## Original input availability

The user completed all four original downloads on 2026-09-27. They were moved from
`/mnt/ssd2/Downloads/` to `data/samples/` on the same second SSD, without making duplicate
copies. The browser's incomplete files were not moved. All four sizes match the previously
checked organiser Drive metadata, and video probing reports 3840×2160 at 30000/1001 fps.
C3896 has 10,200 frames, C3897 and C3902 each have 9,525, and C3905 has 3,825.
C3897 and C3902 have different SHA-256 checksums despite equal byte sizes and frame counts.
Existing partial downloads and official previews have been preserved.

The baseline complete-set harness output is preserved as
`reports/original_gpu/predictions-all.json` with its original manifest. The current-rule run is
`predictions-reviewed.json` / `run-reviewed.json`, with verified logs, budgets, frame coverage
and source/input provenance. All risk curves and non-accident events exactly match the baseline;
only the expected accident-rule results change. Original-set EDA and annotated media were
validated in staging, then promoted together with root predictions and provenance. The old
preview set is recoverable from `.cache/before-original-promotion.vJ7Y5V/` on the second SSD.

All four annotated videos are H.264/yuv420p at 960×636 (540 px image plus the timeline band),
14.985 fps, with the `moov` index before media data for browser seeking. They have 5,100 / 4,763 /
4,763 / 1,913 sampled frames and preserve the input durations to within one sampled-frame period.
Each passes full decoding and is below 100 MB; the original 4K inputs remain outside Git.

The first export process ended with SIGTERM during C3902; its 70-second partial output was
preserved separately and never promoted. The two completed outputs passed full decoding and
were retained. C3902/C3905 were resumed offline from existing GPU perception caches, using
the CPU Python environment and a render-only two-frame read-ahead queue to reduce memory.
No model, event, risk, sampling-stride or frame-content changes were made for this recovery.
An overlapping repeat harness was deliberately terminated without producing a result when RAM
became constrained; it is not counted as a failed model run or as determinism evidence. Heavy
rendering and the repeat harness are subsequently scheduled sequentially.
The subsequent serialized repeat was interrupted across a host restart: its process and tool
session no longer exist, and neither final prediction JSON nor provenance was written. The
first three per-video progress messages are not counted as complete determinism evidence.
The validated first-run output and promoted assets remain unchanged. A subsequent checkpointed
repeat completed all four originals with exact event/risk equality; its individual outputs,
manifests and aggregate are now preserved in `reports/original_gpu/`. The reference processed
all videos in one process; the completed repeat deliberately used one fresh process per video.

The promoted site passed Chromium checks at 1440 px/light and 390 px/dark for all four
originals: the correct video/duration and event count appear; clicking event-table rows,
pressing Enter on timeline bars and clicking the risk curve all seek to the expected time.
Each MP4 returns HTTP 206 for range requests. All four EDA selectors show original metadata
and their image sets; the hero shows 18.4 minutes, 165 events and the 4K-original caption.
No page JavaScript errors or horizontal overflow were observed. Screenshots of desktop/mobile
results and EDA were inspected; the browser was closed after verification.

A delayed-response browser check found that an older C3897 request could replace C3902 after
the visitor had selected it. The results view now ignores superseded draws. The regression
scenario passes at 1440 px and 390 px: the selector, C3902 media, 48 event rows and 48 timeline
bars remain aligned; selecting the cached C3897 result afterwards also works. No page errors
or horizontal overflow occurred. This is a website-only fix and leaves inference unchanged.

## External prerequisites

The [publication runbook](deployment.md) covers repository access, Pages, a freshly assembled
demo package, actual public uploads and the final handoff. Preparing it does not publish either
service. Remote CI is now independently verified: [run 36299069627](https://github.com/samanwirst/hackaton_wiut_2026/actions/runs/36299069627)
passed on commit `e02faf2` with 72 passing tests, Ruff, official prediction validation, all
weight checksums and the package audit (77 passes / 3 warnings / 0 failures). The earlier
CI failure and test-only correction remain visible in [development history](development-history.md).

Both GitHub workflows now pin verified action release commits; CI has read-only repository
permissions and keys its pip cache from the actual CPU/shared/demo dependency files.
`actionlint` 1.7.12 reports no workflow errors. Space metadata explicitly selects Python 3.11
with Gradio 5.50.0. A fresh release package has 32 files, each hash-identical to its current
source; this assembly check did not rerun inference while the full GPU repeat was active.
The Git-visible publication set contains no original/preview inputs, virtual environments or
caches, and none of its files reaches 100 MiB. These are local checks, not remote deployments.

1. Add the three team members and their roles, contributions, GitHub, LinkedIn, portfolios
   and previous projects when supplied. The user explicitly deferred these details until the
   final stage; continue independent work without inventing profiles or requesting them again.
2. GitHub CLI access is now confirmed as `samanwirst`, with ADMIN permission on
   `samanwirst/hackaton_wiut_2026`; the remote remains unchanged. The repository is currently
   private, so authenticated access is not proof of public availability. The user requested
   a separate development branch with reviewable commits; preserve `main` and its existing
   history while preparing that branch. The user explicitly requested that publication be the
   final step: keep the repository private, do not merge to `main`, and do not publish the
   website or demo before a later confirmation. Continue preparation and private-branch
   verification in the meantime. Do not send tokens in chat.
3. Confirm access to an eligible public demo host. No Hugging Face owner or Space URL has
   been supplied. Current [HF documentation](https://huggingface.co/docs/hub/spaces-overview)
   requires a paid plan for ordinary Gradio Space creation, apart from a limited ZeroGPU
   exception; this CPU package has not been verified on ZeroGPU. Hosting costs and availability
   through judging require an explicit decision, not an automatic purchase.
4. Provide access to the evaluation-class machine for the target-hardware benchmark.

The separate clean-container check also needs Docker storage capacity. A local build was
stopped during the base-image pull after checking that `/var/lib/docker` is on the system
partition with only about 7 GiB free, whereas the project is on a different partition.
No existing images were pruned and no daemon/storage configuration was changed. The native
clean-Python-environment GPU checks are complete; the Docker build is **not** verified.

## Final checks

From the repository root, using the environment appropriate to the machine:

```bash
pytest -q
ruff check .
python evaluate.py --pred predictions_samples.json --validate-only
python tools/check_submission.py --strict --online
```

Also inspect every annotated sample, repeat the official harness on the same machine with
network access disabled, compare its event/risk outputs, and perform a real upload through the
published demo. These are separate checks; none is replaced by the static package audit.
