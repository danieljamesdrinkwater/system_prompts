"""Speech-to-text engine using faster-whisper."""

import asyncio
import logging
import tempfile
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class STTEngine:
    """Lazy-loading speech-to-text engine backed by faster-whisper."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        """Load the whisper model on first use."""
        if self._model is not None:
            return
        settings = get_settings()
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                settings.voice.stt_model,
                device=settings.voice.stt_device,
            )
            logger.info(
                "Loaded STT model '%s' on device '%s'",
                settings.voice.stt_model,
                settings.voice.stt_device,
            )
        except Exception as exc:
            logger.error("Failed to load STT model: %s", exc)
            raise

    def _transcribe_sync(self, audio_bytes: bytes, language: str | None) -> dict:
        """Run transcription synchronously (called in a thread pool)."""
        self._load_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp_path = tmp.name

            segments, info = self._model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
            )
            text = " ".join(segment.text.strip() for segment in segments)

        return {
            "text": text,
            "language": info.language,
            "duration": round(info.duration, 2),
        }

    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> dict:
        """Transcribe audio bytes to text.

        Returns dict with keys: text, language, duration.
        Runs the CPU-bound transcription in a thread pool executor.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._transcribe_sync, audio_bytes, language
        )


stt_engine = STTEngine()
