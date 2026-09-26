"""Regression evidence from the organiser samples, plus retained collision positives."""
from __future__ import annotations

import numpy as np
from synthetic import CAR, MOTORBIKE, PERSON, make_context, path_rows

from trafficwatch.events import RULES
from trafficwatch.events.interactions import _rest_together, _settle_time


def test_walking_up_to_a_parked_car_is_not_a_collision():
    car = path_rows(1, CAR, [(0, 600, 500), (12, 600, 500)])
    person = path_rows(2, PERSON, [(0, 200, 465), (4, 560, 465), (4.2, 575, 465), (12, 575, 465)],
                       size=(20, 50))
    assert RULES['accident'](make_context([car, person], 14)) == []


def test_moving_vehicle_contact_with_a_person_remains_a_collision():
    car = path_rows(1, CAR, [(0, 100, 500), (3, 540, 500), (3.3, 560, 500), (12, 560, 500)])
    person = path_rows(2, PERSON, [(0, 600, 500), (12, 600, 500)], size=(20, 50))
    events = RULES['accident'](make_context([car, person], 14))
    assert len(events) == 1 and 2.5 < events[0].start < 3.5


def test_two_wheeler_hitting_parked_car_remains_a_collision():
    car = path_rows(1, CAR, [(0, 600, 500), (12, 600, 500)])
    bike = path_rows(2, MOTORBIKE, [(0, 100, 500), (3, 540, 500), (3.3, 560, 500), (12, 560, 500)],
                     size=(60, 40))
    events = RULES['accident'](make_context([car, bike], 14))
    assert len(events) == 1 and 2.5 < events[0].start < 3.5


def test_track_end_does_not_prove_half_a_second_at_rest():
    track = make_context([path_rows(1, CAR, [(0, 600, 500), (1, 600, 500)])], 1).tracks[0]
    time, settled = _settle_time(track, 0.8, settle_nspeed=0.25, hold_s=0.5)
    assert not settled and time == track.t1


def test_full_observed_stop_window_is_accepted():
    track = make_context([path_rows(1, CAR, [(0, 600, 500), (2, 600, 500)])], 2).tracks[0]
    time, settled = _settle_time(track, 0.8, settle_nspeed=0.25, hold_s=0.5)
    assert settled and abs(time - 0.8) < 0.01


def test_missing_joint_observations_do_not_prove_rest_together():
    pair = {'t': np.array([0.0, 0.5]), 'ok': np.ones(2, dtype=bool), 'dn': np.array([0.5, 0.5])}
    assert not _rest_together(pair, 1.0, {'rest_together_s': 1.0, 'rest_scale': 1.5})


def test_observed_pair_remaining_close_supports_rest():
    pair = {'t': np.array([0.0, 0.5, 1.0, 1.5, 2.0]), 'ok': np.ones(5, dtype=bool),
            'dn': np.array([0.5, 0.5, 0.5, 0.5, 0.5])}
    assert _rest_together(pair, 1.0, {'rest_together_s': 1.0, 'rest_scale': 1.5})
