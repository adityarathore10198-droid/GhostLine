# ============================================================================
# GhostLine: AI-Powered RC Racing - Main MPU Application
# Component: python/main.py
# Description: Central coordinator running on the Qualcomm Dragonwing Linux MPU.
#              Orchestrates real USB Camera Video Object Detection (YOLOX Nano),
#              live driver/car registration with custom laps, GhostLine engine,
#              Bridge RPC with STM32 MCU, and WebUI WebSockets.
# ============================================================================

import time
import math
import json
import threading
from typing import Dict, Any

# ----------------------------------------------------------------------------
# Arduino App Lab & Brick Imports (with graceful mock fallbacks for testing)
# ----------------------------------------------------------------------------
try:
    from arduino.app_utils import App, Bridge
    from arduino.app_bricks.web_ui import WebUI
    from arduino.app_bricks.video_objectdetection import VideoObjectDetection
    RUNNING_IN_APP_LAB = True
except ImportError:
    RUNNING_IN_APP_LAB = False

    class MockBridge:
        @staticmethod
        def call(name, *args):
            return "OK"
        @staticmethod
        def notify(name, *args):
            pass
        @staticmethod
        def provide(name, callback):
            pass

    class MockWebUI:
        def __init__(self):
            self.handlers = {}
        def on_message(self, event, callback):
            self.handlers[event] = callback
        def send_message(self, event, message, client=None):
            pass

    class MockVideoObjectDetection:
        def __init__(self, confidence=0.4, debounce_sec=0.0):
            self.confidence = confidence
            self.callback = None
        def on_detect_all(self, callback):
            self.callback = callback
        def override_threshold(self, value):
            self.confidence = value

    class MockApp:
        @staticmethod
        def run(user_loop=None):
            if user_loop:
                while True:
                    user_loop()
                    time.sleep(0.05)

    Bridge = MockBridge()
    WebUI = MockWebUI
    VideoObjectDetection = MockVideoObjectDetection
    App = MockApp

# Local engine modules
from tracker import VisionTracker
from ghost_engine import GhostEngine
from race_manager import RaceManager

# ----------------------------------------------------------------------------
# System Initialization
# ----------------------------------------------------------------------------
ui = WebUI()
# Set threshold to 0.30 for responsive detection of micro RC cars
detection_stream = VideoObjectDetection(confidence=0.30, debounce_sec=0.0)
tracker = VisionTracker(track_scale_meters=3.0)
ghost = GhostEngine(persistence_file="ghost_best_lap.json")
race = RaceManager(target_laps=5)

# Operation mode: Physical USB Camera tracking (True by default)
PHYSICAL_MODE = True
simulation_demo = False

# ----------------------------------------------------------------------------
# Real-Time Video Object Detection Callback (Edge Impulse Vehicle Model)
# ----------------------------------------------------------------------------
last_log_time = 0.0

def on_camera_detections(detections: dict):
    """
    Called whenever the VideoObjectDetection brick detects vehicles from the USB camera.
    Feeds real bounding boxes [x1, y1, x2, y2] into the tracker.
    """
    global last_log_time
    if not detections:
        return

    now = time.time()
    if now - last_log_time >= 2.0:
        last_log_time = now
        print(f"[Edge Impulse Vehicle Detection] Active detections: {list(detections.keys()) if isinstance(detections, dict) else len(detections)}")

    # Process detections into vehicle coordinates
    tracker.process_object_detections(detections)

detection_stream.on_detect_all(on_camera_detections)

# Dynamic confidence adjustment from UI
ui.on_message("override_th", lambda sid, threshold: detection_stream.override_threshold(threshold))

# ----------------------------------------------------------------------------
# Bridge RPC Interfacing with STM32 MCU
# ----------------------------------------------------------------------------
def mcu_set_race_state(state: str):
    try:
        Bridge.call("set_race_state", state)
    except Exception as e:
        print(f"[Bridge Error] set_race_state: {e}")

def mcu_trigger_countdown():
    try:
        Bridge.call("trigger_countdown")
    except Exception as e:
        print(f"[Bridge Error] trigger_countdown: {e}")

def mcu_display_lap(lap_time: float):
    try:
        Bridge.call("display_lap_time", f"{lap_time:.2f}")
    except Exception as e:
        print(f"[Bridge Error] display_lap_time: {e}")

