"""Camera manager — ingests RTSP/MJPEG/video streams from wireless cameras."""

import logging
import threading
import time

import cv2
import numpy as np

from config import Config

log = logging.getLogger("camera")


class CameraStream:
    """Threaded camera stream reader. Keeps only the latest frame."""

    def __init__(self, cam_config):
        self.id = cam_config.id
        self.zone = cam_config.zone
        self.flip = cam_config.flip
        self._url = cam_config.url
        self._cap = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        url = self._url
        # Numeric string means local camera index
        if url.isdigit():
            url = int(url)

        self._cap = cv2.VideoCapture(url)
        if not self._cap.isOpened():
            log.warning("Camera %s: failed to open %s", self.id, self._url)
            return

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        log.info("Camera %s started: %s", self.id, self._url)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def _read_loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                # For video files, loop back to start
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.1)
                continue

            if self.flip:
                frame = cv2.flip(frame, 1)

            with self._lock:
                self._frame = frame


class CameraManager:
    """Manages multiple camera streams."""

    def __init__(self, config: Config):
        self.streams = {}
        for cam in config.cameras:
            self.streams[cam.id] = CameraStream(cam)

    def start(self):
        for stream in self.streams.values():
            stream.start()

    def stop(self):
        for stream in self.streams.values():
            stream.stop()

    def get_frames(self) -> dict:
        """Return dict of {cam_id: frame} for all cameras with a frame ready."""
        frames = {}
        for cam_id, stream in self.streams.items():
            frame = stream.get_frame()
            if frame is not None:
                frames[cam_id] = frame
        return frames
