"""Shared types for the event rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np

from ..config import rule_params
from ..detector import paired_overlap
from ..perception import Perception
from ..scene import Scene
from ..signal import SignalTimeline, derive_signals
from ..tracks import Track


@dataclass
class Event:
    start: float
    end: float
    label: str
    score: float = 1.0
    tracks: tuple[int, ...] = ()
    info: dict = field(default_factory=dict)

    def as_list(self) -> list:
        return [round(float(self.start), 2), round(float(self.end), 2), self.label]


class Context:
    """Everything a rule may look at, with cached derived views."""

    def __init__(self, perception: Perception, scene: Scene, cfg: dict):
        self.perception = perception
        self.scene = scene
        self.cfg = cfg
        self.info = perception.info
        self.fps = perception.info.fps
        self.dt = perception.dt
        self.duration = perception.info.duration
        self.heading_min = cfg.get("kinematics", {}).get("heading_min_nspeed", 0.3)

    def params(self, label: str) -> dict:
        return rule_params(self.cfg, label)

    def px(self, v: float) -> int:
        """A pixel margin from the config (tuned on 1280-pixel-wide video) at this video's size."""
        return int(round(float(v) * max(self.info.width, 1) / 1280.0))

    # -- track views ----------------------------------------------------------------------
    @cached_property
    def tracks(self) -> list[Track]:
        """Tracks outside the ignore zones."""
        keep = []
        for tr in self.perception.tracks:
            if self.scene.ignored(tr.gp).mean() < 0.5:
                keep.append(tr)
        return keep

    @cached_property
    def by_id(self) -> dict[int, Track]:
        return {tr.tid: tr for tr in self.tracks}

    @cached_property
    def vehicles(self) -> list[Track]:
        return [tr for tr in self.tracks if tr.is_vehicle]

    @cached_property
    def pedestrians(self) -> list[Track]:
        """Person tracks that are not riders of a bicycle / motorcycle."""
        thr = self.params("jaywalking").get("rider_overlap", 0.35)
        bikes = [tr for tr in self.tracks if tr.category == "two_wheeler"]
        out = []
        for p in (tr for tr in self.tracks if tr.category == "person"):
            riding = np.zeros(len(p.t), dtype=bool)
            for b in bikes:
                ia, ib = self.common(p, b)
                if len(ia):
                    riding[ia] |= paired_overlap(p.box[ia], b.box[ib], mode="min") > thr
            if riding.mean() < 0.5:
                out.append(p)
        return out

    def frame_index(self, tr: Track) -> np.ndarray:
        return np.round(tr.t * self.fps).astype(np.int64)

    def common(self, a: Track, b: Track) -> tuple[np.ndarray, np.ndarray]:
        """Indices into a and b of the processed frames where both tracks exist."""
        if a.t1 < b.t0 or b.t1 < a.t0:
            return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
        _, ia, ib = np.intersect1d(self.frame_index(a), self.frame_index(b), return_indices=True)
        return ia, ib

    @cached_property
    def time_table(self) -> dict[int, list[tuple[int, int]]]:
        """frame index -> [(track position in self.tracks, row in that track)]."""
        table: dict[int, list[tuple[int, int]]] = {}
        for k, tr in enumerate(self.tracks):
            for j, f in enumerate(self.frame_index(tr)):
                table.setdefault(int(f), []).append((k, j))
        return table

    def close_pairs(self, max_dist_scale: float, categories=("vehicle", "two_wheeler", "person"),
                    need_vehicle: bool = True) -> dict[tuple[int, int], np.ndarray]:
        """Pairs of tracks that come within ``max_dist_scale`` object sizes of each other.
        Returns {(k_a, k_b): frame indices where they are that close}."""
        out: dict[tuple[int, int], list[int]] = {}
        for f, members in self.time_table.items():
            members = [(k, j) for k, j in members if self.tracks[k].category in categories]
            if len(members) < 2:
                continue
            ks = np.array([m[0] for m in members])
            pts = np.array([self.tracks[k].gp[j] for k, j in members])
            sc = np.array([self.tracks[k].scale[j] for k, j in members])
            d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
            dn = d / (0.5 * (sc[:, None] + sc[None, :]))
            ii, jj = np.nonzero(np.triu(dn < max_dist_scale, k=1))
            for a, b in zip(ii, jj):
                ka, kb = int(ks[a]), int(ks[b])
                if need_vehicle and not (self.tracks[ka].is_vehicle or self.tracks[kb].is_vehicle):
                    continue
                key = (min(ka, kb), max(ka, kb))
                out.setdefault(key, []).append(f)
        return {k: np.array(sorted(v)) for k, v in out.items()}

    # -- scene views ----------------------------------------------------------------------
    @cached_property
    def signals(self) -> dict[str, SignalTimeline]:
        """Measured light timelines plus the signals derived from them (scene.json ``signals``)."""
        return derive_signals(self.scene.signal_specs, self.perception.signals)

    def dilated(self, label_map: np.ndarray | None, px: int) -> np.ndarray | None:
        """Label map grown by ``px`` pixels (used for crosswalk margins)."""
        if label_map is None or px <= 0:
            return label_map
        kernel = np.ones((2 * px + 1, 2 * px + 1), np.uint8)
        grown = cv2.dilate((label_map + 1).astype(np.uint8), kernel)
        return grown.astype(np.int16) - 1

    def eroded_road(self, px: int) -> np.ndarray | None:
        if self.scene.road_mask is None or px <= 0:
            return self.scene.road_mask
        kernel = np.ones((2 * px + 1, 2 * px + 1), np.uint8)
        return cv2.erode(self.scene.road_mask.astype(np.uint8), kernel).astype(bool)
