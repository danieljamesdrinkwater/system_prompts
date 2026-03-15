"""Radar receiver — listens for UDP packets from ESP32 radar pods."""

import json
import logging
import socket
import threading
import time

from config import Config

log = logging.getLogger("radar")


class RadarReceiver:
    """Receives radar proximity data from ESP32 pods over WiFi/UDP.

    Each ESP32 pod sends JSON packets like:
        {"pod_id": "radar_left_front", "distance": 2.3, "moving": true, "energy": 45}

    The receiver keeps only the latest reading per pod.
    """

    def __init__(self, config: Config):
        self.config = config
        self._data = {}  # pod_id → latest reading
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._sock = None

    def start(self):
        if not self.config.radar_enabled:
            log.info("Radar disabled in config")
            return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.config.radar_port))
        self._sock.settimeout(1.0)

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Radar receiver listening on UDP port %d", self.config.radar_port)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._sock:
            self._sock.close()

    def get_latest(self) -> dict:
        """Return dict of {pod_id: {distance, moving, energy}}.

        Entries older than stale_timeout are excluded.
        """
        now = time.monotonic()
        timeout = getattr(self.config, "radar_stale_timeout", 2.0)
        with self._lock:
            return {
                pod_id: data
                for pod_id, data in self._data.items()
                if now - data.get("_received", 0) < timeout
            }

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                packet = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                log.debug("Bad packet from %s", addr)
                continue

            pod_id = packet.get("pod_id")
            if not pod_id:
                continue

            with self._lock:
                self._data[pod_id] = {
                    "distance": packet.get("distance", 0),
                    "moving": packet.get("moving", False),
                    "energy": packet.get("energy", 0),
                    "timestamp": packet.get("t", 0),
                    "_received": time.monotonic(),
                }
