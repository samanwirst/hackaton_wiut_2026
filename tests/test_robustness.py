"""Regression tests for failure modes found on real traffic footage (live street cameras, highway
clips) and on the synthetic junction: boxes cut off by the frame border, queues and pass-bys that
look like contact, event boundaries, and inputs the harness must survive."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from synthetic import CAR, FPS, H, STRIDE, W, make_context, path_rows

from trafficwatch.detector import Detections
from trafficwatch.events import RULES
from trafficwatch.geometry import polygon_mask
from trafficwatch.risk import CausalRisk
from trafficwatch.scene import Scene, StopLine
from trafficwatch.signal import SignalTimeline

BUS = 5
ROAD = [[0, 100], [W, 100], [W, 719], [0, 719]]


def road_scene(**kw) -> Scene:
    return Scene(W, H, road_mask=polygon_mask(ROAD, W, H), road_source="config", **kw)


def _signal(red_from: float, red_to: float, duration: float) -> SignalTimeline:
    times = np.arange(0, duration, STRIDE / FPS)
    return SignalTimeline(times, ["red" if red_from <= t < red_to else "green" for t in times])


def _exiting_rows(tid: int, x: float, y0: float, speed: float, t_end: float, size=(80, 50)) -> np.ndarray:
    """A car driving down the image and out of the bottom: once it reaches the border the
    detector's box is clipped there, so its bottom edge (the ground point) stops moving."""
    w, h = size
    rows = []
    for f in range(0, int(t_end * FPS) + 1, STRIDE):
        y = y0 + speed * f / FPS
        if y - h >= H - 1:
            break
        rows.append([f, tid, x - w / 2, y - h, x + w / 2, min(y, H - 1), 0.9, CAR])
    return np.array(rows)


# -- signal rules ---------------------------------------------------------------------------------
def test_red_light_lasts_until_the_car_leaves_the_junction():
    sl = StopLine("sl1", np.array([0.0, 450.0]), np.array([W, 450.0]), np.array([0.0, -1.0]), "tl1")
    junction = polygon_mask([[0, 150], [W, 150], [W, 400], [0, 400]], W, H)
    scene = road_scene(stop_lines=[sl], intersection_mask=junction)
    runner = path_rows(1, CAR, [(0, 640, 700), (6, 640, 100)])     # enters the box at 3.0 s, leaves at 5.5 s
    ev = RULES["red_light"](make_context([runner], 8, scene, signals={"tl1": _signal(1.0, 8.0, 8)}))
    assert len(ev) == 1
    assert 1.8 < ev[0].start < 2.6 and 5.0 < ev[0].end < 6.0


def test_stopping_over_the_line_is_a_stop_line_case_not_a_red_light():
    sl = StopLine("sl1", np.array([0.0, 450.0]), np.array([W, 450.0]), np.array([0.0, -1.0]), "tl1")
    junction = polygon_mask([[0, 150], [W, 150], [W, 400], [0, 400]], W, H)
    scene = road_scene(stop_lines=[sl], intersection_mask=junction)
    # moving away from the camera, halts with its front over the line, goes on at green
    car = path_rows(1, CAR, [(0, 640, 700), (2, 640, 440), (12, 640, 440), (14, 640, 100)])
    ctx = make_context([car], 16, scene, signals={"tl1": _signal(0.0, 11.0, 16)})
    stop = RULES["stop_line"](ctx)
    assert len(stop) == 1 and abs(stop[0].end - 11.0) < 0.2
    assert RULES["red_light"](ctx) == []


# -- frame border --------------------------------------------------------------------------------
def test_leaving_the_frame_is_not_a_stop_a_crash_or_a_near_miss():
    lead = _exiting_rows(1, 640, 350, 120, 12)
    follow = _exiting_rows(2, 640, 250, 120, 12)
    ctx = make_context([lead, follow], 12, road_scene())
    assert ctx.by_id[1].edge[-1] and not ctx.by_id[1].edge[0]
    for label in ("accident", "near_miss", "stopped_vehicle", "illegal_u_turn", "wrong_way"):
        assert RULES[label](ctx) == [], label


# -- accident ---------------------------------------------------------------------------------------
def test_braking_into_a_queue_is_not_an_accident():
    stopped = path_rows(1, CAR, [(0, 640, 300), (14, 640, 300)])
    braking = path_rows(2, CAR, [(0, 640, 700), (3, 640, 460), (6, 640, 370), (9, 640, 332), (14, 640, 330)])
    assert RULES["accident"](make_context([stopped, braking], 14, road_scene())) == []


