#!/usr/bin/env python3
"""CARLA-to-pipeline bridge — feeds CARLA sensor data into the Pi detection pipeline.

Usage:
    python carla_bridge.py --scenario blind_spot_left_turn
    python carla_bridge.py --scenario free_drive --record

This runs both the CARLA sim and the full Pi pipeline (detection, tracking,
alerts, display) in one process, so you can validate the entire stack
without any hardware.
"""

import argparse
import logging
import math
import sys
import time

import carla
import cv2
import numpy as np

# Add Pi source to path so we can import the pipeline modules
sys.path.insert(0, "../../pi/src")

from config import Config, CameraConfig
from detector import Detector
from tracker import Tracker
from alert import AlertEngine
from display import Display
from health import HealthMonitor
from recorder import Recorder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("carla-bridge")

# Sensor mount positions — same as run_scenario.py
SENSOR_MOUNTS = {
    "left": {
        "type": "sensor.camera.rgb",
        "x": 0.0, "y": -1.2, "z": 2.5,
        "pitch": -30, "yaw": -90, "roll": 0,
        "width": 1920, "height": 1080, "fov": 110,
    },
    "forward": {
        "type": "sensor.camera.rgb",
        "x": 2.5, "y": 0.0, "z": 3.0,
        "pitch": -5, "yaw": 0, "roll": 0,
        "width": 1920, "height": 1080, "fov": 90,
    },
    "rear": {
        "type": "sensor.camera.rgb",
        "x": -1.0, "y": 0.0, "z": 2.8,
        "pitch": -10, "yaw": 180, "roll": 0,
        "width": 1920, "height": 1080, "fov": 120,
    },
    "radar_left_front": {
        "type": "sensor.other.radar",
        "x": 1.5, "y": -1.2, "z": 1.5,
        "pitch": 0, "yaw": -90, "roll": 0,
        "range": 8, "h_fov": 60, "v_fov": 30,
    },
    "radar_left_rear": {
        "type": "sensor.other.radar",
        "x": -0.5, "y": -1.2, "z": 1.5,
        "pitch": 0, "yaw": -90, "roll": 0,
        "range": 8, "h_fov": 60, "v_fov": 30,
    },
    "radar_rear": {
        "type": "sensor.other.radar",
        "x": -1.5, "y": 0.0, "z": 1.5,
        "pitch": 0, "yaw": 180, "roll": 0,
        "range": 8, "h_fov": 60, "v_fov": 30,
    },
}


