"""Shared test fixtures."""

import os
import pytest
import pytest_asyncio
import aiosqlite
from unittest.mock import AsyncMock, MagicMock, patch

# Use in-memory DB for tests
os.environ["NEXUS_DATA_DIR"] = "/tmp/nexus-test"
os.environ["NEXUS_CONFIG_PATH"] = "/dev/null"


@pytest.fixture(autouse=True)
def reset_settings():
    """Clear cached settings between tests."""
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    from app.database import SCHEMA
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        db.row_factory = aiosqlite.Row
        yield db


@pytest.fixture
def mock_mqtt():
    """Mock MQTT client."""
    with patch("app.devices.mqtt_client.mqtt_manager") as mock:
        mock.publish = AsyncMock()
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        yield mock


@pytest.fixture
def mock_ollama():
    """Mock Ollama client."""
    with patch("app.ai.ollama_client.ollama_client") as mock:
        mock.chat = AsyncMock(return_value="I'll turn on the light for you.")
        mock.generate = AsyncMock(return_value="Test response")
        yield mock