def test_driving_past_a_stopped_bus_is_not_an_accident():
    bus = path_rows(1, BUS, [(0, 500, 400), (10, 500, 400)], size=(300, 170))
    car = path_rows(2, CAR, [(0, 100, 420), (2, 400, 420), (3, 440, 420), (4, 480, 420), (6, 900, 420)])
    assert RULES["accident"](make_context([bus, car], 10, road_scene())) == []


def test_rear_end_seen_along_the_road_is_an_accident():
    # the follower keeps its speed up to the stopped car and is stopped short by the impact; their
    # ground points end up ~0.9 object sizes apart, as a rear-end looks from an elevated camera
    stopped = path_rows(1, CAR, [(0, 640, 300), (14, 640, 300)])
    striker = path_rows(2, CAR, [(0, 640, 700), (5.0, 640, 360), (5.25, 640, 357), (14, 640, 357)])
    ev = RULES["accident"](make_context([stopped, striker], 14, road_scene()))
    assert len(ev) == 1 and 4.0 < ev[0].start < 5.4


# -- stopped vehicle ----------------------------------------------------------------------------------
def test_cars_ahead_driving_off_at_green_is_not_traffic_flowing_past():
    queue = [path_rows(i, CAR, [(0, 100 + 110 * i, 560), (4, 680 + 110 * i, 560), (20 + i, 680 + 110 * i, 560),
                                (24 + i, W, 560)]) for i in range(3)]
    ctx = make_context(queue, 28, road_scene())
    assert RULES["stopped_vehicle"](ctx) == []


# -- Part B ---------------------------------------------------------------------------------------------
def _risk(frames: list[list[list[float]]], size=(W, H)) -> np.ndarray:
    est = CausalRisk()
    est.reset({"fps": FPS, "width": size[0], "height": size[1]}, stride=1)
    out = []
    for i, boxes in enumerate(frames):
        b = np.array(boxes, dtype=float).reshape(-1, 4)
        out.append(est.update(Detections(b, np.full(len(b), 0.9), np.full(len(b), 2.0)), i * STRIDE / FPS))
    return np.array(out)


def test_risk_ignores_a_car_frozen_at_the_frame_border():
    frames = []
    for i in range(60):
        t = i * STRIDE / FPS
        lead_y, follow_y = min(500 + 200 * t, H - 1), 380 + 200 * t     # the lead is clipped at the bottom
        frames.append([[600, lead_y - 50, 680, lead_y], [600, follow_y - 50, 680, follow_y]])
    assert _risk(frames).max() < 0.3


def _following(speed_a: float, speed_b: float) -> list[list[list[float]]]:
    """Two cars in one lane driving away from a camera looking along the road (pinhole over a
    flat ground: image row - horizon ~ 1/distance, size ~ 1/distance), 25 and 35 m away at first."""
    frames = []
    for i in range(60):
        t = i * STRIDE / FPS
        boxes = []
        for dist in (25 + speed_a * t, 35 + speed_b * t):
            y, s = 100 + 8000 / dist, 1200 / dist
            boxes.append([960 - s / 2, y - 0.6 * s, 960 + s / 2, y])
        frames.append(boxes)
    return frames


def test_risk_ignores_cars_following_at_the_same_pace():
    # the nearer car moves much faster in pixels and seems to close in on the other
    assert _risk(_following(8.0, 8.0), size=(1920, 1080)).max() < 0.3


def test_risk_rises_when_the_follower_is_much_faster():
    assert _risk(_following(14.0, 4.0), size=(1920, 1080)).max() >= 0.5


# -- submission interface ------------------------------------------------------------------------------------
def test_solution_survives_unreadable_videos_and_bad_frames(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import solution

    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    assert solution.detect_events(str(broken)) == []
    est = solution.RiskEstimator()
    est.reset({"video_id": "x", "fps": None, "width": None, "height": None, "n_frames": 0})
    for frame in (np.zeros((720, 1280, 3), np.uint8), np.zeros((10, 10), np.uint8), None):
        p = est.step(frame, 0.0)
        assert isinstance(p, float) and 0.0 <= p <= 1.0

