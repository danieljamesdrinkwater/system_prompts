"""YOLOv8 object detector — runs on Hailo-8 accelerator or CPU fallback."""

import logging

import cv2
import numpy as np
from ultralytics import YOLO

from config import Config

log = logging.getLogger("detector")


class Detection:
    """A single detected object."""

    __slots__ = ("class_name", "confidence", "bbox", "distance_estimate")

    def __init__(self, class_name: str, confidence: float, bbox: tuple):
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox  # (x1, y1, x2, y2) in pixels
        self.distance_estimate = None  # Set by proximity estimator

    @property
    def centre(self) -> tuple:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def area(self) -> float:
        return self.height * self.width

    def estimate_distance(self, frame_height: int):
        """Rough distance estimate from bounding box size.

        Based on the assumption that a person is ~1.7m tall.
        Larger bounding box = closer object. This is crude but
        functional as a Phase 1 fallback when radar is unavailable.
        """
        if self.class_name in ("person", "bicycle", "motorcycle"):
            # Proportion of frame height occupied by detection
            ratio = self.height / frame_height
            if ratio > 0:
                # Empirical: at 2m a person fills ~60% of a 1080p side cam
                # at 6m they fill ~20%. Linear approximation.
                self.distance_estimate = max(0.5, min(10.0, 1.2 / ratio))

    def __repr__(self):
        dist = f" ~{self.distance_estimate:.1f}m" if self.distance_estimate else ""
        return f"<{self.class_name} {self.confidence:.0%}{dist}>"


class Detector:
    """YOLOv8 object detection wrapper."""

    def __init__(self, config: Config):
        self.config = config
        self.target_classes = set(config.target_classes)
        self.conf_threshold = config.confidence_threshold

        log.info("Loading model: %s", config.model_path)
        self.model = YOLO(config.model_path)

        # Map COCO class IDs to names we care about
        self._class_names = self.model.names
        log.info("Model loaded — %d classes available", len(self._class_names))

    def detect(self, frame: np.ndarray) -> list:
        """Run detection on a single frame. Returns list of Detection objects."""
        results = self.model(
            frame,
            conf=self.conf_threshold,
            verbose=False,
        )

        detections = []
        for r in results:
            for box in r.boxes:
                class_id = int(box.cls[0])
                class_name = self._class_names.get(class_id, "unknown")

                if class_name not in self.target_classes:
                    continue

                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                det = Detection(class_name, confidence, (x1, y1, x2, y2))
                det.estimate_distance(frame.shape[0])
                detections.append(det)

        return detections
