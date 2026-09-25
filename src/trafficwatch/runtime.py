"""Determinism and hardware profile selection."""
from __future__ import annotations

import os
import random

import numpy as np


def set_determinism(seed: int = 0) -> None:
    """Fix every seed we rely on. Two runs on one machine must give the same predictions."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:  # torch is optional for the pure-rule unit tests
        pass


def cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


def device_for(gpu_profile: bool) -> str:
    """Torch device of a profile. ``TRAFFICWATCH_DEVICE`` (e.g. ``mps``, ``cpu``) overrides it, so the
    GPU profile can be run on a machine without CUDA to reproduce the evaluation machine's output."""
    return os.environ.get("TRAFFICWATCH_DEVICE") or ("cuda:0" if gpu_profile else "cpu")


def pick_profile(cfg: dict, name: str | None = None) -> tuple[str, dict]:
    """Return (profile_name, profile_dict). ``auto`` means gpu if CUDA is present, else cpu."""
    name = name or os.environ.get("TRAFFICWATCH_PROFILE") or cfg.get("profile", "auto")
    if name == "auto":
        name = "gpu" if cuda_available() else "cpu"
    profile = dict(cfg["profiles"][name])
    profile["device"] = device_for(name == "gpu")
    if not profile["device"].startswith("cuda"):
        profile["half"] = False
    return name, profile


def stride_for(fps: float, target_fps: float) -> int:
    return max(1, int(round(fps / max(target_fps, 1e-6))))