def mcu_play_cue(cue_type: str):
    try:
        Bridge.call("play_buzzer_cue", cue_type)
    except Exception as e:
        print(f"[Bridge Error] play_buzzer_cue: {e}")

# Handler for hardware notification when countdown completes on STM32
def on_race_green_flag_from_mcu(timestamp: int):
    print(f"[MCU Signal] Green flag triggered at {timestamp}")
    race.green_flag()
    ui.send_message("race_started", {"timestamp": timestamp})

if RUNNING_IN_APP_LAB:
    Bridge.provide("on_race_green_flag", on_race_green_flag_from_mcu)

# ----------------------------------------------------------------------------
# Race Event Callbacks
# ----------------------------------------------------------------------------
def handle_state_change(new_state: str):
    print(f"[Race State Change] -> {new_state}")
    mcu_set_race_state(new_state)
    ui.send_message("state_changed", {"state": new_state})

def handle_lap_completed(vehicle_id: str, lap_duration: float, is_record: bool):
    print(f"[Lap Completed] {vehicle_id}: {lap_duration}s (New Record: {is_record})")
    mcu_play_cue("lap")
    mcu_display_lap(lap_duration)

    # Car 1 (P1) records into the GhostLine engine
    if vehicle_id == "car_1":
        is_ghost_record = ghost.complete_lap(lap_duration)
        if is_ghost_record:
            print(f"*** NEW GHOSTLINE RECORD: {lap_duration}s ***")
            ui.send_message("new_ghost_record", {
                "best_time": lap_duration,
                "trail": ghost.get_full_ghost_trail()
            })
        ghost.start_lap_recording()

    ui.send_message("lap_completed", {
        "vehicle_id": vehicle_id,
        "lap_duration": lap_duration,
        "is_record": is_record
    })

def handle_race_finished(final_leaderboard: list):
    winner = final_leaderboard[0]["driver_name"] if final_leaderboard else "Racer"
    print(f"[Race Finished] Winner: {winner}")
    mcu_set_race_state("FINISH")
    ui.send_message("race_finished", {"leaderboard": final_leaderboard})

race.on_state_change = handle_state_change
race.on_lap_completed = handle_lap_completed
race.on_race_finished = handle_race_finished

# ----------------------------------------------------------------------------
# WebUI Inbound Action Listeners
# ----------------------------------------------------------------------------
def on_register_race(client, data):
    """
    Handle Driver and Vehicle Registration with custom target laps before the race.
    """
    p1_driver = data.get("p1_driver", "Driver 1")
    p1_car = data.get("p1_car", "Apex GT")
    p2_driver = data.get("p2_driver", "Driver 2")
    p2_car = data.get("p2_car", "Blaze RC")
    target_laps = int(data.get("target_laps", 5))
    mode = data.get("mode", "TIME_ATTACK")

    print(f"[WebUI] Registered Session: {p1_driver} vs {p2_driver} | Laps: {target_laps} | Mode: {mode}")
    tracker.update_registration(p1_driver, p1_car, p2_driver, p2_car)
    race.register_session(p1_driver, p1_car, p2_driver, p2_car, target_laps, mode)

    ui.send_message("registration_confirmed", {
        "p1_driver": p1_driver, "p1_car": p1_car,
        "p2_driver": p2_driver, "p2_car": p2_car,
        "target_laps": target_laps,
        "mode": mode,
        "leaderboard": race.get_leaderboard()
    })

def on_start_race_clicked(client, data):
    print("[WebUI] Start Race command received")
    race.start_countdown()
    mcu_trigger_countdown()

def on_reset_race_clicked(client, data):
    print("[WebUI] Reset Race command received")
    race.reset_stats()
    mcu_set_race_state("IDLE")
    ui.send_message("state_changed", {"state": "IDLE"})

def on_set_mode_clicked(client, data):
    mode = data.get("mode", "TIME_ATTACK")
    race.set_mode(mode)
    ui.send_message("mode_changed", {"mode": mode})

def on_calibrate_finish_line(client, data):
    p1 = (data.get("x1", 0.5), data.get("y1", 0.7))
    p2 = (data.get("x2", 0.5), data.get("y2", 0.95))
    tracker.set_finish_line(p1, p2)
    print(f"[WebUI] Finish Line Calibrated on Camera View: {p1} -> {p2}")
    ui.send_message("finish_line_updated", {"p1": p1, "p2": p2})

