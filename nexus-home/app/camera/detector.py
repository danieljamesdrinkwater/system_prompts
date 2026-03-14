"""YOLOv8 object/person detection pipeline."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.database import get_db
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


class Detector:
    """YOLOv8 detection engine."""

    def __init__(self) -> None:
        self._model = None
        self._loaded = False

    def _load_model(self) -> None:
        """Load YOLO model (blocking, called once)."""
        if self._loaded:
            return
        try:
            from ultralytics import YOLO
            settings = get_settings()
            model_path = settings.cameras.detection.model
            self._model = YOLO(model_path)
            self._loaded = True
            logger.info("YOLO model loaded: %s", model_path)
        except ImportError:
            logger.warning("ultralytics not installed, detection disabled")
        except Exception as e:
            logger.error("Failed to load YOLO model: %s", e)

    def _detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection on a frame (blocking)."""
        if not self._loaded:
            self._load_model()
        if not self._model:
            return []

        settings = get_settings()
        conf = settings.cameras.detection.confidence_threshold
        allowed_classes = settings.cameras.detection.classes

        results = self._model(frame, conf=conf, verbose=False)
        detections = []

        for r in results:
            for box in r.boxes:
                label = r.names[int(box.cls[0])]
                if label not in allowed_classes:
                    continue
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()
                detections.append({
                    "label": label,
                    "confidence": round(confidence, 3),
                    "bbox": [round(v, 1) for v in bbox],
                })

        return detections

    async def detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._detect, frame)

    async def save_event(
        self,
        camera_id: str,
        label: str,
        confidence: float,
        bbox: list[float],
        thumbnail_path: str | None = None,
    ) -> None:
        """Save a detection event to the database and broadcast."""
        import json
        async with get_db() as db:
            await db.execute(
                """INSERT INTO camera_events (camera_id, event_type, label, confidence, bbox, thumbnail_path)
                VALUES (?, 'detection', ?, ?, ?, ?)""",
                (camera_id, label, confidence, json.dumps(bbox), thumbnail_path),
            )
            await db.commit()

        await ws_manager.broadcast({
            "type": "camera_event",
            "camera_id": camera_id,
            "event_type": "detection",
            "label": label,
            "confidence": confidence,
        })

    async def save_thumbnail(self, camera_id: str, frame: np.ndarray) -> str | None:
        """Save a detection thumbnail."""
        try:
            import cv2
            settings = get_settings()
            snap_dir = Path(settings.cameras.snapshot_path)
            snap_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{camera_id}_{int(time.time())}.jpg"
            path = snap_dir / filename

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _executor,
                lambda: cv2.imwrite(str(path), frame),
            )
            return str(path)
        except Exception as e:
            logger.error("Failed to save thumbnail: %s", e)
            return None


detector = Detector()
