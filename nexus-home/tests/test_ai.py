"""Tests for the AI module — chat endpoint, command endpoint, and intent parsing."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.intent import IntentParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_devices():
    return [
        {"id": "light-1", "name": "Living Room Light", "type": "light",
         "room": "living_room", "mqtt_topic": "tasmota/light1", "protocol": "mqtt"},
        {"id": "thermostat-1", "name": "Main Thermostat", "type": "thermostat",
         "room": "hallway", "mqtt_topic": "tasmota/therm1", "protocol": "mqtt"},
    ]


@pytest.fixture
def app():
    """Create a fresh FastAPI app with the AI router mounted."""
    from fastapi import FastAPI
    from app.ai.router import router
    test_app = FastAPI()
    test_app.include_router(router, prefix="/ai")
    return test_app


@pytest.fixture
def api_key():
    return "test-api-key"


# ---------------------------------------------------------------------------
# Intent parser unit tests
# ---------------------------------------------------------------------------

class TestIntentParser:
    """Unit tests for IntentParser._parse_response and parse()."""

    def test_parse_valid_device_command(self):
        raw = json.dumps({
            "type": "device_command",
            "device_id": "light-1",
            "command": {"power": "on"},
            "response": "Turning on the living room light.",
        })
        result = IntentParser._parse_response(raw)
        assert result["type"] == "device_command"
        assert result["device_id"] == "light-1"
        assert result["command"] == {"power": "on"}

    def test_parse_valid_conversation(self):
        raw = json.dumps({
            "type": "conversation",
            "device_id": None,
            "command": None,
            "response": "The weather today is sunny.",
        })
        result = IntentParser._parse_response(raw)
        assert result["type"] == "conversation"
        assert result["device_id"] is None

    def test_parse_with_markdown_fences(self):
        raw = '```json\n{"type": "conversation", "response": "Hello!"}\n```'
        result = IntentParser._parse_response(raw)
        assert result["type"] == "conversation"
        assert result["response"] == "Hello!"

    def test_parse_invalid_json_falls_back(self):
        raw = "I don't understand that command."
        result = IntentParser._parse_response(raw)
        assert result["type"] == "conversation"
        assert result["response"] == raw

    def test_parse_missing_keys_falls_back(self):
        raw = json.dumps({"foo": "bar"})
        result = IntentParser._parse_response(raw)
        assert result["type"] == "conversation"

    @pytest.mark.asyncio
    async def test_parse_calls_ollama(self, sample_devices):
        parser = IntentParser()
        expected = {
            "type": "device_command",
            "device_id": "light-1",
            "command": {"power": "on"},
            "response": "Turning on the light.",
        }
        with patch("app.ai.intent.ollama_client") as mock_client:
            mock_client.chat = AsyncMock(return_value=json.dumps(expected))
            result = await parser.parse("turn on the living room light", sample_devices)

        assert result["type"] == "device_command"
        assert result["device_id"] == "light-1"
        mock_client.chat.assert_awaited_once()


# ---------------------------------------------------------------------------
# Router / endpoint tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    """Tests for POST /ai/chat."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, app, api_key):
        with (
            patch("app.ai.router.ollama_client") as mock_ollama,
            patch("app.ai.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=[api_key])
            )
            mock_devs.return_value = []
            mock_ollama.chat = AsyncMock(return_value="Hello! How can I help?")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/chat",
                    json={"message": "Hello"},
                    headers={"X-API-Key": api_key},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["response"] == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_chat_with_context_history(self, app, api_key):
        with (
            patch("app.ai.router.ollama_client") as mock_ollama,
            patch("app.ai.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=[api_key])
            )
            mock_devs.return_value = []
            mock_ollama.chat = AsyncMock(return_value="Sure thing.")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/chat",
                    json={
                        "message": "What about now?",
                        "context": {
                            "history": [
                                {"role": "user", "content": "Hi"},
                                {"role": "assistant", "content": "Hello!"},
                            ]
                        },
                    },
                    headers={"X-API-Key": api_key},
                )

            assert resp.status_code == 200
            # Verify history was included in the messages sent to ollama
            call_args = mock_ollama.chat.call_args
            messages = call_args[0][0]
            assert len(messages) == 3  # 2 history + 1 new


class TestCommandEndpoint:
    """Tests for POST /ai/command."""

    @pytest.mark.asyncio
    async def test_command_device_execution(self, app, api_key, sample_devices):
        intent_result = {
            "type": "device_command",
            "device_id": "light-1",
            "command": {"power": "on"},
            "response": "Turning on the living room light.",
        }
        with (
            patch("app.ai.router.intent_parser") as mock_parser,
            patch("app.ai.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.ai.router._execute_device_command", new_callable=AsyncMock) as mock_exec,
            patch("app.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=[api_key])
            )
            mock_devs.return_value = sample_devices
            mock_parser.parse = AsyncMock(return_value=intent_result)
            mock_exec.return_value = True

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/command",
                    json={"message": "turn on the living room light"},
                    headers={"X-API-Key": api_key},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["executed"] is True
            assert data["device_id"] == "light-1"
            assert data["command"] == {"power": "on"}

    @pytest.mark.asyncio
    async def test_command_no_devices(self, app, api_key):
        with (
            patch("app.ai.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=[api_key])
            )
            mock_devs.return_value = []

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/command",
                    json={"message": "turn on lights"},
                    headers={"X-API-Key": api_key},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["executed"] is False

    @pytest.mark.asyncio
    async def test_command_conversation_fallback(self, app, api_key, sample_devices):
        intent_result = {
            "type": "conversation",
            "device_id": None,
            "command": None,
            "response": "I can help you with that.",
        }
        with (
            patch("app.ai.router.intent_parser") as mock_parser,
            patch("app.ai.router._get_devices", new_callable=AsyncMock) as mock_devs,
            patch("app.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=[api_key])
            )
            mock_devs.return_value = sample_devices
            mock_parser.parse = AsyncMock(return_value=intent_result)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/command",
                    json={"message": "what's the weather?"},
                    headers={"X-API-Key": api_key},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["executed"] is False
            assert data["device_id"] is None


class TestAuthRequired:
    """Verify API key enforcement."""

    @pytest.mark.asyncio
    async def test_chat_rejects_missing_key(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/ai/chat", json={"message": "hi"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_command_rejects_bad_key(self, app):
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                server=MagicMock(api_keys=["real-key"])
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ai/command",
                    json={"message": "test"},
                    headers={"X-API-Key": "wrong-key"},
                )
        assert resp.status_code == 403
