# ============================================================================
# GhostLine: AI-Powered RC Racing - Vehicle Vision Tracker
# Component: python/tracker.py
# Description: Multi-car vision tracking with custom Edge Impulse vehicle
#              detection models, universal bounding-box extraction, centroid
#              tracking, velocity estimation, and line-crossing calculations.
# ============================================================================

import time
import math
from typing import Dict, List, Tuple, Optional, Any

class TrackedVehicle:
    def __init__(self, vehicle_id: str, driver_name: str, car_name: str, color_hex: str, 
                 hsv_range: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((0, 0, 0), (180, 255, 255))):
        self.vehicle_id = vehicle_id
        self.driver_name = driver_name
        self.car_name = car_name
        self.color_hex = color_hex
        self.hsv_lower = hsv_range[0]
        self.hsv_upper = hsv_range[1]

        # Normalized coordinates [0.0 - 1.0]
        self.x: float = 0.0
        self.y: float = 0.0
        self.prev_x: float = 0.0
        self.prev_y: float = 0.0

        # Bounding box in normalized coordinates [x1, y1, x2, y2]
        self.bbox: Optional[List[float]] = None
        self.confidence: float = 0.0
        self.detected_label: str = "vehicle"

        # Velocity in pixels/sec and estimated scale km/h
        self.speed_px_per_sec: float = 0.0
        self.speed_kmh: float = 0.0
        self.last_update_time: float = time.time()

        # Trail history (last 30 coordinates for trail rendering)
        self.trail: List[Tuple[float, float]] = []
        self.max_trail_len = 30
        self.is_detected: bool = False
        self.frames_since_seen = 0

    def update_detection(self, bbox: List[float], confidence: float, label: str = "vehicle", meters_per_unit: float = 3.0):
        """Update vehicle position from object detection bounding box [x1, y1, x2, y2]."""
        # Calculate centroid from bounding box
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        self.bbox = [round(float(v), 4) for v in bbox]
        self.confidence = round(float(confidence), 2)
        self.detected_label = label
        self.frames_since_seen = 0
        self.update_position(cx, cy, meters_per_unit)

    def update_position(self, x: float, y: float, meters_per_unit: float = 3.0):
        """Update vehicle coordinate and calculate instantaneous speed."""
        now = time.time()
        dt = now - self.last_update_time

        if dt > 0.001 and (self.x != 0.0 or self.y != 0.0):
            dx = x - self.x
            dy = y - self.y
            dist_units = math.hypot(dx, dy)
            self.speed_px_per_sec = dist_units / dt

            # Scale speed conversion to km/h (1:24 or 1:28 scale RC car)
            speed_mps = (dist_units * meters_per_unit) / dt
            # Cap unreasonable spikes due to camera noise
            calc_speed = round(min(80.0, speed_mps * 3.6), 1)
            # Low pass filter for smooth HUD display
            self.speed_kmh = round(0.7 * self.speed_kmh + 0.3 * calc_speed, 1)

        self.prev_x = self.x
        self.prev_y = self.y
        self.x = round(x, 4)
        self.y = round(y, 4)
        self.last_update_time = now
        self.is_detected = True

        self.trail.append((self.x, self.y))
        if len(self.trail) > self.max_trail_len:
            self.trail.pop(0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.vehicle_id,
            "driver_name": self.driver_name,
            "car_name": self.car_name,
            "color": self.color_hex,
            "x": self.x,
            "y": self.y,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "detected_label": self.detected_label,
            "speed_kmh": self.speed_kmh,
            "is_detected": self.is_detected,
            "trail": self.trail[-15:] # Send recent trail points
        }


class LineCrossingDetector:
    """Detects when a vehicle's trajectory vector intersects a virtual line segment."""
    @staticmethod
    def _ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    @classmethod
    def intersects(cls, A: Tuple[float, float], B: Tuple[float, float], 
                   C: Tuple[float, float], D: Tuple[float, float]) -> bool:
        """Returns True if line segment AB and line segment CD intersect."""
        return (cls._ccw(A, C, D) != cls._ccw(B, C, D) and 
                cls._ccw(A, B, C) != cls._ccw(A, B, D))


