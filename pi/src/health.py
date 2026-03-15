"""Sensor health monitor — tracks camera FPS, radar packet rate, system temps."""

import logging
import os
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("health")


@dataclass
class SensorStatus:
    name: str
    alive: bool = False
    fps: float = 0.0         # Frames or packets per second
    last_seen: float = 0.0   # monotonic timestamp
    total_count: int = 0
    _window: list = field(default_factory=list)  # Timestamps for FPS calc

    def record(self):
        now = time.monotonic()
        self.last_seen = now
        self.alive = True
        self.total_count += 1
        self._window.append(now)
        # Keep 1-second window
        cutoff = now - 1.0
        self._window = [t for t in self._window if t > cutoff]
        self.fps = len(self._window)

    def check_stale(self, timeout: float):
        if self.last_seen == 0:
            return
        elapsed = time.monotonic() - self.last_seen
        if elapsed > timeout:
            self.alive = False
            self.fps = 0.0


class HealthMonitor:
    """Monitors sensor health and system vitals."""

    def __init__(self, config):
        self.stale_timeout = getattr(config, "health_stale_timeout", 3.0)
        self._sensors: dict[str, SensorStatus] = {}
        self._lock = threading.Lock()
        self._cpu_temp = 0.0
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def record(self, sensor_id: str):
        """Record a frame/packet received from a sensor."""
        with self._lock:
            if sensor_id not in self._sensors:
                self._sensors[sensor_id] = SensorStatus(name=sensor_id)
            self._sensors[sensor_id].record()

    def get_status(self) -> dict:
        """Return health status for all sensors + system."""
        with self._lock:
            for s in self._sensors.values():
                s.check_stale(self.stale_timeout)

            return {
                "sensors": {
                    sid: {
                        "alive": s.alive,
                        "fps": round(s.fps, 1),
                        "total": s.total_count,
                    }
                    for sid, s in self._sensors.items()
                },
                "cpu_temp": self._cpu_temp,
            }

    def _monitor_loop(self):
        while self._running:
            self._cpu_temp = self._read_cpu_temp()
            time.sleep(2.0)

    def _read_cpu_temp(self) -> float:
        """Read Pi CPU temperature."""
        try:
            path = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(path):
                with open(path) as f:
                    return int(f.read().strip()) / 1000.0
        except Exception:
            pass
        return 0.0
