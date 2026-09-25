"""Helpers shared by the developer tools."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trafficwatch.config import load_config  # noqa: E402
from trafficwatch.pipeline import perceive  # noqa: E402
from trafficwatch.scene import load_scene  # noqa: E402
from trafficwatch.video import probe  # noqa: E402

DEFAULT_CACHE = ROOT / ".cache" / "perception"


def list_videos(path: str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(v for v in p.iterdir() if v.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv"))


def perceive_cached(video: Path, profile: str | None = None, cfg: dict | None = None):
    """Perception with the developer cache switched on (tools re-run rules many times)."""
    os.environ.setdefault("TRAFFICWATCH_CACHE", str(DEFAULT_CACHE))
    cfg = cfg or load_config()
    info = probe(str(video))
    scene = load_scene(cfg, info.width, info.height)
    return perceive(str(video), cfg, scene, profile), scene, cfg
