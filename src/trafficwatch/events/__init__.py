"""Event rules, one function per class. Each takes a Context and returns a list of Events."""
from __future__ import annotations

from typing import Callable

from .common import Context, Event
from .hazards import fire_smoke, road_obstacle
from .interactions import accident, near_miss
from .pedestrians import failure_to_yield, jaywalking
from .signals import red_light, stop_line
from .vehicles import (congestion, illegal_turn, illegal_u_turn, solid_line_crossing,
                       stopped_vehicle, wrong_way)

RULES: dict[str, Callable[[Context], list[Event]]] = {
    "accident": accident,
    "near_miss": near_miss,
    "red_light": red_light,
    "wrong_way": wrong_way,
    "illegal_u_turn": illegal_u_turn,
    "stopped_vehicle": stopped_vehicle,
    "jaywalking": jaywalking,
    "failure_to_yield": failure_to_yield,
    "illegal_turn": illegal_turn,
    "solid_line_crossing": solid_line_crossing,
    "stop_line": stop_line,
    "congestion": congestion,
    "road_obstacle": road_obstacle,
    "fire_smoke": fire_smoke,
}

__all__ = ["RULES", "Context", "Event"]
