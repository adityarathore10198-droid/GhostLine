# ============================================================================
# GhostLine: AI-Powered RC Racing - Race Manager
# Component: python/race_manager.py
# Description: Race state machine, dynamic driver/car registration,
#              custom target lap enforcement, lap timing, and leaderboards.
# ============================================================================

import time
from typing import Dict, List, Optional, Callable, Any

class VehicleRaceStats:
    def __init__(self, vehicle_id: str, driver_name: str, car_name: str):
        self.vehicle_id = vehicle_id
        self.driver_name = driver_name
        self.car_name = car_name
        self.current_lap = 0
        self.total_laps_target = 5
        self.lap_start_time: Optional[float] = None
        self.last_lap_time: Optional[float] = None
        self.best_lap_time: Optional[float] = None
        self.lap_times: List[float] = []
        self.total_race_time: float = 0.0
        self.has_finished: bool = False
        self.last_crossing_time: float = 0.0

    def start_lap(self, start_time: float):
        self.lap_start_time = start_time
        if self.current_lap == 0:
            self.current_lap = 1

    def record_lap_crossing(self, crossing_time: float, min_lap_sec: float = 2.0) -> Optional[float]:
        """
        Record a lap completion with debounce to prevent spurious double triggers.
        Returns lap duration if valid, None otherwise.
        """
        if self.lap_start_time is None:
            self.start_lap(crossing_time)
            self.last_crossing_time = crossing_time
            return None

        lap_duration = crossing_time - self.lap_start_time
        if lap_duration < min_lap_sec:
            # Debounce noise / same line crossing
            return None

        # Valid lap recorded
        lap_duration = round(lap_duration, 3)
        self.last_lap_time = lap_duration
        self.lap_times.append(lap_duration)
        if self.best_lap_time is None or lap_duration < self.best_lap_time:
            self.best_lap_time = lap_duration

        self.current_lap += 1
        self.lap_start_time = crossing_time
        self.last_crossing_time = crossing_time

        if self.current_lap > self.total_laps_target:
            self.has_finished = True

        return lap_duration

    def get_current_lap_elapsed(self) -> float:
        if self.lap_start_time is None:
            return 0.0
        return round(time.time() - self.lap_start_time, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.vehicle_id,
            "driver_name": self.driver_name,
            "car_name": self.car_name,
            "name": f"{self.driver_name} ({self.car_name})",
            "current_lap": min(self.current_lap, self.total_laps_target),
            "total_laps": self.total_laps_target,
            "current_lap_elapsed": self.get_current_lap_elapsed(),
            "last_lap_time": self.last_lap_time,
            "best_lap_time": self.best_lap_time,
            "lap_times": self.lap_times,
            "finished": self.has_finished
        }


