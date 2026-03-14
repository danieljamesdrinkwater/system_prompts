#!/usr/bin/env python3
"""CARLA simulation harness for HGV-ADAS testing.

Spawns a truck with virtual cameras and radar sensors positioned
to match the real hardware design. Runs scripted scenarios
(cyclist in blind spot, pedestrian crossing, reversing) and feeds
sensor data to the Pi detection pipeline.

Usage:
    python run_scenario.py --scenario blind_spot_left_turn
    python run_scenario.py --scenario pedestrian_crossing
    python run_scenario.py --scenario reversing
    python run_scenario.py --scenario free_drive
"""

import argparse
import logging
import math
import sys
import time

import carla
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("carla-harness")

# Sensor mount positions relative to truck origin (metres)
# Matches the real hardware placement design
SENSOR_MOUNTS = {
    "cam_left": {
        "type": "sensor.camera.rgb",
        "x": 0.0, "y": -1.2, "z": 2.5,  # Left side, below window height
        "pitch": -30, "yaw": -90, "roll": 0,  # Angled down, facing left
        "width": 1920, "height": 1080, "fov": 110,
    },
    "cam_forward": {
        "type": "sensor.camera.rgb",
        "x": 2.5, "y": 0.0, "z": 3.0,  # Top of windscreen
        "pitch": -5, "yaw": 0, "roll": 0,  # Slightly downward, facing forward
        "width": 1920, "height": 1080, "fov": 90,
    },
    "cam_rear": {
        "type": "sensor.camera.rgb",
        "x": -1.0, "y": 0.0, "z": 2.8,  # Rear of cab
        "pitch": -10, "yaw": 180, "roll": 0,  # Facing backward
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


class SensorData:
    """Stores latest sensor readings."""

    def __init__(self):
        self.frames = {}  # sensor_id → numpy frame
        self.radar = {}   # sensor_id → list of detections


class SimHarness:
    """CARLA simulation harness for HGV-ADAS testing."""

    def __init__(self, host="localhost", port=2000):
        self.client = carla.Client(host, port)
        self.client.set_timeout(10.0)
        self.world = None
        self.truck = None
        self.sensors = {}
        self.sensor_data = SensorData()
        self._actors = []

    def setup(self, map_name="Town03"):
        """Load map and configure simulation."""
        log.info("Loading map: %s", map_name)
        self.world = self.client.load_world(map_name)

        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05  # 20 FPS
        self.world.apply_settings(settings)

        # Set weather — overcast for consistent lighting
        weather = carla.WeatherParameters.ClearNoon
        self.world.set_weather(weather)

        log.info("World ready")

    def spawn_truck(self, spawn_index=0):
        """Spawn the truck at a map spawn point."""
        bp_lib = self.world.get_blueprint_library()

        # Use a large vehicle as truck proxy
        # CARLA has limited truck models — use the largest available
        truck_bp = bp_lib.find("vehicle.carlamotors.firetruck")
        if truck_bp is None:
            # Fallback to any large vehicle
            trucks = [
                bp for bp in bp_lib.filter("vehicle.*")
                if "truck" in bp.id or "van" in bp.id
            ]
            truck_bp = trucks[0] if trucks else bp_lib.filter("vehicle.*")[0]

        spawn_points = self.world.get_map().get_spawn_points()
        spawn = spawn_points[spawn_index % len(spawn_points)]

        self.truck = self.world.spawn_actor(truck_bp, spawn)
        self._actors.append(self.truck)
        log.info("Truck spawned: %s at %s", truck_bp.id, spawn.location)

        return self.truck

    def attach_sensors(self):
        """Attach cameras and radar to the truck matching real hardware positions."""
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

            # Register callbacks
            if "camera" in mount["type"]:
                sensor.listen(lambda img, sid=sensor_id: self._on_camera(sid, img))
            elif "radar" in mount["type"]:
                sensor.listen(lambda data, sid=sensor_id: self._on_radar(sid, data))

            self.sensors[sensor_id] = sensor
            log.info("Sensor attached: %s", sensor_id)

    def spawn_cyclist(self, offset_x=15.0, offset_y=-3.0):
        """Spawn a cyclist near the truck's left side for blind spot testing."""
        bp_lib = self.world.get_blueprint_library()

        # Spawn a bicycle + rider
        bike_bp = bp_lib.find("vehicle.bh.crossbike")
        if bike_bp is None:
            bike_bp = bp_lib.filter("vehicle.*bike*")[0]

        truck_loc = self.truck.get_location()
        bike_transform = carla.Transform(
            carla.Location(
                x=truck_loc.x + offset_x,
                y=truck_loc.y + offset_y,
                z=truck_loc.z + 0.5,
            ),
            carla.Rotation(yaw=self.truck.get_transform().rotation.yaw),
        )

        cyclist = self.world.spawn_actor(bike_bp, bike_transform)
        self._actors.append(cyclist)

        # Set cyclist moving forward
        cyclist.set_autopilot(True)
        log.info("Cyclist spawned at offset (%.1f, %.1f)", offset_x, offset_y)

        return cyclist

    def spawn_pedestrian(self, offset_x=10.0, offset_y=-2.0):
        """Spawn a pedestrian near the truck."""
        bp_lib = self.world.get_blueprint_library()

        ped_bps = bp_lib.filter("walker.pedestrian.*")
        ped_bp = ped_bps[0]

        truck_loc = self.truck.get_location()
        ped_transform = carla.Transform(
            carla.Location(
                x=truck_loc.x + offset_x,
                y=truck_loc.y + offset_y,
                z=truck_loc.z + 1.0,
            ),
        )

        pedestrian = self.world.spawn_actor(ped_bp, ped_transform)
        self._actors.append(pedestrian)

        # Make pedestrian walk across the road
        walker_ctrl_bp = bp_lib.find("controller.ai.walker")
        controller = self.world.spawn_actor(walker_ctrl_bp, carla.Transform(), pedestrian)
        self._actors.append(controller)

        controller.start()
        # Walk toward the truck's path
        target = carla.Location(
            x=truck_loc.x + offset_x,
            y=truck_loc.y + 3.0,
            z=truck_loc.z,
        )
        controller.go_to_location(target)
        controller.set_max_speed(1.4)  # Normal walking speed

        log.info("Pedestrian spawned, walking across path")
        return pedestrian

    def get_vehicle_state(self) -> dict:
        """Read truck telemetry — simulates OBD-II data."""
        if not self.truck:
            return {}

        velocity = self.truck.get_velocity()
        speed_kmh = 3.6 * math.sqrt(
            velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2
        )

        control = self.truck.get_control()
        # CARLA steer is -1.0 to 1.0, convert to degrees (approx)
        steering_angle = control.steer * 540  # Typical truck steering ratio

        return {
            "speed_kmh": speed_kmh,
            "steering_angle": steering_angle,
            "left_indicator": steering_angle < -15,  # Approximate
            "right_indicator": steering_angle > 15,
            "braking": control.brake > 0.1,
            "throttle_pct": control.throttle * 100,
        }

    def tick(self):
        """Advance simulation one step."""
        self.world.tick()

    def cleanup(self):
        """Destroy all spawned actors."""
        log.info("Cleaning up %d actors", len(self._actors))
        for actor in reversed(self._actors):
            try:
                actor.destroy()
            except Exception:
                pass
        self._actors.clear()

        # Restore async mode
        if self.world:
            settings = self.world.get_settings()
            settings.synchronous_mode = False
            self.world.apply_settings(settings)

    def _on_camera(self, sensor_id, image):
        """Camera callback — convert CARLA image to numpy array."""
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))  # BGRA
        self.sensor_data.frames[sensor_id] = array[:, :, :3]  # BGR

    def _on_radar(self, sensor_id, data):
        """Radar callback — extract detection list."""
        detections = []
        for det in data:
            detections.append({
                "distance": det.depth,
                "velocity": det.velocity,
                "azimuth": math.degrees(det.azimuth),
                "altitude": math.degrees(det.altitude),
            })
        self.sensor_data.radar[sensor_id] = detections


