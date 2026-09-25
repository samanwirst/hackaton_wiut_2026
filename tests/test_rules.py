"""Scenario tests for the event rules on synthetic trajectories."""
from __future__ import annotations

import numpy as np
from synthetic import CAR, FPS, H, MOTORBIKE, PERSON, W, make_context, path_rows

from trafficwatch.direction_field import DirectionField
from trafficwatch.events import RULES
from trafficwatch.geometry import polygon_mask
from trafficwatch.scene import Scene, StopLine
from trafficwatch.signal import SignalTimeline
from trafficwatch.tracks import build_tracks

ROAD = [[0, 300], [W, 300], [W, 600], [0, 600]]


def road_scene(**kw) -> Scene:
    return Scene(W, H, road_mask=polygon_mask(ROAD, W, H), road_source="config", **kw)


def passing_cars(n: int, t0: float, gap: float, y: float, first_id: int = 100) -> list[np.ndarray]:
    return [path_rows(first_id + i, CAR, [(t0 + i * gap, 0, y), (t0 + i * gap + 6, W, y)]) for i in range(n)]


# -- stopped_vehicle --------------------------------------------------------------------------
def test_stopped_vehicle_with_traffic_passing():
    stopped = path_rows(1, CAR, [(0, 100, 560), (4, 500, 560), (24, 500, 560), (28, 1000, 560)])
    ctx = make_context([stopped] + passing_cars(6, 5, 2.5, 470), 40, road_scene())
    ev = RULES["stopped_vehicle"](ctx)
    assert len(ev) == 1
    assert abs(ev[0].start - 4.0) < 0.8 and abs(ev[0].end - 24.0) < 0.8


def test_queue_is_not_a_stopped_vehicle():
    queue = [path_rows(i, CAR, [(0, 300 + 110 * i, 560), (15, 300 + 110 * i, 560), (20, 900 + 110 * i, 560)])
             for i in range(4)]
    ctx = make_context(queue, 25, road_scene())
    assert RULES["stopped_vehicle"](ctx) == []


# -- jaywalking ---------------------------------------------------------------------------------
def test_jaywalking_outside_but_not_inside_crosswalk():
    scene = road_scene(crosswalk_map=None)
    cw = np.full((H, W), -1, np.int16)
    cw[polygon_mask([[800, 300], [900, 300], [900, 600], [800, 600]], W, H)] = 0
    scene.crosswalk_map = cw
    outside = path_rows(1, PERSON, [(0, 400, 280), (2, 400, 320), (10, 400, 620)], size=(20, 50))
    inside = path_rows(2, PERSON, [(0, 850, 280), (2, 850, 320), (10, 850, 620)], size=(20, 50))
    ev = RULES["jaywalking"](make_context([outside, inside], 12, scene))
    assert len(ev) == 1 and ev[0].tracks == (1,)
    assert 1.0 < ev[0].start < 3.5 and 8.0 < ev[0].end < 10.5


def test_rider_is_not_a_pedestrian():
    bike = path_rows(1, MOTORBIKE, [(0, 0, 450), (8, W, 450)], size=(60, 40))
    rider = path_rows(2, PERSON, [(0, 0, 440), (8, W, 440)], size=(30, 60))
    ctx = make_context([bike, rider], 10, road_scene())
    assert RULES["jaywalking"](ctx) == []


# -- wrong_way ----------------------------------------------------------------------------------
def test_wrong_way_against_learned_direction_field():
    history = passing_cars(40, 0, 1.0, 400) + [path_rows(300 + i, CAR, [(i, W, 520), (i + 6, 0, 520)])
                                               for i in range(40)]
    field_tracks = build_tracks(np.concatenate(history), FPS, 2)
    field = DirectionField.learn([field_tracks], W, H)
    scene = road_scene(flow_field=field)
    rogue = path_rows(1, CAR, [(0, W, 400), (6, 0, 400)])      # upper lane, driving left
    ok_car = path_rows(2, CAR, [(0, 0, 400), (6, W, 400)])     # upper lane, driving right
    ev = RULES["wrong_way"](make_context([rogue, ok_car], 8, scene))
    assert len(ev) == 1 and ev[0].tracks == (1,)
    assert ev[0].end - ev[0].start > 3.0


# -- red_light / stop_line -------------------------------------------------------------------------
def _signal(red_from: float, red_to: float, duration: float) -> SignalTimeline:
    times = np.arange(0, duration, 2 / FPS)
    states = ["red" if red_from <= t < red_to else "green" for t in times]
    return SignalTimeline(times, states)


