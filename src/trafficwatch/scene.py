"""Scene geometry: the hand-made layout of a camera (configs/scene_tashkent.json) plus what we learned
from its sample videos (configs/scene_model_tashkent.npz: drivable-area mask and direction field).

Every field is optional. A rule that needs geometry that is missing simply does not fire, so the
pipeline runs (with fewer classes) before the scene has been annotated. See docs/scene.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .config import resolve
from .direction_field import DirectionField
from .geometry import lookup, polygon_mask


@dataclass
class StopLine:
    id: str
    a: np.ndarray
    b: np.ndarray
    forward: np.ndarray          # unit vector: direction of travel when crossing into the junction
    light: str | None = None


@dataclass
class Scene:
    width: int
    height: int
    road_mask: np.ndarray | None = None        # carriageway
    road_source: str = "none"                  # "config" | "learned" | "none"
    ignore_mask: np.ndarray | None = None
    parking_mask: np.ndarray | None = None
    intersection_mask: np.ndarray | None = None
    uturn_ok_mask: np.ndarray | None = None
    uturn_prohibited_mask: np.ndarray | None = None
    crosswalk_map: np.ndarray | None = None    # int16 label map, -1 = none
    crosswalk_ids: list[str] = field(default_factory=list)
    crosswalk_signals: list[str | None] = field(default_factory=list)   # pedestrian signal per crossing
    crosswalk_polys: list[np.ndarray] = field(default_factory=list)
    zone_map: np.ndarray | None = None
    zone_ids: list[str] = field(default_factory=list)
    lane_map: np.ndarray | None = None
    lanes: list[dict] = field(default_factory=list)
    group_map: np.ndarray | None = None
    group_ids: list[str] = field(default_factory=list)
    stop_lines: list[StopLine] = field(default_factory=list)
    lights: dict[str, list[int]] = field(default_factory=dict)   # id -> roi [x1, y1, x2, y2]
    light_specs: dict[str, dict] = field(default_factory=dict)   # id -> {roi, kind, lamps}
    signal_specs: list[dict] = field(default_factory=list)       # derived signals (signal.derive_signals)
    solid_lines: list[np.ndarray] = field(default_factory=list)
    prohibited_movements: set[tuple[str, str]] = field(default_factory=set)
    flow_field: DirectionField | None = None
    raw: dict = field(default_factory=dict)

    # -- queries ---------------------------------------------------------------------------
    @property
    def has_road(self) -> bool:
        return self.road_mask is not None

    def on_road(self, pts: np.ndarray) -> np.ndarray:
        if self.road_mask is None:
            return np.ones(len(np.asarray(pts).reshape(-1, 2)), dtype=bool)
        return lookup(self.road_mask, pts, outside=False)

    def ignored(self, pts: np.ndarray) -> np.ndarray:
        return self._in(self.ignore_mask, pts)

    def in_parking(self, pts: np.ndarray) -> np.ndarray:
        return self._in(self.parking_mask, pts)

    def in_intersection(self, pts: np.ndarray) -> np.ndarray:
        return self._in(self.intersection_mask, pts)

    def uturn_allowed(self, pts: np.ndarray) -> np.ndarray:
        return self._in(self.uturn_ok_mask, pts)

    def uturn_prohibited(self, pts: np.ndarray) -> np.ndarray:
        return self._in(self.uturn_prohibited_mask, pts) & ~self.uturn_allowed(pts)

    def crosswalk_at(self, pts: np.ndarray) -> np.ndarray:
        return self._label(self.crosswalk_map, pts)

    def zone_at(self, pts: np.ndarray) -> np.ndarray:
        return self._label(self.zone_map, pts)

    def lane_at(self, pts: np.ndarray) -> np.ndarray:
        return self._label(self.lane_map, pts)

    def group_at(self, pts: np.ndarray) -> np.ndarray:
        return self._label(self.group_map, pts)

    @staticmethod
    def _in(mask: np.ndarray | None, pts: np.ndarray) -> np.ndarray:
        n = len(np.asarray(pts).reshape(-1, 2))
        if mask is None:
            return np.zeros(n, dtype=bool)
        return lookup(mask, pts, outside=False)

    @staticmethod
    def _label(label_map: np.ndarray | None, pts: np.ndarray) -> np.ndarray:
        n = len(np.asarray(pts).reshape(-1, 2))
        if label_map is None:
            return np.full(n, -1, dtype=np.int16)
        return lookup(label_map, pts, outside=-1)


def _label_map(items: list, key: str, width: int, height: int) -> tuple[np.ndarray | None, list[str]]:
    if not items:
        return None, []
    m = np.full((height, width), -1, dtype=np.int16)
    ids = []
    for i, item in enumerate(items):
        m[polygon_mask(item[key], width, height)] = i
        ids.append(str(item.get("id", i)))
    return m, ids


def _scale_coords(obj, sx: float, sy: float):
    """Recursively scale [x, y] pairs (used when the video size differs from the annotated one)."""
    if isinstance(obj, list):
        if len(obj) == 2 and all(isinstance(v, (int, float)) for v in obj):
            return [obj[0] * sx, obj[1] * sy]
        if len(obj) == 4 and all(isinstance(v, (int, float)) for v in obj):
            return [obj[0] * sx, obj[1] * sy, obj[2] * sx, obj[3] * sy]
        return [_scale_coords(v, sx, sy) for v in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("forward", "direction", "id", "light", "allowed_turns", "registration") else
                    _scale_coords(v, sx, sy)) for k, v in obj.items()}
    return obj


def _frame_size(path: Path | None) -> tuple[int, int] | None:
    if path is None or not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            fs = json.load(f).get("frame_size")
        return (int(fs[0]), int(fs[1])) if fs else None
    except (OSError, ValueError, TypeError, IndexError):
        return None


def pick_camera(scfg: dict, width: int, height: int) -> tuple[str, str]:
    """(scene.json, scene model) for a video of this size. ``scene.cameras`` lists the layouts of
    known cameras; the one annotated at exactly this size wins, then one with the same aspect ratio
    (a downscaled copy of the video), otherwise the default ``scene.config`` / ``scene.model``."""
    default = (scfg.get("config") or "", scfg.get("model") or "")
    cams = [(c["config"], c.get("model", "")) for c in scfg.get("cameras", []) or []]
    sizes = [_frame_size(resolve(c[0])) for c in cams]
    default_size = _frame_size(resolve(default[0])) if default[0] else None
    for cam, fs in zip(cams + [default], sizes + [default_size]):
        if fs == (width, height):
            return cam
    if width and height:
        for cam, fs in zip(cams, sizes):
            if fs and abs(fs[0] / fs[1] - width / height) < 0.01:
                return cam
    return default


def load_scene(cfg: dict, width: int, height: int, frame: np.ndarray | None = None) -> Scene:
    scfg = cfg.get("scene", {})
    config_path, model_path = pick_camera(scfg, width, height)
    raw: dict = {}
    path = resolve(config_path) if config_path else None
    if path is not None and path.is_file():
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        fw, fh = raw.get("frame_size", [width, height])
        if fw and fh and (fw, fh) != (width, height):
            raw = _scale_coords(raw, width / fw, height / fh)
    if frame is not None and raw.get("registration", {}).get("reference"):
        from .registration import estimate_registration, transform_layout

        reference = resolve(raw["registration"]["reference"])
        matrix, evidence = estimate_registration(reference, frame)
        if matrix is None:
            # A different camera or an unreadable reference view must not inherit these ROIs.
            return Scene(width=width, height=height, raw={"_registration": evidence})
        raw = transform_layout(raw, matrix)
        raw["_registration"] = evidence
    scene = Scene(width=width, height=height, raw=raw)

    if raw.get("road"):
        scene.road_mask = polygon_mask(raw["road"], width, height)
        if raw.get("road_exclude"):          # medians, islands and pavement inside the road outline
            scene.road_mask &= ~polygon_mask(raw["road_exclude"], width, height)
        scene.road_source = "config"
    for key, attr in (("ignore", "ignore_mask"), ("parking", "parking_mask"),
                      ("intersection", "intersection_mask"), ("u_turn_allowed", "uturn_ok_mask"),
                      ("u_turn_prohibited", "uturn_prohibited_mask")):
        if raw.get(key):
            setattr(scene, attr, polygon_mask(raw[key], width, height))
    scene.crosswalk_map, scene.crosswalk_ids = _label_map(raw.get("crosswalks", []), "polygon", width, height)
    scene.crosswalk_signals = [cw.get("signal") for cw in raw.get("crosswalks", [])]
    scene.crosswalk_polys = [np.asarray(cw["polygon"], dtype=np.float64) for cw in raw.get("crosswalks", [])]
    scene.zone_map, scene.zone_ids = _label_map(raw.get("zones", []), "polygon", width, height)
    scene.lanes = raw.get("lanes", [])
    scene.lane_map, _ = _label_map(scene.lanes, "polygon", width, height)
    scene.group_map, scene.group_ids = _label_map(raw.get("direction_groups", []), "polygon", width, height)
    for sl in raw.get("stop_lines", []):
        fwd = np.asarray(sl.get("forward", [0, -1]), dtype=np.float64)
        scene.stop_lines.append(StopLine(
            id=str(sl.get("id", len(scene.stop_lines))), a=np.asarray(sl["line"][0], float),
            b=np.asarray(sl["line"][1], float), forward=fwd / (np.hypot(*fwd) + 1e-9),
            light=sl.get("light")))
    scene.lights = {str(tl["id"]): [int(round(v)) for v in tl["roi"]] for tl in raw.get("traffic_lights", [])}
    scene.light_specs = {str(tl["id"]): {"roi": scene.lights[str(tl["id"])], "kind": tl.get("kind", "vehicle"),
                                         "lamps": tl.get("lamps")} for tl in raw.get("traffic_lights", [])}
    scene.signal_specs = list(raw.get("signals", []))
    scene.solid_lines = [np.asarray(s["polyline"], dtype=np.float64) for s in raw.get("solid_lines", [])]
    scene.prohibited_movements = {(str(a), str(b)) for a, b in raw.get("prohibited_movements", [])}

    model_path = resolve(model_path) if model_path else None
    if model_path is not None and Path(model_path).exists():
        z = np.load(model_path)
        if scene.road_mask is None and "road_mask" in z:
            rm = z["road_mask"].astype(np.uint8)
            scene.road_mask = cv2.resize(rm, (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)
            scene.road_source = "learned"
        if "counts" in z:
            fw, fh = int(z["width"]), int(z["height"])
            df = DirectionField(z["counts"], fw, fh)
            if (fw, fh) != (width, height):
                df = DirectionField(z["counts"], width, height)
            scene.flow_field = df
    return scene


def load_video_scene(cfg: dict, video_path: str, width: int, height: int) -> Scene:
    """Part A only: align hand-drawn geometry to a representative middle frame.

    The midpoint avoids brief start-of-recording camera settling seen in the samples. Part A
    explicitly permits random access. This is static image matching, never a filename rule.

    Part B never calls this helper or opens a file. Its independent learned direction field
    remains in its original pixel coordinates and is not changed by hand-layout registration.
    """
    config_path, _ = pick_camera(cfg.get("scene", {}), width, height)
    path = resolve(config_path) if config_path else None
    if path is None or not path.is_file():
        return load_scene(cfg, width, height)
    with path.open(encoding="utf-8") as stream:
        registered = bool(json.load(stream).get("registration", {}).get("reference"))
    if not registered:
        return load_scene(cfg, width, height)
    cap = cv2.VideoCapture(video_path)
    try:
        middle = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
        cap.set(cv2.CAP_PROP_POS_FRAMES, middle)
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read a frame for scene registration: {video_path}")
    return load_scene(cfg, width, height, frame=frame)
