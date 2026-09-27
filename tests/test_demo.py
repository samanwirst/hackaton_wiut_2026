"""Demo output lifecycle: no unmanaged originals and working scheduled cleanup.

Requires the optional demo dependencies; inference/rendering are replaced with small fixtures.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("gradio")
pytest.importorskip("plotly")


@pytest.fixture
def app(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "demo" / "app.py"
    spec = importlib.util.spec_from_file_location("trafficwatch_demo_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = tmp_path / "cache"
    monkeypatch.setattr(module.out_video, "GRADIO_CACHE", str(cache))
    monkeypatch.setattr(module.download, "GRADIO_CACHE", str(cache))
    info = SimpleNamespace(n_frames=25, width=1280, height=720, fps=25.0, duration=1.0)
    result = SimpleNamespace(perception=SimpleNamespace(info=info), scene=None,
                             events=[[0.1, 0.9, "jaywalking"]], raw_events=[])
    monkeypatch.setattr(module, "probe", lambda _: info)
    monkeypatch.setattr(module, "analyze", lambda *args, **kwargs: result)
    monkeypatch.setattr(module, "risk_curve_from_perception", lambda *args: ([0.0, 0.5], [0.01, 0.2]))
    monkeypatch.setattr(module, "timeline_figure", lambda *args: None)
    upload = tmp_path / "upload.mp4"
    upload.write_bytes(b"test upload")
    return module, upload


def test_outputs_survive_workspace_cleanup_and_expire_from_managed_cache(app, monkeypatch):
    import gradio.route_utils as route_utils

    module, upload = app
    rendered = []

    def render(*args, **kwargs):
        target = Path(args[5])
        target.write_bytes(b"test rendered video")
        rendered.append(target)

    monkeypatch.setattr(module, "render_video", render)
    _, video, _, table, events = module.run(str(upload), progress=lambda *args, **kwargs: None)
    assert not rendered[0].parent.exists()
    assert Path(video).read_bytes() == b"test rendered video"
    assert json.loads(Path(events).read_text())["events"] == [[0.1, 0.9, "jaywalking"]]
    assert table == [[0.1, 0.9, "jaywalking", 0.8]]
    assert video in module.out_video.temp_files
    assert events in module.download.temp_files
    assert any(video in files for files in module.demo.temp_file_sets)
    assert any(events in files for files in module.demo.temp_file_sets)
    assert module.demo.delete_cache == (3600, module.CACHE_MAX_AGE_S)

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(hours=7)

    monkeypatch.setattr(route_utils, "datetime", Later)
    route_utils.delete_files_created_by_app(module.demo, age=module.CACHE_MAX_AGE_S)
    assert not Path(video).exists()
    assert not Path(events).exists()
    assert upload.exists()  # Never remove caller-owned inputs.


@pytest.mark.parametrize("fail_at", ["render", "cache"])
def test_failed_render_or_cache_copy_cleans_workspace(app, monkeypatch, fail_at):
    module, upload = app
    rendered = []

    def render(*args, **kwargs):
        target = Path(args[5])
        target.write_bytes(b"partial rendered video")
        rendered.append(target)
        if fail_at == "render":
            raise OSError("render failed")

    def cache_failure(*args, **kwargs):
        raise OSError("cache failed")

    monkeypatch.setattr(module, "render_video", render)
    if fail_at == "cache":
        monkeypatch.setattr(module.out_video, "move_resource_to_block_cache", cache_failure)
    with pytest.raises(OSError, match=f"{fail_at} failed"):
        module.run(str(upload), progress=lambda *args, **kwargs: None)
    assert not rendered[0].parent.exists()
    assert upload.exists()


@pytest.mark.parametrize("case,message", [
    ("empty", "Upload an .mp4 first"),
    ("extension", "Only .mp4 files"),
    ("missing", "not a readable MP4"),
    ("corrupt", "not a readable MP4"),
    ("zero_frames", "no readable frames"),
    ("zero_width", "no readable frames"),
    ("zero_height", "no readable frames"),
    ("too_long", "up to 2 minutes"),
])
def test_invalid_upload_is_rejected_before_inference(app, monkeypatch, case, message):
    module, upload = app

    def should_not_run(*args, **kwargs):
        pytest.fail("Rejected uploads must not start inference")

    monkeypatch.setattr(module, "analyze", should_not_run)
    path = str(upload)
    if case == "empty":
        path = ""
    elif case == "extension":
        path = str(upload.with_suffix(".mov"))
    elif case == "missing":
        path = str(upload.with_name("missing.mp4"))
    elif case == "corrupt":
        def unreadable(_):
            raise OSError("Cannot decode input")
        monkeypatch.setattr(module, "probe", unreadable)
    else:
        info = SimpleNamespace(n_frames=25, width=1280, height=720, fps=25.0, duration=1.0)
        if case == "too_long":
            info.duration = module.MAX_DURATION_S + 0.11
        else:
            setattr(info, {"zero_frames": "n_frames", "zero_width": "width", "zero_height": "height"}[case], 0)
        monkeypatch.setattr(module, "probe", lambda _: info)
    with pytest.raises(module.gr.Error, match=message):
        module.run(path, progress=lambda *args, **kwargs: None)
    assert upload.exists()


def test_oversize_upload_is_rejected_before_decoding(app, monkeypatch):
    module, upload = app
    original_stat = Path.stat

    def stat(path, *args, **kwargs):
        if path == upload:
            return SimpleNamespace(st_size=module.MAX_UPLOAD_BYTES + 1)
        return original_stat(path, *args, **kwargs)

    def should_not_run(*args, **kwargs):
        pytest.fail("Oversize upload must be rejected before decoding or inference")

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(module, "probe", should_not_run)
    monkeypatch.setattr(module, "analyze", should_not_run)
    with pytest.raises(module.gr.Error, match="up to 500 MB"):
        module.run(str(upload), progress=lambda *args, **kwargs: None)


@pytest.mark.parametrize("duration", [119.99, 120.0, 120.1])
def test_duration_limit_allows_boundary_and_frame_rounding_tolerance(app, monkeypatch, duration):
    module, upload = app
    info = SimpleNamespace(n_frames=3600, width=1280, height=720, fps=30.0, duration=duration)
    monkeypatch.setattr(module, "probe", lambda _: info)

    def reached_inference(*args, **kwargs):
        raise RuntimeError("Accepted upload reached inference")

    monkeypatch.setattr(module, "analyze", reached_inference)
    with pytest.raises(RuntimeError, match="Accepted upload reached inference"):
        module.run(str(upload), progress=lambda *args, **kwargs: None)


def test_uppercase_mp4_extension_is_accepted(app, monkeypatch):
    module, upload = app
    uppercase = upload.rename(upload.with_suffix(".MP4"))

    def reached_inference(*args, **kwargs):
        raise RuntimeError("Accepted upload reached inference")

    monkeypatch.setattr(module, "analyze", reached_inference)
    with pytest.raises(RuntimeError, match="Accepted upload reached inference"):
        module.run(str(uppercase), progress=lambda *args, **kwargs: None)
