# Local datasets

- `samples/`: original organiser videos and resumable `.part` downloads (ignored by Git).
- `previews/`: smaller official preview transcodes for local work (ignored by Git).
- `labels/`: dev annotations and scoped review notes, when available; these may be committed.

`labels/candidate_reviews.json` contains scoped, AI-assisted visual-review notes, **not**
exhaustive metric ground truth. Do not pass it to the official evaluator as dev labels.

From the repository root:

```bash
python tools/download_samples.py
python tools/download_samples.py --preview --out data/previews
```

Keep generated predictions and run reports in `reports/`, except for the submission's
root-level `predictions_samples.json`. Published website assets belong to `website/data/`
and `website/media/`, not this directory.
