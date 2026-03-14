"""Vehicle data link — reads steering, speed, indicators from OBD-II dongle."""

import logging
import threading
import time

from config import Config

log = logging.getLogger("vehicle")


class VehicleDataLink:
    """Reads vehicle telemetry from OBD-II Bluetooth dongle.

    Provides steering angle, speed, indicator state, and brake status.
    Falls back to neutral defaults if OBD-II is unavailable (Phase 1).
    """

    def __init__(self, config: Config):
        self.config = config
        self._state = {
            "speed_kmh": 0.0,
            "steering_angle": 0.0,  # degrees, negative = left
            "left_indicator": False,
            "right_indicator": False,
            "braking": False,
            "throttle_pct": 0.0,
        }
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._connection = None

    def start(self):
        if not self.config.obd_enabled:
            log.info("OBD-II disabled — using neutral vehicle state")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._connection:
            self._connection.close()

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def update_from_carla(self, data: dict):
        """Update vehicle state from CARLA simulation data."""
        with self._lock:
            self._state.update(data)

    def _poll_loop(self):
        """Poll OBD-II dongle for vehicle data."""
        try:
            import obd

            log.info("Connecting to OBD-II on %s", self.config.obd_port)
            self._connection = obd.OBD(self.config.obd_port)

            if not self._connection.is_connected():
                log.warning("OBD-II connection failed — falling back to defaults")
                return

            log.info("OBD-II connected: %s", self._connection.protocol_name())
        except Exception as e:
            log.warning("OBD-II init failed: %s — using defaults", e)
            return

        while self._running:
            try:
                speed = self._connection.query(obd.commands.SPEED)
                if speed and not speed.is_null():
                    with self._lock:
                        self._state["speed_kmh"] = speed.value.magnitude

                throttle = self._connection.query(obd.commands.THROTTLE_POS)
                if throttle and not throttle.is_null():
                    with self._lock:
                        self._state["throttle_pct"] = throttle.value.magnitude

                # Steering angle is a manufacturer-specific PID —
                # not all trucks expose it via standard OBD-II.
                # On trucks that support it, it's typically PID 0x0138.
                # For now we log what's available and add custom PIDs later.

            except Exception as e:
                log.debug("OBD-II poll error: %s", e)

            time.sleep(0.1)  # ~10Hz polling
