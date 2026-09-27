"""Check that website risk visualisations cannot silently diverge from the submission."""
from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "tools" / "check_submission.py"
_spec = importlib.util.spec_from_file_location("submission_audit", _path)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


@pytest.fixture
def curves():
    source = {"risk": [[0.0, 0.01], [0.0334, 0.7], [0.0667, 0.9156], [0.1001, 0.01]]}
    display = {"risk": [[0.0, 0.01], [0.07, 0.916], [0.1, 0.01]], "risk_peak": [0.07, 0.916]}
    return source, display


def test_rounded_downsampled_curve_and_peak_match(curves):
    source, display = curves
    assert audit.result_risk_matches(display, source)


@pytest.mark.parametrize("change", ["score", "timestamp", "peak", "start", "end", "empty", "order", "missing"])
def test_changed_or_incomplete_display_is_rejected(curves, change):
    source, display = deepcopy(curves)
    if change == "score":
        display["risk"][1][1] = 0.1
    elif change == "timestamp":
        display["risk"][1][0] = 0.05
    elif change == "peak":
        display["risk_peak"] = [0.03, 0.7]
    elif change == "start":
        display["risk"].pop(0)
    elif change == "end":
        display["risk"].pop()
    elif change == "empty":
        display["risk"] = []
    elif change == "order":
        display["risk"].insert(1, display["risk"][1])
    elif change == "missing":
        del display["risk"]
    assert not audit.result_risk_matches(display, source)


def test_peak_uses_first_full_curve_maximum_even_when_not_displayed(curves):
    source, display = curves
    source["risk"][1][1] = source["risk"][2][1]
    display["risk_peak"] = [0.03, 0.916]
    assert audit.result_risk_matches(display, source)


def test_empty_curve_is_valid_only_for_empty_submission():
    display = {"risk": [], "risk_peak": [0, 0]}
    assert audit.result_risk_matches(display, {"risk": []})
    assert not audit.result_risk_matches({"risk": [[0, 0]], "risk_peak": [0, 0]}, {"risk": []})


@pytest.fixture
def original_metadata():
    source = {"width": 3840, "height": 2160, "n_frames": 9525, "fps": 30000 / 1001, "duration": 317.8175}
    display = {**source, "fps": 29.97, "duration": 317.82, "profile": "gpu"}
    return source, display


def test_rounded_original_eda_metadata_matches(original_metadata):
    source, display = original_metadata
    assert audit.eda_input_matches(display, source, "gpu")


@pytest.mark.parametrize("field,value", [
    ("width", 1920), ("height", 1080), ("n_frames", 9524), ("fps", 25),
    ("duration", 318), ("profile", "demo"), ("fps", float("nan")), ("duration", None),
])
def test_changed_eda_metadata_is_rejected(original_metadata, field, value):
    source, display = original_metadata
    display[field] = value
    assert not audit.eda_input_matches(display, source, "gpu")


def test_missing_eda_metadata_is_rejected(original_metadata):
    source, display = original_metadata
    assert not audit.eda_input_matches({}, source, "gpu")
    assert not audit.eda_input_matches(display, {}, "gpu")
