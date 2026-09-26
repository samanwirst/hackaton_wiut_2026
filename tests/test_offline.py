"""Missing package assets must fail locally instead of triggering a network download."""
import pytest
import synthetic  # noqa: F401

from trafficwatch.detector import Detector


def test_missing_weights_are_rejected_before_model_loading(tmp_path, monkeypatch):
    import ultralytics

    def unexpected_model(*args, **kwargs):
        raise AssertionError("YOLO may download missing weights")

    monkeypatch.setattr(ultralytics, "YOLO", unexpected_model)
    with pytest.raises(FileNotFoundError, match="Missing local weights"):
        Detector(str(tmp_path / "yolo11n.pt"))
