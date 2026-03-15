"""Telemetry recorder — logs detections, alerts, and vehicle state to disk."""

import json
import logging
import os
import threading
import time
from datetime import datetime

import cv2

log = logging.getLogger("recorder")


class Recorder:
    """Records telemetry data to JSON-lines files and optional frame snapshots."""

    def __init__(self, config):
        self.enabled = getattr(config, "recording_enabled", False)
        self.output_dir = getattr(config, "recording_dir", "recordings")
        self.save_frames = getattr(config, "recording_save_frames", False)
        self.frame_interval = getattr(config, "recording_frame_interval", 30)
        self._max_file_mb = getattr(config, "recording_max_file_mb", 50)

        self._log_file = None
        self._frame_count = 0
        self._session_dir = ""
        self._lock = threading.Lock()

        if self.enabled:
            self._init_session()

    def _init_session(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(self.output_dir, stamp)
        os.makedirs(self._session_dir, exist_ok=True)

        if self.save_frames:
            os.makedirs(os.path.join(self._session_dir, "frames"), exist_ok=True)

        log_path = os.path.join(self._session_dir, "telemetry.jsonl")
        self._log_file = open(log_path, "a")
        log.info("Recording to %s", self._session_dir)

    def record(self, detections: dict, alerts: list, radar_data: dict,
               vehicle_state: dict, tracks: list = None, frames: dict = None):
        """Record a single pipeline cycle."""
        if not self.enabled or not self._log_file:
            return

        entry = {
            "t": time.time(),
            "detections": {
                cam_id: [
                    {
                        "class": d.class_name,
                        "conf": round(d.confidence, 3),
                        "bbox": [round(v, 1) for v in d.bbox],
                        "dist": round(d.distance_estimate, 2) if d.distance_estimate else None,
                    }
                    for d in dets
                ]
                for cam_id, dets in detections.items()
            },
            "alerts": [
                {
                    "level": a.level.name,
                    "zone": a.zone,
                    "message": a.message,
                    "class": a.class_name,
                    "dist": round(a.distance, 2),
                    "turn_collision": a.is_turn_collision,
                }
                for a in alerts
            ],
            "radar": {
                pod_id: {
                    "dist": round(d.get("distance", 0), 2),
                    "moving": d.get("moving", False),
                }
                for pod_id, d in radar_data.items()
            },
            "vehicle": {
                k: round(v, 2) if isinstance(v, float) else v
                for k, v in vehicle_state.items()
            },
        }

        if tracks:
            entry["tracks"] = [
                {
                    "id": t.track_id,
                    "class": t.class_name,
                    "vel": [round(t.velocity[0], 1), round(t.velocity[1], 1)],
                    "hits": t.hits,
                    "dist": round(t.distance_estimate, 2) if t.distance_estimate else None,
                }
                for t in tracks
                if t.is_confirmed
            ]

        with self._lock:
            self._log_file.write(json.dumps(entry) + "\n")

            # Rotate if file is too large
            if self._log_file.tell() > self._max_file_mb * 1024 * 1024:
                self._rotate_log()

        # Save frame snapshots at interval
        self._frame_count += 1
        if self.save_frames and frames and self._frame_count % self.frame_interval == 0:
            self._save_frames(frames)

    def close(self):
        if self._log_file:
            self._log_file.close()

    def _save_frames(self, frames: dict):
        stamp = int(time.time() * 1000)
        for cam_id, frame in frames.items():
            path = os.path.join(
                self._session_dir, "frames", f"{stamp}_{cam_id}.jpg"
            )
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

    def _rotate_log(self):
        self._log_file.close()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(self._session_dir, f"telemetry_{stamp}.jsonl")
        self._log_file = open(log_path, "a")
        log.info("Log rotated to %s", log_path)
