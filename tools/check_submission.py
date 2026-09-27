#!/usr/bin/env python3
"""Audit the repository against the WIUT submission package requirements.

The default mode fails only on defects that would break or invalidate a submission.  ``--strict``
also fails on missing publication/team/sample-visualisation items and is intended for the final tag.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluate import OFFICIAL_CLASSES, validate  # noqa: E402

REQUIRED = (
    "solution.py",
    "run_submission.py",
    "evaluate.py",
    "requirements.txt",
    "requirements/base.txt",
    "requirements/cpu.txt",
    "Dockerfile",
    ".dockerignore",
    "README.md",
    "weights",
    "src",
    "predictions_samples.json",
    "website/index.html",
    "demo/app.py",
)
STARTER_HASHES = {
    "run_submission.py": "a47b494afae14432a65166b43cd5f2a278408ce661aecf0fb86b6fa05a06c204",
    "evaluate.py": "111c6fa04709c9f1df4ea3db4bede749953b2c27bdc5679c2ef56794637573b5",
}
WEIGHT_HASHES = {
    "yolo11n.pt": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
    "yolo11s.pt": "85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5",
    "yolo11m.pt": "d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95",
}
SITE_SECTIONS = ("team", "approach", "eda", "results", "demo", "report", "links")
SAMPLE_NAMES = {"C3896.MP4", "C3897.MP4", "C3902.MP4", "C3905.MP4"}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def solution_classes() -> list[str]:
    """Read the public interface without importing heavyweight inference dependencies."""
    tree = ast.parse((ROOT / "solution.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CLASSES" for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return list(value)
    return []


def result_risk_matches(result: dict, prediction: dict) -> bool:
    """The website curve is a rounded subset, with the exact full-curve peak.

    Allow display downsampling without accepting a different model's risk values.
    Check endpoints as well, so an empty or truncated chart cannot silently pass.
    """
    try:
        source = prediction["risk"]
        curve = result["risk"]
        peak = result["risk_peak"]
        if not source:
            return curve == [] and peak == [0, 0]
        rounded = {(round(float(t), 2), round(float(score), 3)) for t, score in source}
        shown = [tuple(point) for point in curve]
        if not shown or any(point not in rounded for point in shown):
            return False
        if shown[0] != tuple(round(float(v), d) for v, d in zip(source[0], (2, 3))):
            return False
        if shown[-1] != tuple(round(float(v), d) for v, d in zip(source[-1], (2, 3))):
            return False
        if any(a[0] >= b[0] for a, b in zip(shown, shown[1:])):
            return False
        best = max(source, key=lambda point: point[1])
        return peak == [round(float(best[0]), 2), round(float(best[1]), 3)]
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def eda_input_matches(item: dict, source: dict, profile: str) -> bool:
    """EDA must describe the same input/profile as the recorded sample run.

    The exporter rounds fps to three decimal places and duration to two. Compare
    at that precision without accepting metadata from a lower-resolution preview.
    """
    try:
        return (
            item["profile"] == profile
            and all(item[key] == source[key] for key in ("width", "height", "n_frames"))
            and math.isclose(float(item["fps"]), round(float(source["fps"]), 3), rel_tol=0, abs_tol=1e-9)
            and math.isclose(float(item["duration"]), round(float(source["duration"]), 2), rel_tol=0, abs_tol=1e-9)
        )
    except (KeyError, TypeError, ValueError):
        return False


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def check(self, condition: bool, success: str, failure: str, warning: bool = False) -> None:
        if condition:
            self.passes.append(success)
        elif warning:
            self.warnings.append(failure)
        else:
            self.errors.append(failure)

    def read_json(self, relative: str, default):
        try:
            return json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.errors.append(f"cannot read {relative}: {exc}")
            return default


def audit(online: bool = False) -> Audit:
    out = Audit()

    missing = [path for path in REQUIRED if not (ROOT / path).exists()]
    out.check(not missing, "required package paths are present", f"missing required paths: {missing}")

    for name, expected in STARTER_HASHES.items():
        path = ROOT / name
        out.check(path.is_file() and digest(path) == expected, f"{name} matches the organiser starter",
                  f"{name} differs from the organiser starter")

    out.check((ROOT / "solution.py").is_file() and solution_classes() == OFFICIAL_CLASSES, "solution exposes all 14 official class ids",
              "solution.CLASSES does not exactly match the 14 official ids")

    gpu_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8") if (ROOT / "requirements.txt").is_file() else ""
    cpu_requirements = (ROOT / "requirements/cpu.txt").read_text(encoding="utf-8") if (ROOT / "requirements/cpu.txt").is_file() else ""
    out.check("torch==2.6.0+cu124" in gpu_requirements,
              "evaluation requirements select the CUDA 12.4 PyTorch wheel",
              "evaluation requirements do not pin the expected CUDA PyTorch wheel")
    out.check("torch==2.6.0+cpu" in cpu_requirements,
              "development requirements select the CPU-only PyTorch wheel",
              "development requirements do not pin the CPU-only PyTorch wheel")

    weight_bytes = 0
    for name, expected in WEIGHT_HASHES.items():
        path = ROOT / "weights" / name
        good = path.is_file() and digest(path) == expected
        out.check(good, f"{name} checksum is valid", f"missing or corrupt model weight: {name}")
        if path.is_file():
            weight_bytes += path.stat().st_size
    out.check(weight_bytes <= 5 * 1024**3, f"weights total {weight_bytes / 2**20:.1f} MiB",
              "model weights exceed the 5 GiB limit")

    pred_path = ROOT / "predictions_samples.json"
    try:
        predictions = json.loads(pred_path.read_text(encoding="utf-8"))
        pred_errors, pred_warnings = validate(predictions)
    except (OSError, json.JSONDecodeError) as exc:
        pred_errors, pred_warnings, predictions = [str(exc)], [], {"videos": {}}
    out.check(not pred_errors, "predictions_samples.json passes the official validator",
              "invalid predictions_samples.json: " + "; ".join(pred_errors[:3]))
    out.warnings.extend(f"prediction warning: {message}" for message in pred_warnings)
    predicted_names = set(predictions.get("videos", {}))
    out.check(predicted_names == SAMPLE_NAMES, "predictions cover all four official samples",
              f"sample predictions incomplete: have {sorted(predicted_names)}, need {sorted(SAMPLE_NAMES)}",
              warning=True)

    logs = predictions.get("log", {})
    bad_runs = [name for name in predicted_names if not logs.get(name) or logs[name].get("errors")
                or logs[name].get("total_sec", float("inf")) > logs[name].get("budget_sec", 0)]
    out.check(not bad_runs, "recorded harness runs have no errors and respect the time budget",
              f"missing, failed or over-budget harness logs: {sorted(bad_runs)}", warning=True)
    run_path = ROOT / "reports/submission_run.json"
    run = {}
    if run_path.is_file():
        run = out.read_json("reports/submission_run.json", {})
        out.check(run.get("predictions_sha256") == digest(pred_path),
                  "prediction provenance matches the committed output",
                  "prediction provenance is stale or does not match predictions_samples.json")
        out.check(run.get("input_kind") == "original" and run.get("profile") == "gpu",
                  "sample run uses original footage and the evaluation profile",
                  "sample run is provisional: original footage / evaluation-profile reproduction still required",
                  warning=True)
        for sample, info in run.get("inputs", {}).items():
            entry = predictions.get("videos", {}).get(sample)
            out.check(entry is not None and len(entry.get("risk", [])) == info.get("n_frames"),
                      f"{sample} has one risk score per input frame",
                      f"{sample} has missing or incomplete frame risks")
        for name, expected in {**run.get("config_sha256", {}), **run.get("source_sha256", {})}.items():
            path = ROOT / name
            out.check(path.is_file() and digest(path) == expected,
                      f"run source matches {name}", f"sample predictions predate changes to {name}")
    else:
        out.warnings.append("sample-run provenance is missing: reports/submission_run.json")

    html_path = ROOT / "website" / "index.html"
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    missing_sections = [section for section in SITE_SECTIONS if f'id="{section}"' not in html]
    out.check(not missing_sections, "website contains all seven required sections",
              f"website sections missing: {missing_sections}")

    site = out.read_json("website/data/site.json", {})
    team = site.get("team") or []
    member_fields = ("name", "role", "contributions", "github", "linkedin", "portfolio", "projects")
    incomplete = [member.get("name", "unnamed") for member in team if not all(member.get(k) for k in member_fields)]
    out.check(len(team) == 3 and not incomplete,
              "three complete team profiles, contributions and portfolio links are configured",
              f"team profiles incomplete: {len(team)}/3 members; missing fields for {incomplete}", warning=True)
    out.check(bool(site.get("repo_url")), "repository link is configured",
              "repository link is missing", warning=True)
    out.check(bool(site.get("demo_url")), "public live-demo link is configured",
              "public live-demo URL is not configured", warning=True)
    out.check(bool(site.get("website_url")), "website URL is configured",
              "website URL is not configured", warning=True)

    if online:
        for key in ("repo_url", "website_url", "demo_url", "weights_url", "predictions_url"):
            url = site.get(key, "")
            if not url.startswith("https://"):
                out.warnings.append(f"{key}: missing public HTTPS URL")
                continue
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "TrafficWatch-readiness-audit/1.0"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    out.check(response.status == 200, f"{key} is reachable without credentials",
                              f"{key} returned HTTP {response.status}", warning=True)
            except (OSError, urllib.error.URLError) as exc:
                out.warnings.append(f"{key} is not publicly reachable: {exc}")
    else:
        out.warnings.append("public link availability not checked (use --online before submission)")

    eda = out.read_json("website/data/eda.json", {})
    eda_names = {item.get("video") for item in eda.get("videos", [])}
    out.check(eda_names == SAMPLE_NAMES, "EDA covers all four official samples",
              f"EDA incomplete: have {sorted(eda_names)}, need {sorted(SAMPLE_NAMES)}", warning=True)
    out.check(run.get("input_kind") in ("original", "preview") and eda.get("source_kind") == run.get("input_kind"),
              "EDA input source kind matches the sample run",
              "EDA input source kind differs from the sample run", warning=True)
    for item in eda.get("videos", []):
        source = run.get("inputs", {}).get(item.get("video"), {})
        out.check(eda_input_matches(item, source, run.get("profile")),
                  f"{item.get('video')} EDA metadata/profile match the sample run",
                  f"{item.get('video')} EDA metadata/profile differ from the sample run", warning=True)
        paths = item.get("images", {}).values()
        missing_images = [p for p in paths if not (ROOT / "website" / p).is_file()]
        out.check(not missing_images, f"{item.get('video')} EDA images exist",
                  f"missing EDA images: {missing_images}")
    results = out.read_json("website/data/results_index.json", [])
    result_names = {item.get("video") for item in results}
    out.check(result_names == SAMPLE_NAMES, "website results cover all four official samples",
              f"result visualisations incomplete: have {sorted(result_names)}, need {sorted(SAMPLE_NAMES)}",
              warning=True)
    for item in results:
        data = out.read_json("website/" + item["file"], {})
        media = ROOT / "website" / data.get("annotated", "")
        out.check(media.is_file() and media.stat().st_size > 12,
                  f"{item['video']} annotated media is packaged", f"missing annotated media: {media}")
        entry = predictions.get("videos", {}).get(item["video"])
        out.check(entry is not None and data.get("events") == entry.get("events"),
                  f"{item['video']} website events match predictions_samples.json",
                  f"{item['video']} website results differ from the submitted predictions", warning=True)
        out.check(entry is not None and result_risk_matches(data, entry),
                  f"{item['video']} website risk curve and peak match predictions_samples.json",
                  f"{item['video']} website risk curve/peak do not match the submitted predictions", warning=True)
        out.check(run.get("input_kind") in ("original", "preview")
                  and data.get("prediction_source") == "submission harness"
                  and data.get("source_kind") == item.get("source_kind") == run.get("input_kind"),
                  f"{item['video']} website input provenance matches the sample run",
                  f"{item['video']} website input/provenance differs from the sample run", warning=True)

    tracked_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [ROOT / "README.md", ROOT / "website" / "data" / "site.json"] if path.is_file()
    ).lower()
    out.check("todo" not in tracked_text, "submission-facing content has no TODO placeholders",
              "submission-facing content still contains TODO placeholders")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="treat readiness warnings as failures")
    parser.add_argument("--online", action="store_true", help="also verify public links without credentials")
    args = parser.parse_args()
    result = audit(online=args.online)
    for message in result.passes:
        print(f"PASS  {message}")
    for message in result.warnings:
        print(f"WARN  {message}")
    for message in result.errors:
        print(f"FAIL  {message}")
    print(
        f"\n{len(result.passes)} passed, {len(result.warnings)} warning(s), "
        f"{len(result.errors)} failure(s)"
    )
    return 1 if result.errors or (args.strict and result.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
