"""Camera stream capture via OpenCV."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Generator

import numpy as np

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=8)


def _open_stream(source: str | int):
    """Open a video capture stream (blocking)."""
    try:
        import cv2
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error("Failed to open stream: %s", source)
            return None
        return cap
    except ImportError:
        logger.error("OpenCV not installed")
        return None


def _read_frame(cap) -> np.ndarray | None:
    """Read a single frame (blocking)."""
    ret, frame = cap.read()
    return frame if ret else None


def _encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    """Encode frame as JPEG (blocking)."""
    import cv2
    params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode(".jpg", frame, params)
    return buffer.tobytes()


class StreamCapture:
    """Manages a single camera stream."""

    def __init__(self, source: str | int) -> None:
        self.source = source
        self._cap = None
        self._running = False

    async def start(self) -> bool:
        """Open the stream."""
        loop = asyncio.get_event_loop()
        self._cap = await loop.run_in_executor(_executor, _open_stream, self.source)
        self._running = self._cap is not None
        return self._running

    async def read_frame(self) -> np.ndarray | None:
        """Read a frame asynchronously."""
        if not self._cap:
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _read_frame, self._cap)

    async def get_snapshot(self, quality: int = 85) -> bytes | None:
        """Get current frame as JPEG bytes."""
        frame = await self.read_frame()
        if frame is None:
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _encode_jpeg, frame, quality)

    async def mjpeg_generator(self, fps: int = 15):
        """Generate MJPEG frames for streaming."""
        delay = 1.0 / fps
        while self._running:
            jpeg = await self.get_snapshot()
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(delay)

    async def stop(self) -> None:
        """Release the stream."""
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None

    @property
    def is_running(self) -> bool:
        return self._running
