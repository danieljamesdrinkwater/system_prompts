"""Video recording — continuous and event-triggered."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


class Recorder:
    """Record video segments from a camera stream."""

    def __init__(self, camera_id: str, source) -> None:
        self.camera_id = camera_id
        self.source = source
        self._recording = False
        self._writer = None
        self._current_path: str | None = None
        self._start_time: datetime | None = None

    def _init_writer(self, frame) -> str:
        """Initialize video writer (blocking)."""
        import cv2
        settings = get_settings()
        rec_dir = Path(settings.cameras.recording_path) / self.camera_id
        rec_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = rec_dir / f"{timestamp}.mp4"

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(path), fourcc, 15.0, (w, h))
        self._current_path = str(path)
        self._start_time = datetime.now()
        return str(path)

    def _write_frame(self, frame) -> None:
        """Write a frame to video (blocking)."""
        if self._writer:
            self._writer.write(frame)

    def _release(self) -> None:
        """Release the writer (blocking)."""
        if self._writer:
            self._writer.release()
            self._writer = None

    async def start_recording(self, frame) -> str:
        """Start recording with first frame."""
        self._recording = True
        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(_executor, self._init_writer, frame)
        logger.info("Recording started: %s", path)
        return path

    async def write_frame(self, frame) -> None:
        """Write a frame to the recording."""
        if not self._recording:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._write_frame, frame)

    async def stop_recording(self, trigger: str = "continuous") -> None:
        """Stop recording and log to database."""
        if not self._recording:
            return
        self._recording = False
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._release)

        if self._current_path and self._start_time:
            file_size = Path(self._current_path).stat().st_size if Path(self._current_path).exists() else 0
            async with get_db() as db:
                await db.execute(
                    """INSERT INTO recordings (camera_id, file_path, start_time, end_time, size_bytes, trigger)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (self.camera_id, self._current_path, self._start_time.isoformat(),
                     datetime.now().isoformat(), file_size, trigger),
                )
                await db.commit()
            logger.info("Recording saved: %s (%d bytes)", self._current_path, file_size)

        self._current_path = None
        self._start_time = None

    @property
    def is_recording(self) -> bool:
        return self._recording
