"""Tests for the devices module."""

import json
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Set test config before importing app modules
os.environ["NEXUS_DATA_DIR"] = "/tmp/nexus_test_data"
os.environ["NEXUS_CONFIG_PATH"] = "/dev/null"

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.database import init_db, DB_PATH
from app.config import get_settings


# Patch MQTT manager before importing the app
with patch("app.devices.mqtt_client.MQTTManager.start", new_callable=AsyncMock):
    with patch("app.devices.mqtt_client.MQTTManager.stop", new_callable=AsyncMock):
        pass


API_KEY = "change-me-to-a-real-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Initialize a fresh test database for each test."""
    db_path = tmp_path / "nexus_test.db"
    monkeypatch.setattr("app.database.DB_PATH", db_path)
    await init_db()
    yield
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client():
    """Create a test client with mocked MQTT and scheduler."""
    with patch("app.devices.mqtt_client.MQTTManager.start", new_callable=AsyncMock):
        with patch("app.devices.mqtt_client.MQTTManager.stop", new_callable=AsyncMock):
            with patch("app.automation.scheduler.scheduler_manager.start", new_callable=AsyncMock):
                with patch("app.automation.scheduler.scheduler_manager.stop", new_callable=AsyncMock):
                    with patch("app.camera.manager.camera_manager.stop_all", new_callable=AsyncMock):
                        from app.main import app
                        with TestClient(app) as c:
                            yield c


def test_create_device(client):
    """Test creating a new device."""
    payload = {
        "name": "Living Room Light",
        "type": "light",
        "room": "living_room",
        "mqtt_topic": "tele/light1",
        "protocol": "tasmota",
    }
    response = client.post("/api/devices/", json=payload, headers=HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Living Room Light"
    assert data["type"] == "light"
    assert data["room"] == "living_room"
    assert "id" in data


def test_list_devices(client):
    """Test listing devices with filters."""
    # Create two devices
    client.post("/api/devices/", json={
        "name": "Light 1", "type": "light", "room": "bedroom",
    }, headers=HEADERS)
    client.post("/api/devices/", json={
        "name": "Sensor 1", "type": "sensor", "room": "kitchen",
    }, headers=HEADERS)

    # List all
    response = client.get("/api/devices/", headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()["devices"]) == 2

    # Filter by room
    response = client.get("/api/devices/?room=bedroom", headers=HEADERS)
    assert len(response.json()["devices"]) == 1
    assert response.json()["devices"][0]["name"] == "Light 1"

    # Filter by type
    response = client.get("/api/devices/?type=sensor", headers=HEADERS)
    assert len(response.json()["devices"]) == 1


def test_get_device(client):
    """Test getting a single device."""
    create_resp = client.post("/api/devices/", json={
        "name": "Test Device", "type": "switch",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Test Device"


def test_get_device_not_found(client):
    """Test 404 for missing device."""
    response = client.get("/api/devices/nonexistent-id", headers=HEADERS)
    assert response.status_code == 404


def test_update_device(client):
    """Test updating a device."""
    create_resp = client.post("/api/devices/", json={
        "name": "Old Name", "type": "light",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.put(
        f"/api/devices/{device_id}",
        json={"name": "New Name", "room": "garage"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["room"] == "garage"


def test_delete_device(client):
    """Test deleting a device."""
    create_resp = client.post("/api/devices/", json={
        "name": "Temp Device", "type": "switch",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.delete(f"/api/devices/{device_id}", headers=HEADERS)
    assert response.status_code == 200

    # Confirm deleted
    response = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert response.status_code == 404


def test_send_command_no_topic(client):
    """Test sending a command to a device without an MQTT topic."""
    create_resp = client.post("/api/devices/", json={
        "name": "No Topic", "type": "light",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.post(
        f"/api/devices/{device_id}/command",
        json={"command": {"power": "on"}},
        headers=HEADERS,
    )
    assert response.status_code == 404


@patch("app.devices.mqtt_client.mqtt_manager.publish_command", new_callable=AsyncMock)
def test_send_command(mock_publish, client):
    """Test sending a command publishes to MQTT."""
    create_resp = client.post("/api/devices/", json={
        "name": "Smart Plug",
        "type": "switch",
        "mqtt_topic": "cmnd/plug1",
        "protocol": "mqtt",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.post(
        f"/api/devices/{device_id}/command",
        json={"command": {"power": "on"}},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    mock_publish.assert_called_once()


def test_device_history_empty(client):
    """Test device history returns empty for new device."""
    create_resp = client.post("/api/devices/", json={
        "name": "History Test", "type": "sensor",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.get(f"/api/devices/{device_id}/history", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["history"] == []


def test_auth_required(client):
    """Test that endpoints require API key."""
    response = client.get("/api/devices/")
    assert response.status_code in (401, 403)


@patch("app.devices.discovery.discover_mdns", new_callable=AsyncMock)
@patch("app.devices.discovery.discover_network", new_callable=AsyncMock)
def test_discover_devices(mock_network, mock_mdns, client):
    """Test discovery endpoint returns expected format."""
    mock_mdns.return_value = []
    mock_network.return_value = []

    response = client.get("/api/devices/discover/", headers=HEADERS)
    assert response.status_code == 200
    assert "discovered" in response.json()
    assert isinstance(response.json()["discovered"], list)


def test_wake_no_mac(client):
    """Test WoL fails when device has no MAC address."""
    create_resp = client.post("/api/devices/", json={
        "name": "No MAC", "type": "computer",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.post(f"/api/devices/{device_id}/wake", headers=HEADERS)
    assert response.status_code == 400


@patch("app.devices.wol.send_magic_packet")
def test_wake_device(mock_wol, client):
    """Test WoL sends magic packet when MAC is configured."""
    create_resp = client.post("/api/devices/", json={
        "name": "Desktop",
        "type": "computer",
        "mac_address": "AA:BB:CC:DD:EE:FF",
    }, headers=HEADERS)
    device_id = create_resp.json()["id"]

    response = client.post(f"/api/devices/{device_id}/wake", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    mock_wol.assert_called_once()
