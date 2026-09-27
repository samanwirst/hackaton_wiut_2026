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
