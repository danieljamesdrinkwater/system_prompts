"""MQTT client manager using gmqtt for Tasmota and ESPHome device communication."""

import json
import logging
from typing import Any

from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311

from app.config import get_settings
from app.database import get_db
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Tasmota topics
TASMOTA_TOPICS = [
    "tele/+/STATE",
    "tele/+/SENSOR",
    "stat/+/RESULT",
]

# ESPHome topics
ESPHOME_TOPICS = [
    "+/state",
    "+/sensor/+/state",
]


class MQTTManager:
    """Manages MQTT connection lifecycle and message routing."""

    def __init__(self) -> None:
        self._client: MQTTClient | None = None
        self._connected = False

    async def start(self) -> None:
        settings = get_settings()
        self._client = MQTTClient(client_id="nexus-home")

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        if settings.mqtt.username:
            self._client.set_auth_credentials(
                settings.mqtt.username, settings.mqtt.password
            )

        await self._client.connect(
            settings.mqtt.host,
            settings.mqtt.port,
            version=MQTTv311,
        )
        logger.info(
            "MQTT connected to %s:%d", settings.mqtt.host, settings.mqtt.port
        )

    async def stop(self) -> None:
        if self._client and self._connected:
            await self._client.disconnect()
            logger.info("MQTT client disconnected")

    def _on_connect(self, client: MQTTClient, flags: int, rc: int, properties: Any) -> None:
        self._connected = True
        logger.info("MQTT connected (rc=%d)", rc)

        for topic in TASMOTA_TOPICS + ESPHOME_TOPICS:
            client.subscribe(topic, qos=1)
            logger.debug("Subscribed to %s", topic)

    def _on_disconnect(self, client: MQTTClient, packet: Any, exc: BaseException | None = None) -> None:
        self._connected = False
        logger.warning("MQTT disconnected")

    async def _on_message(
        self, client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any
    ) -> None:
        try:
            data = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug("Non-JSON payload on %s: %s", topic, payload[:100])
            return

        logger.debug("MQTT message on %s: %s", topic, data)

        device_name = self._extract_device_name(topic)
        if not device_name:
            return

        await self._update_device_state(device_name, topic, data)

    def _extract_device_name(self, topic: str) -> str | None:
        """Extract the device identifier from a topic string."""
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] in ("tele", "stat"):
            # Tasmota: tele/<device>/STATE or stat/<device>/RESULT
            return parts[1]
        if len(parts) >= 2:
            # ESPHome: <device>/state or <device>/sensor/<name>/state
            return parts[0]
        return None

    async def _update_device_state(self, device_name: str, topic: str, data: dict) -> None:
        """Persist state update and broadcast via WebSocket."""
        async with get_db() as db:
            row = await db.execute_fetchall(
                "SELECT id FROM devices WHERE mqtt_topic = ? OR name = ? LIMIT 1",
                (topic.rsplit("/", 1)[0], device_name),
            )
            if not row:
                logger.debug("No device found for topic %s / name %s", topic, device_name)
                return

            device_id = row[0][0]
            state_json = json.dumps(data)

            await db.execute(
                "INSERT INTO device_states (device_id, state) VALUES (?, ?)",
                (device_id, state_json),
            )
            await db.commit()

        await ws_manager.broadcast({
            "type": "device_state",
            "device_id": device_id,
            "topic": topic,
            "state": data,
        })

    async def publish_command(self, topic: str, payload: dict | str) -> None:
        """Publish a command to an MQTT topic."""
        if not self._client or not self._connected:
            raise RuntimeError("MQTT client is not connected")

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        self._client.publish(topic, payload.encode(), qos=1)
        logger.info("Published to %s: %s", topic, payload)


mqtt_manager = MQTTManager()