# ── Scenario Runners ────────────────────────────────────────────

def scenario_blind_spot_left_turn(harness: SimHarness):
    """Scenario: Truck turns left with cyclist in blind spot."""
    log.info("=== SCENARIO: Blind spot left turn ===")
    harness.setup()
    harness.spawn_truck()
    harness.attach_sensors()

    # Spawn cyclist alongside the truck's left
    harness.spawn_cyclist(offset_x=5.0, offset_y=-2.5)

    # Drive truck forward and turn left
    harness.truck.set_autopilot(True)

    for step in range(500):
        harness.tick()

        # Display camera feeds
        for cam_id in ("cam_left", "cam_forward", "cam_rear"):
            frame = harness.sensor_data.frames.get(cam_id)
            if frame is not None:
                display = cv2.resize(frame, (640, 360))
                cv2.imshow(cam_id, display)

        # Print radar detections
        for radar_id, dets in harness.sensor_data.radar.items():
            for d in dets:
                if d["distance"] < 8.0:
                    log.info(
                        "%s: %.1fm, vel=%.1f, az=%.1f°",
                        radar_id, d["distance"], d["velocity"], d["azimuth"],
                    )

        # Print vehicle state
        state = harness.get_vehicle_state()
        if step % 20 == 0:
            log.info(
                "Vehicle: %.0f km/h, steer=%.0f°, brake=%s",
                state["speed_kmh"], state["steering_angle"], state["braking"],
            )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


