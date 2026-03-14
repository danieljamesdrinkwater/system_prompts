"""Camera lifecycle manager — start/stop streams, run detection."""

import asyncio
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.database import get_db
from app.camera.capture import StreamCapture
from app.camera.detector import detector
from app.camera.recorder import Recorder

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages all camera streams, detection, and recording."""

    def __init__(self) -> None:
        self._streams: dict[str, StreamCapture] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._recorders: dict[str, Recorder] = {}

    def _get_source(self, camera: dict) -> str | int:
        """Get the capture source from camera config."""
        cam_type = camera["type"]
        if cam_type == "usb":
            path = camera.get("device_path", "/dev/video0")
            # Try to extract device index
            try:
                return int(path.split("video")[-1])
            except (ValueError, IndexError):
                return 0
        elif cam_type in ("rtsp", "onvif"):
            url = camera.get("url", "")
            username = camera.get("username", "")
            password = camera.get("password", "")
            if username and password and "://" in url:
                # Inject credentials into RTSP URL
                proto, rest = url.split("://", 1)
                url = f"{proto}://{username}:{password}@{rest}"
            return url
        return camera.get("url", "")

    async def start_camera(self, camera_id: str) -> bool:
        """Start streaming and detection for a camera."""
        if camera_id in self._streams:
            return True

        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM cameras WHERE id = ? AND enabled = 1", (camera_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            camera = dict(row)

        source = self._get_source(camera)
        stream = StreamCapture(source)
        if not await stream.start():
            return False

        self._streams[camera_id] = stream

        # Start detection loop
        task = asyncio.create_task(self._detection_loop(camera_id, stream))
        self._tasks[camera_id] = task

        logger.info("Camera started: %s", camera_id)
        return True

    async def _detection_loop(self, camera_id: str, stream: StreamCapture) -> None:
        """Run detection on frames at configured FPS."""
        settings = get_settings()
        fps = settings.cameras.detection.detection_fps
        delay = 1.0 / fps if fps > 0 else 1.0

        while stream.is_running:
            try:
                frame = await stream.read_frame()
                if frame is None:
                    await asyncio.sleep(1)
                    continue

                detections = await detector.detect(frame)
                for det in detections:
                    thumbnail = await detector.save_thumbnail(camera_id, frame)
                    await detector.save_event(
                        camera_id=camera_id,
                        label=det["label"],
                        confidence=det["confidence"],
                        bbox=det["bbox"],
                        thumbnail_path=thumbnail,
                    )

                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Detection loop error for %s: %s", camera_id, e)
                await asyncio.sleep(5)

    async def stop_camera(self, camera_id: str) -> None:
        """Stop a camera stream."""
        task = self._tasks.pop(camera_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        stream = self._streams.pop(camera_id, None)
        if stream:
            await stream.stop()

        recorder = self._recorders.pop(camera_id, None)
        if recorder:
            await recorder.stop_recording()

        logger.info("Camera stopped: %s", camera_id)

    async def stop_all(self) -> None:
        """Stop all camera streams."""
        ids = list(self._streams.keys())
        for cam_id in ids:
            await self.stop_camera(cam_id)

    def get_stream(self, camera_id: str) -> StreamCapture | None:
        """Get a camera stream."""
        return self._streams.get(camera_id)

    def list_active(self) -> list[str]:
        """List active camera IDs."""
        return list(self._streams.keys())


camera_manager = CameraManager()
