"""TrafficWatch: traffic event detection and accident anticipation for a fixed CCTV camera."""
import os

# Evaluation runs without internet: stop Ultralytics from probing the network or printing banners.
os.environ.setdefault("YOLO_OFFLINE", "true")
os.environ.setdefault("YOLO_VERBOSE", "false")

CLASSES = [
    "accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn",
    "stopped_vehicle", "jaywalking", "failure_to_yield", "illegal_turn",
    "solid_line_crossing", "stop_line", "congestion", "road_obstacle", "fire_smoke",
]

__all__ = ["CLASSES"]
