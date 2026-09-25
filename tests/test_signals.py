"""Derived signals, crossing against a red pedestrian signal, queues at a red signal, camera layouts."""
from __future__ import annotations

import json

import numpy as np
from synthetic import CAR, PERSON, W, H, make_context, path_rows

from trafficwatch.events import RULES
from trafficwatch.geometry import polygon_mask
from trafficwatch.scene import Scene, StopLine, pick_camera
from trafficwatch.signal import AMBER, GREEN, RED, UNKNOWN, SignalTimeline, derive_signals

ROAD = [[0, 300], [W, 300], [W, 600], [0, 600]]
CROSSING = [[800, 300], [900, 300], [900, 600], [800, 600]]


def timeline(spans: list[tuple[float, float, str]], step: float = 0.08) -> SignalTimeline:
    times = np.arange(0, spans[-1][1], step)
    states = [next(s for a, b, s in spans if a <= t < b) for t in times]
    return SignalTimeline(times, states, smooth_s=0)


# -- derived signals ----------------------------------------------------------------------------
def test_vehicle_signal_follows_the_parallel_pedestrian_signal():
    ped = timeline([(0, 10, RED), (10, 20, GREEN), (20, 30, RED)])
    veh = timeline([(0, 30, RED)])
    specs = [{"id": "avenue", "sources": [{"light": "ped", "red_delay_s": 6.0, "amber_s": 3.0}]},
             {"id": "avenue_fb", "sources": [{"light": "ped", "red_delay_s": 6.0, "amber_s": 3.0}, {"light": "veh"}]},
             {"id": "crossing", "inverse_of": "avenue_fb", "green_after_s": 2.0, "red_before_s": 4.0}]
    sig = derive_signals(specs, {"ped": ped, "veh": veh})
    av = sig["avenue"]
    assert av.state_at(5) == UNKNOWN          # red since the video began: the delay is unknown
    assert av.state_at(15) == GREEN
    assert av.state_at(22) == GREEN           # pedestrians already red, vehicles still green ...
    assert av.state_at(24.5) == AMBER         # ... then amber ...
    assert av.state_at(27) == RED             # ... and red 6 s after the pedestrian red
    assert sig["avenue_fb"].state_at(5) == RED   # the second source fills the unknown start
    cr = sig["crossing"]
    assert cr.state_at(5) == GREEN and cr.state_at(8) == UNKNOWN   # clearance before the vehicles' green
    assert cr.state_at(15) == RED and cr.state_at(24.5) == RED
    assert cr.state_at(27) == UNKNOWN and cr.state_at(29) == GREEN


# -- crossing against a red pedestrian signal ----------------------------------------------------
def crossing_scene() -> Scene:
    cw = np.full((H, W), -1, np.int16)
    cw[polygon_mask(CROSSING, W, H)] = 0
    return Scene(W, H, road_mask=polygon_mask(ROAD, W, H), road_source="config", crosswalk_map=cw,
                 crosswalk_ids=["cw"], crosswalk_signals=["ped"], crosswalk_polys=[np.array(CROSSING, float)])


def walker(tid: int, t_kerb: float) -> np.ndarray:
    """Waits on the pavement above the crossing, then walks over it in 8 s."""
    return path_rows(tid, PERSON, [(0, 850, 280), (t_kerb, 850, 285), (t_kerb + 8, 850, 620)], size=(20, 50))


def test_stepping_onto_the_crossing_on_red_is_jaywalking():
    ped = timeline([(0, 30, RED), (30, 40, GREEN)])
    ctx = make_context([walker(1, 4.0)], 40, crossing_scene(), signals={"ped": ped})
    ev = RULES["jaywalking"](ctx)
    assert len(ev) == 1 and ev[0].tracks == (1,) and ev[0].info.get("crossing_on_red") == 0
    assert 3.5 < ev[0].start < 5.5


def test_crossing_on_green_or_just_before_green_is_not_jaywalking():
    ped = timeline([(0, 10, RED), (10, 30, GREEN), (30, 40, RED)])
    early = walker(1, 9.0)       # sets off one second before the green
    on_green = walker(2, 12.0)
    late = walker(3, 27.0)       # started on green, still walking when it turns red
    ctx = make_context([early, on_green, late], 40, crossing_scene(), signals={"ped": ped})
    assert RULES["jaywalking"](ctx) == []


def test_no_failure_to_yield_to_a_pedestrian_crossing_on_red():
    ped = timeline([(0, 30, RED), (30, 40, GREEN)])
    person = walker(1, 4.0)
    car = path_rows(2, CAR, [(6, 300, 470), (10, 1200, 470)])
    ctx = make_context([person, car], 40, crossing_scene(), signals={"ped": ped})
    assert RULES["failure_to_yield"](ctx) == []


# -- a queue at a red signal ---------------------------------------------------------------------
def signal_scene() -> Scene:
    line = StopLine("sl", np.array([700.0, 300.0]), np.array([700.0, 600.0]), np.array([1.0, 0.0]), "tl")
    return Scene(W, H, road_mask=polygon_mask(ROAD, W, H), road_source="config", stop_lines=[line],
                 lights={"tl": [0, 0, 1, 1]})


def test_waiting_at_a_long_red_is_not_a_stopped_vehicle():
    tl = timeline([(0, 3, GREEN), (3, 54, RED), (54, 70, GREEN)])
    car = path_rows(1, CAR, [(0, 100, 450), (4, 640, 450), (54, 640, 450), (58, 1200, 450)])
    ctx = make_context([car], 70, signal_scene(), signals={"tl": tl})
    assert RULES["stopped_vehicle"](ctx) == []
    assert RULES["congestion"](ctx) == []


def test_breaking_down_at_green_behind_the_line_is_a_stopped_vehicle():
    tl = timeline([(0, 30, GREEN), (30, 70, RED)])
    car = path_rows(1, CAR, [(0, 100, 450), (4, 640, 450), (70, 640, 450)])
    ctx = make_context([car], 70, signal_scene(), signals={"tl": tl})
    ev = RULES["stopped_vehicle"](ctx)
    assert len(ev) == 1 and abs(ev[0].start - 4.0) < 1.0


# -- one layout per camera -----------------------------------------------------------------------
def test_camera_layout_is_picked_by_frame_size(tmp_path):
    official, synthetic = tmp_path / "official.json", tmp_path / "synthetic.json"
    official.write_text(json.dumps({"frame_size": [3840, 2160]}))
    synthetic.write_text(json.dumps({"frame_size": [1280, 720]}))
    scfg = {"cameras": [{"config": str(official), "model": "o.npz"}], "config": str(synthetic), "model": "s.npz"}
    assert pick_camera(scfg, 3840, 2160) == (str(official), "o.npz")
    assert pick_camera(scfg, 1280, 720) == (str(synthetic), "s.npz")
    assert pick_camera(scfg, 1920, 1080) == (str(official), "o.npz")    # a downscaled copy
    assert pick_camera(scfg, 1000, 1000) == (str(synthetic), "s.npz")
