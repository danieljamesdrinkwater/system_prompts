"""Tests for the Voice module — transcribe, speak, and voice command endpoints."""

import io
import wave
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate minimal valid WAV audio bytes for testing."""
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        silence = struct.pack("<" + "h" * num_samples, *([0] * num_samples))
        wf.writeframes(silence)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a fresh FastAPI app with the voice router mounted."""
    from fastapi import FastAPI
    from app.voice.router import router
    test_app = FastAPI()
    test_app.include_router(router, prefix="/voice")
    return test_app


@pytest.fixture
def api_key():
    return "test-api-key"


@pytest.fixture
def mock_auth(api_key):
    """Patch auth to accept the test API key."""
    with patch("app.auth.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            server=MagicMock(api_keys=[api_key])
        )
        yield


@pytest.fixture
def sample_wav():
    return _make_wav_bytes()


# ---------------------------------------------------------------------------
# Transcribe endpoint tests
# ---------------------------------------------------------------------------

class TestTranscribeEndpoint:
    """Tests for POST /voice/transcribe."""

    @pytest.mark.asyncio
    async def test_transcribe_success(self, app, api_key, sample_wav, mock_auth):
        transcription_result = {
            "text": "turn on the lights",
            "language": "en",
            "duration": 1.5,
        }
        with patch("app.voice.router.stt_engine") as mock_stt:
            mock_stt.transcribe = AsyncMock(return_value=transcription_result)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/transcribe",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "turn on the lights"
        assert data["language"] == "en"
        assert data["duration"] == 1.5

    @pytest.mark.asyncio
    async def test_transcribe_with_language_param(self, app, api_key, sample_wav, mock_auth):
        with patch("app.voice.router.stt_engine") as mock_stt:
            mock_stt.transcribe = AsyncMock(
                return_value={"text": "hola", "language": "es", "duration": 0.8}
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/transcribe",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    params={"language": "es"},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        assert resp.json()["language"] == "es"

    @pytest.mark.asyncio
    async def test_transcribe_empty_file(self, app, api_key, mock_auth):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/voice/transcribe",
                files={"file": ("audio.wav", b"", "audio/wav")},
                headers={"X-API-Key": api_key},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_transcribe_engine_failure(self, app, api_key, sample_wav, mock_auth):
        with patch("app.voice.router.stt_engine") as mock_stt:
            mock_stt.transcribe = AsyncMock(side_effect=RuntimeError("Model not loaded"))

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/transcribe",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Speak endpoint tests
# ---------------------------------------------------------------------------

class TestSpeakEndpoint:
    """Tests for POST /voice/speak."""

    @pytest.mark.asyncio
    async def test_speak_returns_wav(self, app, api_key, sample_wav, mock_auth):
        with patch("app.voice.router.tts_engine") as mock_tts:
            mock_tts.synthesize = AsyncMock(return_value=sample_wav)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/speak",
                    json={"text": "Hello world"},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_speak_empty_text_rejected(self, app, api_key, mock_auth):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/voice/speak",
                json={"text": "   "},
                headers={"X-API-Key": api_key},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_speak_engine_failure(self, app, api_key, mock_auth):
        with patch("app.voice.router.tts_engine") as mock_tts:
            mock_tts.synthesize = AsyncMock(side_effect=RuntimeError("TTS crashed"))

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/speak",
                    json={"text": "Hello"},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Voice command (full pipeline) endpoint tests
# ---------------------------------------------------------------------------

class TestVoiceCommandEndpoint:
    """Tests for POST /voice/command."""

    @pytest.mark.asyncio
    async def test_full_pipeline_device_command(self, app, api_key, sample_wav, mock_auth):
        transcription = {"text": "turn on the light", "language": "en", "duration": 1.2}
        intent_result = {
            "type": "device_command",
            "device_id": "light-1",
            "command": {"power": "on"},
            "response": "Turning on the light.",
        }
        with (
            patch("app.voice.router.stt_engine") as mock_stt,
            patch("app.voice.router.intent_parser") as mock_parser,
            patch("app.voice.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.voice.router._execute_device_command", new_callable=AsyncMock) as mock_exec,
        ):
            mock_stt.transcribe = AsyncMock(return_value=transcription)
            mock_parser.parse = AsyncMock(return_value=intent_result)
            mock_devs.return_value = [{"id": "light-1", "name": "Light", "type": "light"}]
            mock_exec.return_value = True

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/command",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["transcription"] == "turn on the light"
        assert data["ai_response"] == "Turning on the light."
        assert data["executed"] is True

    @pytest.mark.asyncio
    async def test_full_pipeline_conversation(self, app, api_key, sample_wav, mock_auth):
        transcription = {"text": "what time is it", "language": "en", "duration": 0.9}
        intent_result = {
            "type": "conversation",
            "device_id": None,
            "command": None,
            "response": "It is 3 PM.",
        }
        with (
            patch("app.voice.router.stt_engine") as mock_stt,
            patch("app.voice.router.intent_parser") as mock_parser,
            patch("app.voice.router._get_devices", new_callable=AsyncMock) as mock_devs,
        ):
            mock_stt.transcribe = AsyncMock(return_value=transcription)
            mock_parser.parse = AsyncMock(return_value=intent_result)
            mock_devs.return_value = []

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/command",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is False
        assert data["ai_response"] == "It is 3 PM."

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_transcription(self, app, api_key, sample_wav, mock_auth):
        transcription = {"text": "  ", "language": "en", "duration": 0.1}
        with patch("app.voice.router.stt_engine") as mock_stt:
            mock_stt.transcribe = AsyncMock(return_value=transcription)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/voice/command",
                    files={"file": ("audio.wav", sample_wav, "audio/wav")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is False
        assert "didn't catch" in data["ai_response"].lower()


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

class TestVoiceAuth:
    """Verify API key is required on all voice endpoints."""

    @pytest.mark.asyncio
    async def test_transcribe_requires_auth(self, app, sample_wav):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/voice/transcribe",
                files={"file": ("audio.wav", sample_wav, "audio/wav")},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_speak_requires_auth(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/voice/speak",
                json={"text": "hello"},
            )
        assert resp.status_code == 401
