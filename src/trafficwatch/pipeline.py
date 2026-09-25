"""Part A pipeline: perception pass -> event rules -> segment post-processing."""
from __future__ import annotations

import hashlib
import os
import pickle
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import CLASSES
from .config import load_config
from .events import RULES, Context, Event
from .perception import Perception, run_perception
from .runtime import set_determinism
from .scene import Scene, load_scene
from .segments import postprocess
from .video import probe


@dataclass
class Result:
    events: list[list]                 # final [[start, end, label], ...]
    raw_events: list[Event]            # rule firings before post-processing (with track ids)
    perception: Perception
    scene: Scene
    timings: dict = field(default_factory=dict)


PERCEPTION_VERSION = 3      # bump when what a Perception / Track holds changes (invalidates caches)


def _cache_path(video_path: str, profile: str | None, scene: Scene | None = None) -> Path | None:
    """Developer cache for perception results (set TRAFFICWATCH_CACHE=dir). Never used by default.
    The key covers the file, the profile and the signal ROIs (the light states are read there)."""
    root = os.environ.get("TRAFFICWATCH_CACHE")
    if not root:
        return None
    st = os.stat(video_path)
    lights = sorted((k, v.get("roi"), v.get("lamps")) for k, v in scene.light_specs.items()) if scene is not None else []
    key = (f"v{PERCEPTION_VERSION}:{Path(video_path).name}:{st.st_size}:{int(st.st_mtime)}:"
           f"{profile or os.environ.get('TRAFFICWATCH_PROFILE', 'auto')}:{lights}")
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return Path(root) / f"{Path(video_path).stem}_{digest}.pkl"


def perceive(video_path: str, cfg: dict, scene: Scene, profile: str | None = None,
             progress: Callable[[float], None] | None = None) -> Perception:
    cache = _cache_path(video_path, profile, scene)
    if cache is not None and cache.exists():
        with open(cache, "rb") as f:
            return pickle.load(f)
    perception = run_perception(video_path, cfg, scene, profile, progress)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "wb") as f:
            pickle.dump(perception, f)
    return perception


def enabled_rules(cfg: dict) -> list[str]:
    return [c for c in CLASSES if cfg.get("rules", {}).get(c, {}).get("enabled", False)]


def analyze(video_path: str, cfg: dict | None = None, profile: str | None = None,
            progress: Callable[[float], None] | None = None) -> Result:
    cfg = cfg or load_config()
    set_determinism(int(cfg.get("seed", 0)))
    info = probe(video_path)
    scene = load_scene(cfg, info.width, info.height)
    perception = perceive(video_path, cfg, scene, profile, progress)
    ctx = Context(perception, scene, cfg)
    raw: list[Event] = []
    timings = dict(perception.timings)
    for label in enabled_rules(cfg):
        t0 = time.perf_counter()
        try:
            raw.extend(RULES[label](ctx))
        except Exception:  # one faulty rule must not cost the other classes of this video
            print(f"[trafficwatch] rule {label} failed on {video_path}:\n{traceback.format_exc()}",
                  file=sys.stderr)
        timings[f"rule_{label}_s"] = time.perf_counter() - t0
    events = postprocess(raw, perception.info.duration, cfg, set(enabled_rules(cfg)))
    return Result(events=events, raw_events=raw, perception=perception, scene=scene, timings=timings)


def detect_events(video_path: str, cfg: dict | None = None) -> list[list]:
    return analyze(video_path, cfg).events