def scenario_pedestrian_crossing(harness: SimHarness):
    """Scenario: Pedestrian walks across the truck's path."""
    log.info("=== SCENARIO: Pedestrian crossing ===")
    harness.setup()
    harness.spawn_truck()
    harness.attach_sensors()

    harness.spawn_pedestrian(offset_x=20.0, offset_y=-4.0)
    harness.truck.set_autopilot(True)

    for step in range(500):
        harness.tick()

        for cam_id in ("cam_left", "cam_forward"):
            frame = harness.sensor_data.frames.get(cam_id)
            if frame is not None:
                cv2.imshow(cam_id, cv2.resize(frame, (640, 360)))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


def scenario_reversing(harness: SimHarness):
    """Scenario: Truck reverses toward obstacles."""
    log.info("=== SCENARIO: Reversing ===")
    harness.setup()
    harness.spawn_truck()
    harness.attach_sensors()

    # Spawn a pedestrian behind the truck
    harness.spawn_pedestrian(offset_x=-10.0, offset_y=0.0)

    # Manual reverse — apply reverse throttle
    for step in range(300):
        harness.tick()

        control = carla.VehicleControl()
        control.throttle = 0.3
        control.reverse = True
        harness.truck.apply_control(control)

        frame = harness.sensor_data.frames.get("cam_rear")
        if frame is not None:
            cv2.imshow("cam_rear", cv2.resize(frame, (640, 360)))

        for radar_id, dets in harness.sensor_data.radar.items():
            if "rear" in radar_id:
                for d in dets:
                    if d["distance"] < 5.0:
                        log.info("REAR: %.1fm", d["distance"])

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


def scenario_free_drive(harness: SimHarness):
    """Free drive — truck on autopilot with all sensors active."""
    log.info("=== SCENARIO: Free drive ===")
    harness.setup()
    harness.spawn_truck()
    harness.attach_sensors()
    harness.truck.set_autopilot(True)

    log.info("Free driving — press Q to quit")

    while True:
        harness.tick()

        for cam_id in ("cam_left", "cam_forward", "cam_rear"):
            frame = harness.sensor_data.frames.get(cam_id)
            if frame is not None:
                cv2.imshow(cam_id, cv2.resize(frame, (640, 360)))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


# ── Entry Point ─────────────────────────────────────────────────

SCENARIOS = {
    "blind_spot_left_turn": scenario_blind_spot_left_turn,
    "pedestrian_crossing": scenario_pedestrian_crossing,
    "reversing": scenario_reversing,
    "free_drive": scenario_free_drive,
}


def main():
    parser = argparse.ArgumentParser(description="HGV-ADAS CARLA Test Harness")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="blind_spot_left_turn",
        help="Scenario to run",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()

    harness = SimHarness(args.host, args.port)

    try:
        SCENARIOS[args.scenario](harness)
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        harness.cleanup()


if __name__ == "__main__":
    main()
