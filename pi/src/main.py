#!/usr/bin/env python3
"""HGV-ADAS: Main detection pipeline.

Ingests camera streams + radar pod data + OBD-II vehicle telemetry,
runs YOLOv8 object detection, and generates audio/visual alerts.
"""

import argparse
import logging
import signal
import sys
import threading
import time

from camera import CameraManager
from detector import Detector
from tracker import Tracker
from alert import AlertEngine
from radar import RadarReceiver
from vehicle import VehicleDataLink
from display import Display
from health import HealthMonitor
from recorder import Recorder
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("hgv-adas")


class Pipeline:
    """Main ADAS pipeline: ingest → detect → fuse → alert → display."""

    def __init__(self, config: Config):
        self.config = config
        self.running = False

        self.cameras = CameraManager(config)
        self.detector = Detector(config)
        self.trackers = {}  # cam_id → Tracker
        self.alert_engine = AlertEngine(config)
        self.radar = RadarReceiver(config)
        self.vehicle = VehicleDataLink(config)
        self.display = Display(config)
        self.health = HealthMonitor(config)
        self.recorder = Recorder(config)

    def start(self):
        self.running = True
        log.info("Starting HGV-ADAS pipeline")

        self.radar.start()
        self.vehicle.start()
        self.cameras.start()
        self.health.start()

        log.info("All subsystems started — entering main loop")
        self.alert_engine.speak("System active")

        try:
            self._run_loop()
        except KeyboardInterrupt:
            log.info("Interrupted")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        self.cameras.stop()
        self.radar.stop()
        self.vehicle.stop()
        self.health.stop()
        self.recorder.close()
        self.display.close()
        log.info("Pipeline stopped")

    def _run_loop(self):
        while self.running:
            frames = self.cameras.get_frames()
            if not frames:
                time.sleep(0.01)
                continue

            # Run YOLOv8 detection + tracking on each camera frame
            all_detections = {}
            all_tracks = []
            for cam_id, frame in frames.items():
                detections = self.detector.detect(frame)
                all_detections[cam_id] = detections
                self.health.record(cam_id)

                # Track objects across frames
                if cam_id not in self.trackers:
                    self.trackers[cam_id] = Tracker(self.config)
                tracks = self.trackers[cam_id].update(detections)
                all_tracks.extend(tracks)

            # Get radar proximity data (stale entries auto-filtered)
            radar_data = self.radar.get_latest()

            # Get vehicle state (steering, speed, indicators)
            vehicle_state = self.vehicle.get_state()

            # Fuse detections + radar + vehicle data → alert decisions
            alerts = self.alert_engine.evaluate(
                all_detections, radar_data, vehicle_state
            )

            # Render display with overlays and alert indicators
            self.display.render(frames, all_detections, alerts, radar_data)

            # Fire audio alerts
            for alert in alerts:
                self.alert_engine.fire(alert)

            # Record telemetry
            self.recorder.record(
                all_detections, alerts, radar_data, vehicle_state,
                tracks=all_tracks, frames=frames,
            )


def main():
    parser = argparse.ArgumentParser(description="HGV-ADAS Detection Pipeline")
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--mode",
        choices=["live", "demo", "carla"],
        default="live",
        help="live=real cameras, demo=video files, carla=CARLA sim",
    )
    parser.add_argument(
        "--video",
        help="Video file path for demo mode",
    )
    args = parser.parse_args()

    config = Config.load(args.config)
    config.mode = args.mode
    if args.video:
        config.demo_video = args.video

    pipeline = Pipeline(config)

    # Graceful shutdown on SIGTERM
    signal.signal(signal.SIGTERM, lambda *_: pipeline.stop())

    pipeline.start()


if __name__ == "__main__":
    main()
