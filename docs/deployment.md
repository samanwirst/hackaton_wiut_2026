# Publication runbook

Keep the confirmed repository owner: `samanwirst/hackaton_wiut_2026`.
This is a preparation checklist, not evidence that any service has been deployed.
See [submission readiness](submission-readiness.md) for the measured results and open gates.

Registered team: **Zero Context** (project: TrafficWatch). The captain's participant portal,
checked on 27 September 2026, gives the deadline as **27 September, 23:59 Tashkent time
(UTC+5)**.

**Publication is deliberately deferred by the owner.** Keep the repository private, preserve
`main`, and prepare/verify changes on `feat/trafficwatch-submission`. Do not enable the public
website, publish the demo or change repository visibility until the owner confirms the final
publication step. The commands below describe that later release, not permission to run it now.

## 1. Confirm access and the release contents

These commands are read-only and do not print credentials:

```bash
git remote get-url origin
gh api user --jq .login
gh repo view samanwirst/hackaton_wiut_2026 --json nameWithOwner,visibility,viewerPermission,url
git status --short
python evaluate.py --pred predictions_samples.json --validate-only
python tools/check_submission.py
```

Stop if the target is inaccessible. Authenticate locally with the confirmed account; do not
paste tokens into chat or change the remote to a different owner. An authenticated 404 alone
does not establish whether a repository is absent or private. The final repository must be
public, and the authenticated account must be authorised to publish to it.

Review the files before committing: include current source/configuration, all three weights,
root predictions and their manifest, reports, and the complete `website/` assets. Leave raw
videos, `.cache/`, virtual environments, partial downloads and generated `space/` packages out
of Git. Use the existing original-run outputs; do not replace them with a CPU/preview run.
Use names and registration details verified in the participant portal. Roles, contributions,
portfolio links and previous projects still need confirmation if the portal does not provide
them; do not invent details or copy private contact information into the public site.

## 2. Publish the static website

