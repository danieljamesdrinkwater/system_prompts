"""Text-to-speech engine using piper-tts."""

import asyncio
import io
import logging
import struct
import wave

from app.config import get_settings

logger = logging.getLogger(__name__)


class TTSEngine:
    """Lazy-loading text-to-speech engine backed by piper-tts."""

    def __init__(self) -> None:
        self._voice = None
        self._available = True

    def _load_model(self) -> None:
        """Load the piper voice model on first use."""
        if self._voice is not None:
            return
        settings = get_settings()
        try:
            from piper import PiperVoice

            self._voice = PiperVoice.load(settings.voice.tts_model_path)
            logger.info("Loaded TTS model from %s", settings.voice.tts_model_path)
        except Exception as exc:
            logger.warning("Piper TTS not available: %s", exc)
            self._available = False

    def _synthesize_sync(self, text: str) -> bytes:
        """Run TTS synthesis synchronously (called in a thread pool)."""
        self._load_model()

        if not self._available or self._voice is None:
            return self._generate_silence_wav()

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize(text, wav_file)
        return buf.getvalue()

    @staticmethod
    def _generate_silence_wav() -> bytes:
        """Generate a short silent WAV as a fallback when TTS is unavailable."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            # 0.5 seconds of silence
            silence = struct.pack("<" + "h" * 11025, *([0] * 11025))
            wav_file.writeframes(silence)
        return buf.getvalue()

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio bytes.

        Falls back to a silent WAV if piper-tts is not available.
        Runs the CPU-bound synthesis in a thread pool executor.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)


tts_engine = TTSEngine()