def test_red_light_runner():
    sl = StopLine("sl1", np.array([0.0, 450.0]), np.array([W, 450.0]), np.array([0.0, -1.0]), "tl1")
    scene = road_scene(stop_lines=[sl])
    runner = path_rows(1, CAR, [(0, 640, 700), (6, 640, 200)])           # crosses y=450 at t=3.0
    ctx = make_context([runner], 8, scene, signals={"tl1": _signal(1.0, 8.0, 8)})
    ev = RULES["red_light"](ctx)
    assert len(ev) == 1 and 2.0 < ev[0].start < 3.3
    ctx_green = make_context([runner], 8, scene, signals={"tl1": _signal(6.0, 8.0, 8)})
    assert RULES["red_light"](ctx_green) == []


def test_stop_line_violation_ends_at_green():
    sl = StopLine("sl1", np.array([0.0, 450.0]), np.array([W, 450.0]), np.array([0.0, -1.0]), "tl1")
    scene = road_scene(stop_lines=[sl])
    car = path_rows(1, CAR, [(0, 640, 700), (2, 640, 430), (12, 640, 430), (14, 640, 200)])
    ctx = make_context([car], 16, scene, signals={"tl1": _signal(0.0, 11.0, 16)})
    ev = RULES["stop_line"](ctx)
    assert len(ev) == 1 and abs(ev[0].end - 11.0) < 0.2


# -- accident / near_miss -----------------------------------------------------------------------------
def test_accident_contact_then_stop():
    a = path_rows(1, CAR, [(0, 100, 500), (3, 600, 500), (3.6, 640, 500), (12, 640, 500)])
    b = path_rows(2, CAR, [(0, 1200, 500), (3, 700, 500), (3.6, 668, 500), (12, 668, 500)])
    ev = RULES["accident"](make_context([a, b], 14, road_scene()))
    assert len(ev) == 1
    assert 2.6 < ev[0].start < 3.6 and ev[0].end > ev[0].start


def test_normal_passing_is_not_an_accident():
    a = path_rows(1, CAR, [(0, 0, 400), (8, W, 400)])
    b = path_rows(2, CAR, [(0, W, 520), (8, 0, 520)])
    assert RULES["accident"](make_context([a, b], 10, road_scene())) == []


def test_near_miss_hard_braking_without_contact():
    ped = path_rows(1, PERSON, [(0, 640, 300), (8, 640, 600)], size=(20, 50))    # crossing down
    car = path_rows(2, CAR, [(0, 0, 452), (2.4, 470, 452), (3.4, 540, 452), (7, 540, 452), (9, 1200, 452)])
    ev = RULES["near_miss"](make_context([ped, car], 10, road_scene()))
    assert len(ev) == 1
    assert 1.5 < ev[0].start < 3.5


# -- u-turn -----------------------------------------------------------------------------------------
def test_illegal_u_turn():
    ang = np.linspace(-np.pi / 2, np.pi / 2, 20)
    keys = [(0, 100, 400), (4, 600, 400)]
    keys += [(4 + 4 * (k + 1) / 20, 600 + 80 * np.cos(a), 480 + 80 * np.sin(a)) for k, a in enumerate(ang)]
    keys += [(12, 100, 560)]
    ev = RULES["illegal_u_turn"](make_context([path_rows(1, CAR, keys)], 14, road_scene()))
    assert len(ev) == 1 and 3.0 < ev[0].start < 5.5 and 7.0 < ev[0].end < 9.5


# -- congestion ---------------------------------------------------------------------------------
def test_congestion_when_a_queue_stands_still():
    cars = [path_rows(10 + i, CAR, [(0, 150 + 130 * i, 560), (5, 450 + 130 * i, 560), (45, 450 + 130 * i, 560),
                                     (50, 1050 + 130 * i, 560)]) for i in range(5)]
    ev = RULES["congestion"](make_context(cars, 55, road_scene()))
    assert len(ev) == 1 and 4.0 < ev[0].start < 8.0 and 43.0 < ev[0].end < 48.0


def test_parked_cars_are_not_congestion():
    parked = [path_rows(10 + i, CAR, [(0, 150 + 130 * i, 560), (60, 150 + 130 * i, 560)]) for i in range(5)]
    assert RULES["congestion"](make_context(parked, 60, road_scene())) == []