After repository access is available and publication is approved, push the reviewed changes to
`main` in the confirmed repository. In **Settings → Pages → Build and deployment**, select
**GitHub Actions** as the source. The existing `pages.yml` uploads only `website/`; no Node
build or inference is required. Its permissions and `github-pages` environment follow
[GitHub's custom-workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

Open the **Tests** and **Deploy website** runs and check that both succeed. A change to the
website or its deployment workflow triggers Pages on `main`; **Run workflow** is also available.
Confirm the actual deployment URL is `https://samanwirst.github.io/hackaton_wiut_2026/` and
open it in a signed-out browser. A successful local audit is not a successful remote CI run.

The Actions references are pinned to release commits checked on 2026-09-27:
[checkout 7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
[setup-python 7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0),
[configure-pages 6.0.0](https://github.com/actions/configure-pages/releases/tag/v6.0.0),
[upload-pages-artifact 5.0.0](https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0),
[deploy-pages 5.0.1](https://github.com/actions/deploy-pages/releases/tag/v5.0.1).
CI has read-only repository permissions and does not retain checkout credentials. Its pip
cache key includes the CPU, shared and demo requirements, using
[`cache-dependency-path`](https://github.com/actions/setup-python#caching-packages-dependencies).

## 3. Prepare and publish the live demo

First confirm the team's Hugging Face owner, access and hosting eligibility. Current HF docs
require a paid plan to create ordinary Gradio/Docker Spaces, with a limited ZeroGPU exception
for eligible personal accounts. This package is a CPU Gradio app, not a verified ZeroGPU app.
Do not purchase a plan, allocate paid hardware or switch platforms without approval.
Free hardware can also sleep after inactivity; agree how the demo will remain available through
judging. See [Spaces creation and lifecycle](https://huggingface.co/docs/hub/spaces-overview).

Assemble from the current source into a new, ignored directory:

```bash
mkdir -p .cache
SPACE_STAGE_DIR=$(mktemp -d .cache/space-release.XXXXXX)
bash demo/prepare_space.sh "$SPACE_STAGE_DIR/space"
```

The script refuses existing output paths. Keep its printed path; do not reuse an old `space/`
folder. The generated folder contains `app.py`, `requirements.txt`, `packages.txt`, `README.md`,
`LICENSE`, `src/`, `configs/` and the CPU model `weights/yolo11n.pt`.
No original videos or evaluation GPU weights are needed in the demo package.

Once an eligible, approved **public Gradio Space** exists, upload the generated folder's
**contents to the Space repository root**, not inside a `space/` subfolder. Preserve the Space's
repository metadata. Its root README selects Gradio 5.50.0, Python 3.11 and `app.py`, matching
the checked local runtime family; see the
[Space configuration reference](https://huggingface.co/docs/hub/spaces-config-reference).
Wait for the actual build and app startup, then test an upload before adding its links to the site.

Set these fields in `website/data/site.json` only after the URLs are real and reachable:

| Field | Value to copy |
|---|---|
| `demo_url` | The public `https://huggingface.co/spaces/<owner>/<name>` page |
| `demo_embed_url` | The direct `https://<assigned-subdomain>.hf.space` URL from the Space's embed menu |

Do not guess the assigned subdomain or put the HF repository page inside the iframe.
Keep embedding enabled; HF documents the direct URL and iframe setup in
[Embed your Space](https://huggingface.co/docs/hub/spaces-embed).
Publish the updated website and test both the embedded and standalone app while signed out.

## 4. Public acceptance checks and final handoff

- All four sample videos play and seek from the event table, timeline and risk chart on desktop
  and mobile. Their event counts and risk curves match `predictions_samples.json` exactly;
  EDA shows all four original 4K inputs. Run `python tools/verify_website.py --base-url <url>`
  against the selected deployment and inspect its screenshots.
- A real MP4 upload to the public demo shows progress, annotated playback, timeline/risk chart,
  an event table and a working JSON download. Also check rejection of a clip over 120 seconds;
  the advertised upload limit is 500 MB. No private login should be required.
- Repository, weights, predictions and demo links open while signed out. Check for page errors
  and missing assets; an HTTP 200 alone does not prove the upload workflow works.
- Add the three confirmed profiles and contributions to both the README and website when
  supplied. Retain the report's limitations and unconfirmed-candidate wording.

Run the final gates from the repository root:

```bash
pytest -q
ruff check .
python evaluate.py --pred predictions_samples.json --validate-only
python tools/check_submission.py --strict --online
```

Do not weaken strict checks to hide missing profiles or unreachable links. The static audit
does not measure accuracy, benchmark T4 hardware or replace a real public upload. Record the
published Space revision and GitHub commit after successful checks. Create the final immutable
tag/commit handoff only after the remaining requirements are satisfied; submit that repository
reference together with the website URL and keep both services available through judging.

## 5. Participant-portal handoff

The captain's [submission form](https://hackathon.wiut.uz/team/submit/) was inspected read-only
on 27 September. It is still **not submitted**. It requests:

| Field | Prepared value / remaining action |
|---|---|
| Repository | `https://github.com/samanwirst/hackaton_wiut_2026` — make public only after approval |
| Tag or commit hash | The final tested tag or full 40-character commit hash; not an intermediate checkpoint |
| Team website | Confirm the deployed website, including its working public live demo, before copying the URL |
| T-shirt sizes | Captain Samandar, then Shohruxxo’ja, then Doniyorbek; sizes still need the team's input |
| Message to reviewers | Optional; draft below |

Draft reviewer message (revise against the final verified package before sending):

> Zero Context presents TrafficWatch: an offline open-weights detector/tracker with explainable
> traffic-event rules and an independent causal accident-risk estimator. The repository includes
> weights, sample predictions and reproducibility evidence. The website documents the approach,
> EDA, original-sample visualisations and known limitations; event counts are not accuracy scores.

Submitting confirms originality/compliance and sends an e-mail receipt to every team member.
Do not click **Submit** during preparation. Obtain the owner's separate final confirmation,
submit before **27 September 2026, 23:59 Tashkent time**, and verify the resulting portal status
and submitted references rather than assuming a click succeeded.