def on_toggle_hazard(client, data):
    is_hazard = (race.state != "HAZARD")
    race.set_hazard(is_hazard)

def on_toggle_sim_demo(client, data):
    global simulation_demo
    simulation_demo = not simulation_demo
    print(f"[WebUI] Simulation Demo: {simulation_demo}")

def on_force_complete_race(client, data):
    print("[WebUI] User clicked Complete Race - selecting random winner")
    race.force_complete_random_winner()

# Register WebUI event dispatchers
ui.on_message("register_race", on_register_race)
ui.on_message("start_race", on_start_race_clicked)
ui.on_message("force_complete_race", on_force_complete_race)
ui.on_message("reset_race", on_reset_race_clicked)
ui.on_message("set_mode", on_set_mode_clicked)
ui.on_message("calibrate_finish_line", on_calibrate_finish_line)
ui.on_message("toggle_hazard", on_toggle_hazard)
ui.on_message("toggle_sim_demo", on_toggle_sim_demo)

# ----------------------------------------------------------------------------
# Real-Time Telemetry & Tracking Main Loop
# ----------------------------------------------------------------------------
last_loop_time = time.time()
telemetry_broadcast_timer = 0.0

# Optional demo trajectory variables if simulation_demo is toggled
demo_ang1 = 0.0
demo_ang2 = 1.0

def main_loop():
    global last_loop_time, telemetry_broadcast_timer, demo_ang1, demo_ang2

    now = time.time()
    dt = max(0.001, min(0.1, now - last_loop_time))
    last_loop_time = now

    # 1. Position update: If demo mode is active, feed simulated positions
    if simulation_demo:
        if race.state in ["RACING", "HAZARD"]:
            spd = 0.5 if race.state == "HAZARD" else 1.5
            demo_ang1 += spd * dt
            demo_ang2 += (spd * 0.9) * dt
            tracker.vehicles["car_1"].update_detection(
                [0.5 + 0.32 * math.cos(demo_ang1) - 0.04, 0.5 + 0.22 * math.sin(demo_ang1) - 0.04,
                 0.5 + 0.32 * math.cos(demo_ang1) + 0.04, 0.5 + 0.22 * math.sin(demo_ang1) + 0.04],
                0.92, tracker.track_scale_meters
            )
            tracker.vehicles["car_2"].update_detection(
                [0.5 + 0.36 * math.cos(demo_ang2) - 0.04, 0.5 + 0.25 * math.sin(demo_ang2) - 0.04,
                 0.5 + 0.36 * math.cos(demo_ang2) + 0.04, 0.5 + 0.25 * math.sin(demo_ang2) + 0.04],
                0.88, tracker.track_scale_meters
            )

    # 2. Check Virtual Finish Line Crossings
    for car_id in ["car_1", "car_2"]:
        if tracker.check_line_crossing(car_id):
            race.register_line_crossing(car_id)

    # 3. Update Ghost Engine with live Car 1 telemetry
    car1 = tracker.vehicles["car_1"]
    car1_stats = race.vehicles["car_1"]
    if race.state == "RACING" and car1.is_detected:
        ghost.record_point(car1.x, car1.y, car1.speed_kmh)

    ghost_status = ghost.get_ghost_state_at(
        car1_stats.get_current_lap_elapsed(),
        car1.x,
        car1.y
    )

    # 4. Broadcast Telemetry to WebUI at 20 Hz (50ms interval)
    telemetry_broadcast_timer += dt
    if telemetry_broadcast_timer >= 0.05:
        telemetry_broadcast_timer = 0.0

        payload = {
            "race_state": race.state,
            "race_mode": race.mode,
            "target_laps": race.target_laps,
            "leaderboard": race.get_leaderboard(),
            "vehicles": {
                "car_1": car1.to_dict(),
                "car_2": tracker.vehicles["car_2"].to_dict()
            },
            "ghost": ghost_status,
            "finish_line": tracker.finish_line,
            "timestamp": round(now, 3)
        }
        ui.send_message("telemetry_update", payload)

    time.sleep(0.02)

# Start Application
if __name__ == "__main__":
    print("=========================================================")
    print("   GhostLine: Live AI-Powered RC Racing Starting         ")
    print("   Live USB Camera + YOLOX Nano Object Detection Brick   ")
    print("   Dual-Brain Architecture: Qualcomm MPU + STM32 MCU     ")
    print("=========================================================")
    App.run(user_loop=main_loop)
