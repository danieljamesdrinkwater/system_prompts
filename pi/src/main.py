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
from alert import AlertEngine
from radar import RadarReceiver
from vehicle import VehicleDataLink
from display import Display
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
        self.alert_engine = AlertEngine(config)
        self.radar = RadarReceiver(config)
        self.vehicle = VehicleDataLink(config)
        self.display = Display(config)

    def start(self):
        self.running = True
        log.info("Starting HGV-ADAS pipeline")

        self.radar.start()
        self.vehicle.start()
        self.cameras.start()

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
        self.display.close()
        log.info("Pipeline stopped")

    def _run_loop(self):
        while self.running:
            frames = self.cameras.get_frames()
            if not frames:
                time.sleep(0.01)
                continue

            # Run YOLOv8 detection on each camera frame
            all_detections = {}
            for cam_id, frame in frames.items():
                detections = self.detector.detect(frame)
                all_detections[cam_id] = detections

            # Get radar proximity data
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
