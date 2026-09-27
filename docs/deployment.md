# Publication runbook

Keep the confirmed repository owner: `samanwirst/hackaton_wiut_2026`.
This is the operating runbook. Actual deployment evidence is recorded separately in
[server verification](../reports/server_demo/).
See [submission readiness](submission-readiness.md) for the measured results and open gates.

Registered team: **Zero Context** (project: TrafficWatch). The captain's participant portal,
checked on 27 September 2026, gives the deadline as **27 September, 23:59 Tashkent time
(UTC+5)**.

**Publication was authorised by the owner during the evening session**, conditional on a
successful server-demo check and protecting credentials/private registration data. Those checks
passed before the repository and demo were made public. The approval covers the
public repository, merging to `main`, the website and an isolated HTTPS demo. The captain later
lifted the submission pause and authorised sending the form after final specification checks.
Do not interpret release approval as permission to
modify or restart other sites on the shared server.

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
cache key includes the CPU, shared, demo and optional notebook requirements, using
[`cache-dependency-path`](https://github.com/actions/setup-python#caching-packages-dependencies).

## 3. Prepare and publish the live demo

**Evening update:** the owner supplied a shared server and authorised preparation there,
with an explicit requirement not to disrupt its existing sites. Use the isolated
[server staging instructions](../demo/server/README.md) for this route. No HF account or
purchase is now needed. Keep staging private until publication is approved; test real
uploads and existing-site health before adding any HTTPS route. The HF instructions below
remain an alternative, not the selected deployment or a purchase request.

For the HF alternative, first confirm the team's owner, access and hosting eligibility. Current HF docs
require a paid plan to create ordinary Gradio/Docker Spaces, with a limited ZeroGPU exception
for eligible personal accounts. This package is a CPU Gradio app, not a verified ZeroGPU app.
Do not purchase a plan, allocate paid hardware or switch platforms without approval.
Free hardware can also sleep after inactivity; agree how the demo will remain available through
judging. See [Spaces creation and lifecycle](https://huggingface.co/docs/hub/spaces-overview).

### Historical hosting alternatives (not used for this release)

The captain confirmed that the team has no existing host. Official HF terms were checked
again on **27 September 2026**; a newly created free account is not a ready CPU-demo host.

| Option | Published cost / eligibility | Consequence for this package |
|---|---|---|
| Personal PRO + CPU Basic | $9/month subscription; no hourly CPU charge; 2 vCPU / 16 GB RAM | Uses the prepared Gradio package; remote build and upload still need testing |
| Personal PRO + CPU Upgrade | $9/month plus $0.03/hour; 8 vCPU / 32 GB RAM | Same package; paid hardware stays awake by default |
| Free ZeroGPU | Verified email and account older than 30 days | Not an immediate option for a new account; this CPU package is not ZeroGPU-verified |

Prices: [HF pricing](https://huggingface.co/pricing). CPU Upgrade computes to **$0.72 per
24 running hours**, additional to the subscription; that is an estimate from the hourly rate,
not a checkout quote or an authorised purchase. Agree a spending cap and hosting duration
before enabling it. Do not treat the PRO subscription alone as an always-awake hardware upgrade.

CPU Basic currently sleeps after 48 hours of inactivity and wakes when visited; upgraded
hardware does not sleep by default. This affects the judging-period availability plan:
see [sleep settings](https://huggingface.co/docs/hub/spaces-gpus#set-a-custom-sleep-time).
The [ZeroGPU requirements](https://huggingface.co/docs/hub/spaces-zerogpu) also list a different
supported Python/PyTorch runtime from this tested Python 3.11 / PyTorch 2.6 CPU package.
Do not simply relabel the existing package as ZeroGPU or promise a same-evening free deployment.

An ordinary Gradio Space was the initial prepared option before the captain supplied a server.
The final release uses that server, not HF. No hosting subscription or paid hardware purchase
was made. The following Space-specific assembly notes are retained only as an alternative.

### Assemble the approved package

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
  After permission to test that public deployment, run
  `python tools/verify_demo.py --base-url <direct-app-url> --video <test-clip.mp4>` and inspect
  the saved screenshot and verification JSON. This command uploads the selected clip and
  triggers inference; it is not a read-only availability probe.
  Use `--width 390 --height 844` for mobile and optionally
  `--reject-video <over-length.mp4>` to verify the visible error after a successful upload.
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
| Repository | `https://github.com/samanwirst/hackaton_wiut_2026` — public with owner approval |
| Tag or commit hash | The final tested tag or full 40-character commit hash; not an intermediate checkpoint |
| Team website | Confirm the deployed website, including its working public live demo, before copying the URL |
| T-shirt sizes | Captain Samandar, then Shohruxxo’ja, then Doniyorbek; supplied privately, use the latest captain corrections |
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
