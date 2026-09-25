"""Learned direction field: for each image cell, a histogram of vehicle headings.

Built from the sample videos (``tools/learn_scene.py``). It lets the rules ask "how usual is
this heading at this place?" without hand-drawing lanes, which is how wrong-way driving and
the lane directions for congestion are found.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


class DirectionField:
    def __init__(self, counts: np.ndarray, width: int, height: int):
        self.counts = counts.astype(np.float64)   # (gy, gx, K)
        self.gy, self.gx, self.k = counts.shape
        self.width, self.height = width, height
        sm = gaussian_filter(self.counts, sigma=(1.0, 1.0, 0.0), mode="nearest")
        # circular smoothing across neighbouring heading bins
        sm = 0.5 * sm + 0.25 * np.roll(sm, 1, axis=2) + 0.25 * np.roll(sm, -1, axis=2)
        self.total = sm.sum(axis=2)
        self.prob = sm / np.maximum(self.total[..., None], 1e-9)

    # -- construction ---------------------------------------------------------------------
    @classmethod
    def learn(cls, tracks_per_video, width: int, height: int, grid=(18, 32), k: int = 12,
              min_nspeed: float = 0.5) -> DirectionField:
        counts = np.zeros((grid[0], grid[1], k))
        tmp = cls(counts, width, height)
        for tracks in tracks_per_video:
            for tr in tracks:
                if not tr.is_vehicle:
                    continue
                ok = (tr.nspeed >= min_nspeed) & tr.reliable
                if ok.sum() == 0:
                    continue
                heads = np.arctan2(tr.vel[ok, 1], tr.vel[ok, 0])
                cy, cx = tmp.cell(tr.gp[ok])
                kb = tmp.bin(heads)
                np.add.at(counts, (cy, cx, kb), 1.0)
        return cls(counts, width, height)

    def save(self, path) -> None:
        np.savez_compressed(path, counts=self.counts, width=self.width, height=self.height)

    @classmethod
    def load(cls, path) -> DirectionField:
        z = np.load(path)
        return cls(z["counts"], int(z["width"]), int(z["height"]))

    # -- queries --------------------------------------------------------------------------
    def cell(self, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        cx = np.clip((pts[:, 0] / self.width * self.gx).astype(int), 0, self.gx - 1)
        cy = np.clip((pts[:, 1] / self.height * self.gy).astype(int), 0, self.gy - 1)
        return cy, cx

    def bin(self, headings: np.ndarray) -> np.ndarray:
        a = np.mod(np.asarray(headings, dtype=np.float64), 2 * np.pi)
        return np.minimum((a / (2 * np.pi) * self.k).astype(int), self.k - 1)

    def query(self, pts: np.ndarray, headings: np.ndarray):
        """Return (p_heading, count, p_opposite) for each point/heading pair."""
        cy, cx = self.cell(pts)
        kb = self.bin(headings)
        opp = (kb + self.k // 2) % self.k
        p = self.prob[cy, cx, kb]
        p_opp = self.prob[cy, cx, opp]
        return p, self.total[cy, cx], p_opp

    def dominant(self, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Dominant heading (radians) and its probability mass at each point."""
        cy, cx = self.cell(pts)
        pr = self.prob[cy, cx]                   # (N, K)
        kb = pr.argmax(axis=1)
        angles = (kb + 0.5) / self.k * 2 * np.pi
        return angles, pr[np.arange(len(kb)), kb]
