"""Configuration loader for HGV-ADAS."""

import os
import yaml
from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    id: str
    url: str  # RTSP/MJPEG URL or video file path
    zone: str  # "left", "forward", "rear"
    flip: bool = False


@dataclass
class Config:
    # Operating mode
    mode: str = "live"
    demo_video: str = ""

    # Detection
    model_path: str = "models/yolov8n.pt"
    confidence_threshold: float = 0.45
    target_classes: list = field(
        default_factory=lambda: ["person", "bicycle", "motorcycle", "car", "bus", "truck"]
    )

    # Cameras
    cameras: list = field(default_factory=list)

    # Radar
    radar_port: int = 5005  # UDP port for ESP32 radar pods
    radar_enabled: bool = True

    # Vehicle data (OBD-II)
    obd_enabled: bool = False
    obd_port: str = ""  # Bluetooth serial port e.g. /dev/rfcomm0

    # Alert thresholds
    caution_distance: float = 6.0   # metres — amber
    warning_distance: float = 3.0   # metres — red + tone
    danger_distance: float = 1.5    # metres — red flash + spoken

    # Turn-into-collision
    steering_left_threshold: float = 15.0  # degrees — trigger escalation
    low_speed_threshold: float = 24.0      # km/h (~15mph) — urban mode

    # Display
    display_width: int = 1024
    display_height: int = 600
    fullscreen: bool = False

    # Tracker
    tracker_iou_threshold: float = 0.25
    tracker_max_misses: int = 8

    # Radar
    radar_stale_timeout: float = 2.0  # seconds — drop stale pod data

    # Health
    health_stale_timeout: float = 3.0  # seconds — mark sensor offline

    # Recording
    recording_enabled: bool = False
    recording_dir: str = "recordings"
    recording_save_frames: bool = False
    recording_frame_interval: int = 30  # Save every Nth frame
    recording_max_file_mb: int = 50

    # Audio
    alert_volume: float = 1.0
    speech_rate: int = 180  # words per minute

    @classmethod
    def load(cls, path: str) -> "Config":
        """Load config from YAML file, falling back to defaults."""
        config = cls()

        if os.path.exists(path):
            with open(path) as f:
                data = yaml.safe_load(f) or {}

            for key, value in data.items():
                if key == "cameras":
                    config.cameras = [CameraConfig(**c) for c in value]
                elif hasattr(config, key):
                    setattr(config, key, value)

        # Default cameras if none configured
        if not config.cameras:
            config.cameras = [
                CameraConfig(id="left", url="0", zone="left"),
                CameraConfig(id="forward", url="1", zone="forward"),
                CameraConfig(id="rear", url="2", zone="rear"),
            ]

        return config