class CARLABridge:
    """Bridges CARLA simulation data into the Pi detection pipeline."""

    def __init__(self, host="localhost", port=2000, config_path="../../pi/config/default.yaml"):
        self.client = carla.Client(host, port)
        self.client.set_timeout(10.0)
        self.world = None
        self.truck = None
        self._actors = []

        # Shared sensor buffers
        self._frames = {}
        self._radar = {}

        # Load Pi pipeline config
        self.config = Config.load(config_path)
        self.config.mode = "carla"
        self.config.radar_enabled = False  # We feed radar data directly
        self.config.obd_enabled = False

        # Pipeline components
        self.detector = Detector(self.config)
        self.trackers = {}  # cam_id → Tracker
        self.alert_engine = AlertEngine(self.config)
        self.display = Display(self.config)
        self.health = HealthMonitor(self.config)
        self.recorder = Recorder(self.config)

    def setup(self, map_name="Town03"):
        log.info("Loading map: %s", map_name)
        self.world = self.client.load_world(map_name)

        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.world.set_weather(carla.WeatherParameters.ClearNoon)

        self.health.start()

    def spawn_truck(self, spawn_index=0):
        bp_lib = self.world.get_blueprint_library()
        truck_bp = bp_lib.find("vehicle.carlamotors.firetruck")
        if truck_bp is None:
            trucks = [
                bp for bp in bp_lib.filter("vehicle.*")
                if "truck" in bp.id or "van" in bp.id
            ]
            truck_bp = trucks[0] if trucks else bp_lib.filter("vehicle.*")[0]

        spawn_points = self.world.get_map().get_spawn_points()
        self.truck = self.world.spawn_actor(
            truck_bp, spawn_points[spawn_index % len(spawn_points)]
        )
        self._actors.append(self.truck)
        log.info("Truck spawned: %s", truck_bp.id)

    def attach_sensors(self):
        bp_lib = self.world.get_blueprint_library()

        for sensor_id, mount in SENSOR_MOUNTS.items():
            bp = bp_lib.find(mount["type"])

            if "camera" in mount["type"]:
                bp.set_attribute("image_size_x", str(mount["width"]))
                bp.set_attribute("image_size_y", str(mount["height"]))
                bp.set_attribute("fov", str(mount["fov"]))
            elif "radar" in mount["type"]:
                bp.set_attribute("horizontal_fov", str(mount.get("h_fov", 60)))
                bp.set_attribute("vertical_fov", str(mount.get("v_fov", 30)))
                bp.set_attribute("range", str(mount.get("range", 8)))

            transform = carla.Transform(
                carla.Location(x=mount["x"], y=mount["y"], z=mount["z"]),
                carla.Rotation(
                    pitch=mount.get("pitch", 0),
                    yaw=mount.get("yaw", 0),
                    roll=mount.get("roll", 0),
                ),
            )

            sensor = self.world.spawn_actor(bp, transform, attach_to=self.truck)
            self._actors.append(sensor)

            if "camera" in mount["type"]:
                sensor.listen(lambda img, sid=sensor_id: self._on_camera(sid, img))
            elif "radar" in mount["type"]:
                sensor.listen(lambda data, sid=sensor_id: self._on_radar(sid, data))

    def spawn_cyclist(self, offset_x=5.0, offset_y=-2.5):
        bp_lib = self.world.get_blueprint_library()
        bike_bp = bp_lib.find("vehicle.bh.crossbike")
        if bike_bp is None:
            bike_bp = bp_lib.filter("vehicle.*bike*")[0]

        truck_loc = self.truck.get_location()
        transform = carla.Transform(
            carla.Location(
                x=truck_loc.x + offset_x,
                y=truck_loc.y + offset_y,
                z=truck_loc.z + 0.5,
            ),
            carla.Rotation(yaw=self.truck.get_transform().rotation.yaw),
        )
        cyclist = self.world.spawn_actor(bike_bp, transform)
        self._actors.append(cyclist)
        cyclist.set_autopilot(True)
        log.info("Cyclist spawned")
        return cyclist

    def spawn_pedestrian(self, offset_x=20.0, offset_y=-4.0):
        bp_lib = self.world.get_blueprint_library()
        ped_bp = bp_lib.filter("walker.pedestrian.*")[0]

        truck_loc = self.truck.get_location()
        transform = carla.Transform(
            carla.Location(
                x=truck_loc.x + offset_x,
                y=truck_loc.y + offset_y,
                z=truck_loc.z + 1.0,
            ),
        )
        pedestrian = self.world.spawn_actor(ped_bp, transform)
        self._actors.append(pedestrian)

        walker_ctrl_bp = bp_lib.find("controller.ai.walker")
        controller = self.world.spawn_actor(walker_ctrl_bp, carla.Transform(), pedestrian)
        self._actors.append(controller)
        controller.start()
        controller.go_to_location(carla.Location(
            x=truck_loc.x + offset_x, y=truck_loc.y + 3.0, z=truck_loc.z,
        ))
        controller.set_max_speed(1.4)
        log.info("Pedestrian spawned")
        return pedestrian

    def get_vehicle_state(self) -> dict:
        if not self.truck:
            return {}
        velocity = self.truck.get_velocity()
        speed_kmh = 3.6 * math.sqrt(
            velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2
        )
        control = self.truck.get_control()
        steering_angle = control.steer * 540
        return {
            "speed_kmh": speed_kmh,
            "steering_angle": steering_angle,
            "left_indicator": steering_angle < -15,
            "right_indicator": steering_angle > 15,
            "braking": control.brake > 0.1,
            "throttle_pct": control.throttle * 100,
        }

    def run_pipeline_step(self):
        """Run one full pipeline cycle: detect → track → alert → display."""
        frames = dict(self._frames)
        if not frames:
            return

        # Detect on each camera
        all_detections = {}
        all_tracks = {}
        for cam_id, frame in frames.items():
            detections = self.detector.detect(frame)
            all_detections[cam_id] = detections
            self.health.record(cam_id)

            # Track per camera
            if cam_id not in self.trackers:
                self.trackers[cam_id] = Tracker(self.config)
            tracks = self.trackers[cam_id].update(detections)
            all_tracks[cam_id] = tracks

        # Radar data — convert from CARLA format to pipeline format
        radar_data = {}
        for pod_id, dets in self._radar.items():
            if dets:
                closest = min(dets, key=lambda d: d["distance"])
                radar_data[pod_id] = {
                    "distance": closest["distance"],
                    "moving": abs(closest.get("velocity", 0)) > 0.5,
                    "energy": 50,
                }
                self.health.record(pod_id)

        vehicle_state = self.get_vehicle_state()

        # Alert evaluation
        alerts = self.alert_engine.evaluate(all_detections, radar_data, vehicle_state)

        # Display
        self.display.render(frames, all_detections, alerts, radar_data)

        # Fire audio alerts
        for alert in alerts:
            self.alert_engine.fire(alert)

        # Record telemetry
        flat_tracks = []
        for t_list in all_tracks.values():
            flat_tracks.extend(t_list)
        self.recorder.record(
            all_detections, alerts, radar_data, vehicle_state,
            tracks=flat_tracks, frames=frames,
        )

    def cleanup(self):
        log.info("Cleaning up %d actors", len(self._actors))
        for actor in reversed(self._actors):
            try:
                actor.destroy()
            except Exception:
                pass
        self._actors.clear()
        if self.world:
            settings = self.world.get_settings()
            settings.synchronous_mode = False
            self.world.apply_settings(settings)
        self.health.stop()
        self.recorder.close()
        self.display.close()

    def _on_camera(self, sensor_id, image):
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        self._frames[sensor_id] = array[:, :, :3]

    def _on_radar(self, sensor_id, data):
        detections = []
        for det in data:
            detections.append({
                "distance": det.depth,
                "velocity": det.velocity,
                "azimuth": math.degrees(det.azimuth),
            })
        self._radar[sensor_id] = detections


