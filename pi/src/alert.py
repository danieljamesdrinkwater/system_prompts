"""Alert engine — evaluates detections + radar + vehicle state → alert decisions."""

import logging
import threading
import time
from dataclasses import dataclass
from enum import IntEnum

import pyttsx3

from config import Config

log = logging.getLogger("alert")


class AlertLevel(IntEnum):
    NONE = 0
    CAUTION = 1   # Amber overlay
    WARNING = 2   # Red overlay + tone
    DANGER = 3    # Red flash + spoken alert


@dataclass
class Alert:
    level: AlertLevel
    zone: str           # "left", "forward", "rear"
    message: str        # Spoken message for DANGER level
    class_name: str     # What was detected
    distance: float     # Metres (from radar or estimate)
    is_turn_collision: bool = False  # Turning into detected object


# Cooldown to avoid alert spam (seconds per zone)
_ALERT_COOLDOWN = {
    AlertLevel.CAUTION: 5.0,
    AlertLevel.WARNING: 2.0,
    AlertLevel.DANGER: 1.0,
}


class AlertEngine:
    """Fuses detection + radar + vehicle data into alert decisions."""

    def __init__(self, config: Config):
        self.config = config
        self._last_alert_time = {}  # zone → timestamp
        self._tts_lock = threading.Lock()

        try:
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", config.speech_rate)
            self._tts.setProperty("volume", config.alert_volume)
        except Exception:
            log.warning("Text-to-speech init failed — audio alerts disabled")
            self._tts = None

    def evaluate(self, detections: dict, radar_data: dict, vehicle_state: dict) -> list:
        """Evaluate all sensor data and return list of Alert objects.

        Args:
            detections: {cam_id: [Detection, ...]}
            radar_data: {pod_id: {"distance": float, "moving": bool}}
            vehicle_state: {"speed_kmh": float, "steering_angle": float,
                           "left_indicator": bool, "braking": bool}
        """
        alerts = []
        speed = vehicle_state.get("speed_kmh", 0)
        steering = vehicle_state.get("steering_angle", 0)
        left_indicator = vehicle_state.get("left_indicator", False)

        for cam_id, dets in detections.items():
            zone = self._cam_zone(cam_id)

            for det in dets:
                # Skip vehicle detections on the left side at high speed
                # (they're just traffic in the adjacent lane)
                if (
                    zone == "left"
                    and speed > self.config.low_speed_threshold
                    and det.class_name in ("car", "bus", "truck")
                ):
                    continue

                # Determine distance — prefer radar, fall back to camera estimate
                distance = self._get_distance(det, zone, radar_data)

                # Determine alert level from distance
                level = self._distance_to_level(distance)

                # ESCALATION: turning left with cyclist/person in left blind spot
                is_turn_collision = False
                if (
                    zone == "left"
                    and det.class_name in ("person", "bicycle", "motorcycle")
                    and steering < -self.config.steering_left_threshold
                    and (left_indicator or speed < self.config.low_speed_threshold)
                ):
                    level = AlertLevel.DANGER
                    is_turn_collision = True

                if level == AlertLevel.NONE:
                    continue

                # Build spoken message
                message = self._build_message(det, zone, distance, is_turn_collision)

                alert = Alert(
                    level=level,
                    zone=zone,
                    message=message,
                    class_name=det.class_name,
                    distance=distance,
                    is_turn_collision=is_turn_collision,
                )
                alerts.append(alert)

        return alerts

    def fire(self, alert: Alert):
        """Execute an alert — play audio if not in cooldown."""
        now = time.time()
        key = (alert.zone, alert.level)
        cooldown = _ALERT_COOLDOWN.get(alert.level, 2.0)

        last = self._last_alert_time.get(key, 0)
        if now - last < cooldown:
            return

        self._last_alert_time[key] = now

        if alert.level == AlertLevel.DANGER:
            self.speak(alert.message)
        elif alert.level == AlertLevel.WARNING:
            log.info("WARNING: %s", alert.message)

    def speak(self, text: str):
        """Speak a warning message via TTS (non-blocking)."""
        if not self._tts:
            log.info("SPEAK: %s", text)
            return

        def _say():
            with self._tts_lock:
                try:
                    self._tts.say(text)
                    self._tts.runAndWait()
                except Exception as e:
                    log.warning("TTS error: %s", e)

        threading.Thread(target=_say, daemon=True).start()

    def _cam_zone(self, cam_id: str) -> str:
        """Map camera ID to zone name."""
        zone_map = {"left": "left", "forward": "forward", "rear": "rear"}
        return zone_map.get(cam_id, cam_id)

    def _get_distance(self, det, zone: str, radar_data: dict) -> float:
        """Get best available distance for a detection."""
        # Check if radar has data for this zone
        radar_zones = {
            "left": ["radar_left_front", "radar_left_rear"],
            "rear": ["radar_rear"],
        }
        for pod_id in radar_zones.get(zone, []):
            if pod_id in radar_data and radar_data[pod_id].get("distance"):
                return radar_data[pod_id]["distance"]

        # Fall back to camera-based estimate
        if det.distance_estimate:
            return det.distance_estimate

        return 10.0  # Unknown — assume safe distance

    def _distance_to_level(self, distance: float) -> AlertLevel:
        if distance <= self.config.danger_distance:
            return AlertLevel.DANGER
        if distance <= self.config.warning_distance:
            return AlertLevel.WARNING
        if distance <= self.config.caution_distance:
            return AlertLevel.CAUTION
        return AlertLevel.NONE

    def _build_message(
        self, det, zone: str, distance: float, is_turn_collision: bool
    ) -> str:
        """Build spoken alert message."""
        class_labels = {
            "person": "person",
            "bicycle": "cyclist",
            "motorcycle": "motorbike",
            "car": "vehicle",
            "bus": "bus",
            "truck": "truck",
        }
        label = class_labels.get(det.class_name, det.class_name)
        side = {"left": "left side", "forward": "ahead", "rear": "behind"}.get(
            zone, zone
        )

        if is_turn_collision:
            return f"STOP. {label} {side}"

        if distance < 2.0:
            return f"{label} {side}"

        return f"{label} {side}, {distance:.0f} metres"