class VisionTracker:
    def __init__(self, track_scale_meters: float = 3.0):
        self.track_scale_meters = track_scale_meters

        # Default virtual finish line in normalized [0, 1] camera coordinates
        self.finish_line: Tuple[Tuple[float, float], Tuple[float, float]] = (
            (0.50, 0.70), (0.50, 0.95)
        )

        # Active tracked vehicles
        self.vehicles: Dict[str, TrackedVehicle] = {
            "car_1": TrackedVehicle(
                vehicle_id="car_1",
                driver_name="Driver 1",
                car_name="Apex GT (Cyan)",
                color_hex="#00f3ff",
                hsv_range=((85, 120, 120), (105, 255, 255))
            ),
            "car_2": TrackedVehicle(
                vehicle_id="car_2",
                driver_name="Driver 2",
                car_name="Blaze RC (Orange)",
                color_hex="#ff5500",
                hsv_range=((5, 150, 150), (18, 255, 255))
            )
        }

    def update_registration(self, p1_driver: str, p1_car: str, p2_driver: str, p2_car: str):
        """Update driver and car names from the Web UI registration form."""
        if "car_1" in self.vehicles:
            self.vehicles["car_1"].driver_name = p1_driver or "Driver 1"
            self.vehicles["car_1"].car_name = p1_car or "Apex GT"
        if "car_2" in self.vehicles:
            self.vehicles["car_2"].driver_name = p2_driver or "Driver 2"
            self.vehicles["car_2"].car_name = p2_car or "Blaze RC"

    def set_finish_line(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        """Calibrate the virtual finish line position on the camera feed."""
        self.finish_line = (p1, p2)

    def _extract_candidate_boxes(self, raw_data: Any) -> List[Tuple[List[float], float, str]]:
        """
        Universal extractor that parses bounding boxes from Edge Impulse models:
        Handles:
          - Dict format: { "vehicle": [{"confidence": 0.85, "box": [x1, y1, x2, y2]}], ... }
          - App Lab format: { "detection": [{"class_name": "car", "bounding_box_xyxy": [...], "confidence": 0.9}] }
          - List format: [ {"label": "car", "box": [...], "confidence": 0.8}, ... ]
        """
        candidates = []
        if not raw_data:
            return candidates

        # Format 1 & 2: Dictionary input
        if isinstance(raw_data, dict):
            # Check for "detection" list (App Lab / YOLOX runner standard)
            if "detection" in raw_data and isinstance(raw_data["detection"], list):
                for item in raw_data["detection"]:
                    label = item.get("class_name") or item.get("label") or "vehicle"
                    conf = item.get("confidence", 0.5)
                    box = item.get("bounding_box_xyxy") or item.get("box") or item.get("bounding_box")
                    if box and len(box) == 4:
                        candidates.append((box, conf, label))
                return candidates

            # Label-keyed dictionary: { "car": [...], "vehicle": [...] }
            for label, items in raw_data.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            conf = item.get("confidence", 0.5)
                            box = item.get("box") or item.get("bounding_box") or item.get("bounding_box_xyxy")
                            item_label = item.get("class_name") or item.get("label") or label
                            if box and len(box) == 4:
                                candidates.append((box, conf, item_label))

        # Format 3: List input
        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    label = item.get("class_name") or item.get("label") or item.get("content") or "vehicle"
                    conf = item.get("confidence", 0.5)
                    box = item.get("box") or item.get("bounding_box") or item.get("bounding_box_xyxy")
                    if box and len(box) == 4:
                        candidates.append((box, conf, label))

        return candidates

    def process_object_detections(self, detections: Any):
        """
        Processes real-time detections from the Edge Impulse vehicle detection model.
        Maps detected bounding boxes to registered vehicles using centroid proximity.
        """
        candidate_boxes = self._extract_candidate_boxes(detections)

        # If no boxes detected in this frame, increment frames_since_seen
        if not candidate_boxes:
            for v in self.vehicles.values():
                v.frames_since_seen += 1
                if v.frames_since_seen > 12:
                    v.is_detected = False
            return self.vehicles

        # Prioritize vehicle labels if multiple object types are present
        vehicle_priority = ["vehicle", "car", "automobile", "auto", "truck", "van", "bus", "suv", "sedan"]
        candidate_boxes.sort(
            key=lambda item: (
                1 if any(vp in item[2].lower() for vp in vehicle_priority) else 0,
                item[1] # Confidence
            ),
            reverse=True
        )

        # Assign candidate bounding boxes to vehicles using centroid proximity
        used_indices = set()
        for car_id, vehicle in self.vehicles.items():
            best_idx = -1
            min_dist = float('inf')

            for idx, (box, conf, label) in enumerate(candidate_boxes):
                if idx in used_indices:
                    continue

                cx = (box[0] + box[2]) / 2.0
                cy = (box[1] + box[3]) / 2.0

                if vehicle.x == 0.0 and vehicle.y == 0.0:
                    # First detection - lock onto candidate
                    best_idx = idx
                    break

                dist = math.hypot(cx - vehicle.x, cy - vehicle.y)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx

            if best_idx != -1:
                used_indices.add(best_idx)
                box, conf, label = candidate_boxes[best_idx]
                vehicle.update_detection(box, conf, label, self.track_scale_meters)
            else:
                vehicle.frames_since_seen += 1
                if vehicle.frames_since_seen > 12:
                    vehicle.is_detected = False

        return self.vehicles

    def check_line_crossing(self, vehicle_id: str) -> bool:
        """Check if vehicle crossed the virtual finish line on this step."""
        v = self.vehicles.get(vehicle_id)
        if not v or not v.is_detected:
            return False

        p_prev = (v.prev_x, v.prev_y)
        p_curr = (v.x, v.y)
        f1, f2 = self.finish_line

        if p_prev == p_curr or (p_prev[0] == 0.0 and p_prev[1] == 0.0):
            return False

        return LineCrossingDetector.intersects(p_prev, p_curr, f1, f2)
