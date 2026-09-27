"""Camera registration uses image evidence, preserves metadata and rejects weak matches."""
from __future__ import annotations

import cv2
import numpy as np
import pytest
import synthetic  # noqa: F401  (adds src/ to the test import path)

from trafficwatch.registration import estimate_registration, transform_layout
from trafficwatch.scene import _scale_coords, load_scene


@pytest.fixture
def reference(tmp_path):
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, (360, 640), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (3, 3), .6)
    for i in range(40):
        xy = tuple(map(int, rng.integers([20, 20], [620, 340])))
        cv2.putText(image, str(i), xy, cv2.FONT_HERSHEY_SIMPLEX, .7, int(i * 5), 2)
    path = tmp_path / "reference.png"
    assert cv2.imwrite(str(path), image)
    return path, image


def test_registration_recovers_small_shift_and_rotation(reference):
    path, image = reference
    expected = cv2.getRotationMatrix2D((320, 180), 1.0, .99)
    expected[:, 2] += [12, -6]
    moved = cv2.warpAffine(image, expected, (640, 360))
    matrix, evidence = estimate_registration(path, moved)
    assert evidence["status"] == "accepted"
    corners = np.array([[0, 0], [639, 0], [639, 359], [0, 359]], dtype=float)
    actual = corners @ matrix[:, :2].T + matrix[:, 2]
    wanted = corners @ expected[:, :2].T + expected[:, 2]
    assert np.max(np.linalg.norm(actual - wanted, axis=1)) < 1.0


def test_registration_repeats_exactly_without_modifying_frame(reference):
    path, image = reference
    before = image.copy()
    first, _ = estimate_registration(path, image)
    second, _ = estimate_registration(path, image)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(image, before)


@pytest.mark.parametrize("kind", ["blank", "different_camera", "excessive_shift"])
def test_registration_rejects_unreliable_or_large_changes(reference, kind):
    path, image = reference
    if kind == "blank":
        frame = np.zeros_like(image)
    elif kind == "different_camera":
        frame = np.random.default_rng(321).integers(0, 256, image.shape, dtype=np.uint8)
    else:
        frame = cv2.warpAffine(image, np.float64([[1, 0, 100], [0, 1, 0]]), (640, 360))
    matrix, evidence = estimate_registration(path, frame)
    assert matrix is None and evidence["status"] == "rejected"


def test_geometry_transforms_ragged_polygons_boxes_and_directions_not_signal_timing():
    raw = {
        "frame_size": [640, 360],
        "road": [[[0, 0], [40, 0], [40, 30]], [[50, 50], [90, 50], [90, 90], [50, 90]]],
        "crosswalks": [{"id": "cw", "polygon": [[1, 1], [5, 1], [5, 4]]}],
        "stop_lines": [{"id": "sl", "line": [[1, 2], [3, 4]], "forward": [1, 0]}],
        "traffic_lights": [{"id": "tl", "roi": [10, 20, 30, 60], "lamps": {"red": [12, 21, 28, 29]}}],
        "signals": [{"id": "derived", "red_delay_s": 6.0}],
        "registration": {"reference": "fixed.png"},
    }
    moved = transform_layout(raw, np.float64([[1, 0, 10], [0, 1, -5]]))
    assert moved["road"][0][0] == [10, -5]
    assert moved["road"][1][-1] == [60, 85]
    assert moved["traffic_lights"][0]["roi"] == [20, 15, 40, 55]
    assert moved["traffic_lights"][0]["lamps"]["red"] == [22, 16, 38, 24]
    assert moved["stop_lines"][0]["forward"] == [1, 0]
    assert moved["signals"] == raw["signals"]
    assert moved["registration"] == raw["registration"]
    assert raw["road"][0][0] == [0, 0]  # caller's reference is not changed


def test_scaling_does_not_change_registration_metadata():
    raw = {"road": [[1, 2], [3, 4]], "registration": {"reference": "fixed.png", "size": [640, 360]}}
    scaled = _scale_coords(raw, 2, 2)
    assert scaled["road"] == [[2, 4], [6, 8]]
    assert scaled["registration"] == raw["registration"]


def test_rejected_camera_does_not_inherit_annotated_geometry(reference, tmp_path):
    import json
    path, _ = reference
    config = tmp_path / "camera.json"
    config.write_text(json.dumps({"frame_size": [640, 360], "road": [[0, 0], [639, 0], [639, 359]],
                                  "registration": {"reference": str(path)}}))
    scene = load_scene({"scene": {"config": str(config)}}, 640, 360, frame=np.zeros((360, 640, 3), np.uint8))
    assert scene.raw["_registration"]["status"] == "rejected"
    assert not scene.has_road and not scene.lights and scene.flow_field is None
