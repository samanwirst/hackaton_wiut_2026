"""Pixel-level signal regressions independent of video names and scene layout."""
import cv2
import numpy as np
import pytest
import synthetic  # noqa: F401 — repository source bootstrap

from trafficwatch.signal import UNKNOWN, lamp_scores, read_light

LAMPS = {"red": [0, 0, 10, 10], "amber": [0, 10, 10, 20], "green": [0, 20, 10, 30]}


def patch(frame, name, hsv):
    x1, y1, x2, y2 = LAMPS[name]
    frame[y1:y2, x1:x2] = cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2BGR)[0, 0]


@pytest.mark.parametrize("name,hue", [("red", 0), ("red", 175), ("amber", 25), ("green", 85)])
def test_dim_daylight_lamp_uses_expected_hue(name, hue):
    frame = np.zeros((30, 10, 3), np.uint8)
    patch(frame, name, (hue, 220, 90))
    assert read_light(frame, {"lamps": LAMPS}) == name


def test_reflection_in_an_unlit_lamp_does_not_override_dim_red():
    frame = np.zeros((30, 10, 3), np.uint8)
    patch(frame, "red", (0, 220, 90))
    patch(frame, "green", (110, 220, 250))  # blue vehicle behind the head
    assert lamp_scores(frame, LAMPS)["green"] == 0
    assert read_light(frame, {"lamps": LAMPS}) == "red"


@pytest.mark.parametrize("hsv", [(0, 0, 255), (0, 255, 30), (85, 255, 30)])
def test_white_headlight_or_dark_lamp_is_unknown(hsv):
    frame = np.zeros((30, 10, 3), np.uint8)
    for name in LAMPS:
        patch(frame, name, hsv)
    assert read_light(frame, {"lamps": LAMPS}) == UNKNOWN


def test_invalid_or_off_frame_lamp_is_unknown():
    frame = np.zeros((30, 10, 3), np.uint8)
    assert read_light(frame, {"lamps": {"red": [100, 100, 110, 110]}}) == UNKNOWN
