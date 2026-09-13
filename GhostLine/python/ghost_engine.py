# ============================================================================
# GhostLine: AI-Powered RC Racing - Ghost Engine
# Component: python/ghost_engine.py
# Description: Records fastest lap trajectory, computes real-time ghost position,
#              and calculates millisecond delta between live vehicle and ghost.
# ============================================================================

import json
import time
import math
import os
from typing import List, Dict, Tuple, Optional

class GhostWaypoint:
    def __init__(self, t_offset: float, x: float, y: float, speed_kmh: float):
        self.t_offset = t_offset    # Seconds from lap start
        self.x = x                  # Normalized X [0, 1]
        self.y = y                  # Normalized Y [0, 1]
        self.speed_kmh = speed_kmh  # Speed at this point

    def to_dict(self) -> Dict:
        return {
            "t": round(self.t_offset, 3),
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "s": round(self.speed_kmh, 1)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GhostWaypoint':
        return cls(data["t"], data["x"], data["y"], data["s"])


class GhostEngine:
    def __init__(self, persistence_file: str = "ghost_best_lap.json"):
        self.persistence_file = persistence_file
        self.best_lap_time: Optional[float] = None
        self.ghost_waypoints: List[GhostWaypoint] = []
        self.active_lap_recording: List[GhostWaypoint] = []
        self.recording_start_time: Optional[float] = None

        self.load_best_ghost()

    def start_lap_recording(self):
        """Called when vehicle crosses the start line to begin a new lap."""
        self.recording_start_time = time.time()
        self.active_lap_recording = []

    def record_point(self, x: float, y: float, speed_kmh: float):
        """Record live coordinate sample during lap."""
        if self.recording_start_time is None:
            return
        t_offset = time.time() - self.recording_start_time
        wp = GhostWaypoint(t_offset, x, y, speed_kmh)
        self.active_lap_recording.append(wp)

    def complete_lap(self, lap_duration: float) -> bool:
        """
        Called when lap is completed.
        If this lap beats the previous best, it becomes the new Ghost Line!
        Returns True if a new record was set.
        """
        is_new_record = False
        if (self.best_lap_time is None or lap_duration < self.best_lap_time) and len(self.active_lap_recording) > 10:
            self.best_lap_time = round(lap_duration, 3)
            self.ghost_waypoints = list(self.active_lap_recording)
            self.save_best_ghost()
            is_new_record = True

        self.active_lap_recording = []
        self.recording_start_time = None
        return is_new_record

    def get_ghost_state_at(self, current_lap_elapsed: float, live_x: float, live_y: float) -> Dict:
        """
        Calculates where the Ghost car is at the current elapsed lap time,
        and computes the spatial / temporal delta.
        """
        if not self.ghost_waypoints or self.best_lap_time is None:
            return {
                "has_ghost": False,
                "best_lap_time": None,
                "ghost_x": None,
                "ghost_y": None,
                "delta_sec": 0.0,
                "ahead_of_ghost": False
            }

        # Find interpolated ghost position at current_lap_elapsed
        t = current_lap_elapsed % self.best_lap_time
        ghost_pt = self._interpolate_waypoint(t)

        # Estimate delta (distance between live car and ghost car projected onto time)
        dist = math.hypot(live_x - ghost_pt.x, live_y - ghost_pt.y)
        
        # Determine if ahead or behind based on nearest waypoint time
        closest_wp_time = self._find_nearest_waypoint_time(live_x, live_y)
        delta = round(closest_wp_time - t, 2)
        ahead = (delta >= 0)

        return {
            "has_ghost": True,
            "best_lap_time": self.best_lap_time,
            "ghost_x": round(ghost_pt.x, 4),
            "ghost_y": round(ghost_pt.y, 4),
            "ghost_speed": round(ghost_pt.speed_kmh, 1),
            "delta_sec": abs(delta),
            "ahead_of_ghost": ahead
        }

    def _interpolate_waypoint(self, t: float) -> GhostWaypoint:
        """Linear interpolation between recorded waypoints for smooth rendering."""
        wps = self.ghost_waypoints
        if not wps:
            return GhostWaypoint(0, 0.5, 0.5, 0)

        if t <= wps[0].t_offset:
            return wps[0]
        if t >= wps[-1].t_offset:
            return wps[-1]

        # Binary search for interval
        low, high = 0, len(wps) - 1
        while low <= high:
            mid = (low + high) // 2
            if wps[mid].t_offset < t:
                low = mid + 1
            else:
                high = mid - 1

        idx2 = max(1, low)
        idx1 = idx2 - 1
        p1 = wps[idx1]
        p2 = wps[min(idx2, len(wps) - 1)]

        span = p2.t_offset - p1.t_offset
        factor = (t - p1.t_offset) / span if span > 0 else 0.0
        factor = max(0.0, min(1.0, factor))

        interp_x = p1.x + (p2.x - p1.x) * factor
        interp_y = p1.y + (p2.y - p1.y) * factor
        interp_spd = p1.speed_kmh + (p2.speed_kmh - p1.speed_kmh) * factor

        return GhostWaypoint(t, interp_x, interp_y, interp_spd)

    def _find_nearest_waypoint_time(self, x: float, y: float) -> float:
        """Find the time offset of the closest waypoint on the ghost line."""
        if not self.ghost_waypoints:
            return 0.0
        min_dist = float('inf')
        best_t = 0.0
        for wp in self.ghost_waypoints:
            d = (wp.x - x)**2 + (wp.y - y)**2
            if d < min_dist:
                min_dist = d
                best_t = wp.t_offset
        return best_t

    def get_full_ghost_trail(self, step: int = 2) -> List[Dict]:
        """Returns subsampled ghost trajectory for rendering on the canvas."""
        return [wp.to_dict() for i, wp in enumerate(self.ghost_waypoints) if i % step == 0]

    def save_best_ghost(self):
        try:
            data = {
                "best_lap_time": self.best_lap_time,
                "waypoints": [wp.to_dict() for wp in self.ghost_waypoints]
            }
            with open(self.persistence_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_best_ghost(self):
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r") as f:
                    data = json.load(f)
                    self.best_lap_time = data.get("best_lap_time")
                    self.ghost_waypoints = [GhostWaypoint.from_dict(d) for d in data.get("waypoints", [])]
            except Exception:
                pass