# ── Scenarios ──────────────────────────────────────────────────

def scenario_blind_spot(bridge: CARLABridge):
    log.info("=== Blind spot left turn (full pipeline) ===")
    bridge.setup()
    bridge.spawn_truck()
    bridge.attach_sensors()
    bridge.spawn_cyclist()
    bridge.truck.set_autopilot(True)

    for _ in range(500):
        bridge.world.tick()
        bridge.run_pipeline_step()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


def scenario_pedestrian(bridge: CARLABridge):
    log.info("=== Pedestrian crossing (full pipeline) ===")
    bridge.setup()
    bridge.spawn_truck()
    bridge.attach_sensors()
    bridge.spawn_pedestrian()
    bridge.truck.set_autopilot(True)

    for _ in range(500):
        bridge.world.tick()
        bridge.run_pipeline_step()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


def scenario_reversing(bridge: CARLABridge):
    log.info("=== Reversing (full pipeline) ===")
    bridge.setup()
    bridge.spawn_truck()
    bridge.attach_sensors()
    bridge.spawn_pedestrian(offset_x=-10.0, offset_y=0.0)

    for _ in range(300):
        bridge.world.tick()
        control = carla.VehicleControl()
        control.throttle = 0.3
        control.reverse = True
        bridge.truck.apply_control(control)
        bridge.run_pipeline_step()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


def scenario_free_drive(bridge: CARLABridge):
    log.info("=== Free drive (full pipeline) ===")
    bridge.setup()
    bridge.spawn_truck()
    bridge.attach_sensors()
    bridge.truck.set_autopilot(True)

    while True:
        bridge.world.tick()
        bridge.run_pipeline_step()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


SCENARIOS = {
    "blind_spot_left_turn": scenario_blind_spot,
    "pedestrian_crossing": scenario_pedestrian,
    "reversing": scenario_reversing,
    "free_drive": scenario_free_drive,
}


def main():
    parser = argparse.ArgumentParser(description="CARLA → Pi Pipeline Bridge")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()),
                        default="blind_spot_left_turn")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--config", default="../../pi/config/default.yaml")
    parser.add_argument("--record", action="store_true",
                        help="Enable telemetry recording")
    args = parser.parse_args()

    bridge = CARLABridge(args.host, args.port, args.config)
    if args.record:
        bridge.config.recording_enabled = True

    try:
        SCENARIOS[args.scenario](bridge)
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        bridge.cleanup()


if __name__ == "__main__":
    main()