class RaceManager:
    def __init__(self, target_laps: int = 5):
        self.state: str = "IDLE"  # IDLE, COUNTDOWN, RACING, HAZARD, FINISHED
        self.mode: str = "TIME_ATTACK"  # TIME_ATTACK or VERSUS_RACE
        self.target_laps: int = target_laps
        self.race_start_time: Optional[float] = None
        self.race_finish_time: Optional[float] = None

        self.vehicles: Dict[str, VehicleRaceStats] = {
            "car_1": VehicleRaceStats("car_1", "Driver 1", "Apex GT"),
            "car_2": VehicleRaceStats("car_2", "Driver 2", "Blaze RC")
        }

        # Event callbacks
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_lap_completed: Optional[Callable[[str, float, bool], None]] = None
        self.on_race_finished: Optional[Callable[[List[Dict]], None]] = None

    def register_session(self, p1_driver: str, p1_car: str, p2_driver: str, p2_car: str, 
                         target_laps: int, mode: str = "TIME_ATTACK"):
        """Register drivers, vehicles, target laps, and race mode from Web UI."""
        self.target_laps = max(1, min(100, int(target_laps)))
        self.mode = mode if mode in ["TIME_ATTACK", "VERSUS_RACE"] else "TIME_ATTACK"

        if "car_1" in self.vehicles:
            self.vehicles["car_1"].driver_name = p1_driver or "Driver 1"
            self.vehicles["car_1"].car_name = p1_car or "Apex GT"
            self.vehicles["car_1"].total_laps_target = self.target_laps

        if "car_2" in self.vehicles:
            self.vehicles["car_2"].driver_name = p2_driver or "Driver 2"
            self.vehicles["car_2"].car_name = p2_car or "Blaze RC"
            self.vehicles["car_2"].total_laps_target = self.target_laps

        self.reset_stats()

    def set_mode(self, mode: str):
        if mode in ["TIME_ATTACK", "VERSUS_RACE"]:
            self.mode = mode

    def start_countdown(self):
        """Transition to COUNTDOWN state."""
        self.state = "COUNTDOWN"
        self.reset_stats()
        if self.on_state_change:
            self.on_state_change("COUNTDOWN")

    def green_flag(self):
        """Transition to RACING state when countdown completes."""
        self.state = "RACING"
        now = time.time()
        self.race_start_time = now
        for v in self.vehicles.values():
            v.start_lap(now)
            v.total_laps_target = self.target_laps

        if self.on_state_change:
            self.on_state_change("RACING")

    def set_hazard(self, is_hazard: bool):
        """Toggle yellow flag hazard."""
        if self.state in ["RACING", "HAZARD"]:
            self.state = "HAZARD" if is_hazard else "RACING"
            if self.on_state_change:
                self.on_state_change(self.state)

    def register_line_crossing(self, vehicle_id: str) -> Optional[float]:
        """Called when a vehicle crosses the virtual finish line."""
        if self.state != "RACING":
            return None

        v = self.vehicles.get(vehicle_id)
        if not v or v.has_finished:
            return None

        now = time.time()
        lap_dur = v.record_lap_crossing(now)
        if lap_dur is not None:
            is_record = (lap_dur == v.best_lap_time)
            if self.on_lap_completed:
                self.on_lap_completed(vehicle_id, lap_dur, is_record)

            # Check if race is complete
            if self.mode == "VERSUS_RACE":
                all_done = all(veh.has_finished for veh in self.vehicles.values())
                if all_done:
                    self.finish_race()
            elif self.mode == "TIME_ATTACK" and vehicle_id == "car_1" and v.has_finished:
                self.finish_race()

        return lap_dur

    def finish_race(self):
        """End the race and declare winners."""
        self.state = "FINISHED"
        self.race_finish_time = time.time()
        if self.on_state_change:
            self.on_state_change("FINISH")
        if self.on_race_finished:
            self.on_race_finished(self.get_leaderboard())

    def reset_stats(self):
        """Reset all telemetry for a new race session."""
        self.state = "IDLE"
        self.race_start_time = None
        self.race_finish_time = None
        for v in self.vehicles.values():
            v.current_lap = 0
            v.total_laps_target = self.target_laps
            v.lap_start_time = None
            v.last_lap_time = None
            v.best_lap_time = None
            v.lap_times = []
            v.has_finished = False

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Return ordered list of racers by position."""
        ranked = list(self.vehicles.values())
        # Ranking criteria: Finished first, then highest lap count, then lowest best_lap_time
        def sort_key(v: VehicleRaceStats):
            return (
                -1 if v.has_finished else 0,
                -v.current_lap,
                v.best_lap_time if v.best_lap_time is not None else 9999.0
            )
        ranked.sort(key=sort_key)

        leaderboard = []
        for rank, v in enumerate(ranked, start=1):
            info = v.to_dict()
            info["position"] = f"P{rank}"
            leaderboard.append(info)
        return leaderboard

    def force_complete_random_winner(self) -> List[Dict[str, Any]]:
        """
        Manually trigger race completion and randomly pick a winner.
        Generates realistic winning statistics for the chosen driver.
        """
        import random
        cars = list(self.vehicles.keys())
        winner_id = random.choice(cars)
        loser_id = [c for c in cars if c != winner_id][0]

        w = self.vehicles[winner_id]
        l = self.vehicles[loser_id]

        # Set winner stats
        w.current_lap = self.target_laps
        w.has_finished = True
        base_time = round(random.uniform(4.25, 5.40), 2)
        if not w.best_lap_time or w.best_lap_time > base_time:
            w.best_lap_time = base_time
        w.last_lap_time = round(w.best_lap_time + random.uniform(0.05, 0.25), 2)

        # Set runner-up stats
        l.current_lap = max(1, self.target_laps - random.choice([0, 1]))
        l.has_finished = (l.current_lap >= self.target_laps)
        l.best_lap_time = round(w.best_lap_time + random.uniform(0.35, 1.10), 2)
        l.last_lap_time = round(l.best_lap_time + random.uniform(0.10, 0.30), 2)

        self.finish_race()
        return self.get_leaderboard()

