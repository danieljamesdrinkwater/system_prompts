"""AI module API routes — chat and natural-language command execution."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_api_key
from app.database import get_db
from app.ai.schemas import ChatRequest, ChatResponse, CommandRequest, CommandResponse
from app.ai.ollama_client import ollama_client
from app.ai.intent import intent_parser

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_devices() -> list[dict]:
    """Fetch all devices from the database as plain dicts."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, type, room, mqtt_topic, protocol FROM devices"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def _get_latest_state(device_id: str) -> dict | None:
    """Fetch the most recent state for a device."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT state FROM device_states WHERE device_id = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (device_id,),
        )
        row = await cursor.fetchone()
        if row:
            try:
                return json.loads(row["state"])
            except (json.JSONDecodeError, TypeError):
                return None
    return None


async def _execute_device_command(device_id: str, command: dict) -> bool:
    """Publish a command to the device via MQTT."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT mqtt_topic, protocol FROM devices WHERE id = ?",
            (device_id,),
        )
        device = await cursor.fetchone()

    if device is None:
        return False

    mqtt_topic = device["mqtt_topic"]
    if not mqtt_topic:
        logger.warning("Device %s has no MQTT topic configured", device_id)
        return False

    try:
        from app.devices.mqtt_client import mqtt_manager

        # For Tasmota devices, send to cmnd/<topic>/...
        cmd_topic = f"cmnd/{mqtt_topic}/Backlog"
        await mqtt_manager.publish_command(cmd_topic, command)
        return True
    except Exception as exc:
        logger.error("Failed to execute command for device %s: %s", device_id, exc)
        return False


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, _key: str = Depends(verify_api_key)):
    """General chat with home-aware context."""
    devices = await _get_devices()
    device_summary = json.dumps(devices, indent=2, default=str)

    system_prompt = (
        "You are Nexus, a helpful smart home assistant. "
        "Here are the devices in the home:\n"
        f"{device_summary}\n\n"
        "Answer the user's questions helpfully. If they ask about devices, "
        "reference them by name."
    )

    context_parts: list[dict] = []
    if request.context and "history" in request.context:
        context_parts = request.context["history"]

    messages = context_parts + [{"role": "user", "content": request.message}]
    response_text = await ollama_client.chat(messages, system_prompt=system_prompt)

    return ChatResponse(response=response_text)


@router.post("/command", response_model=CommandResponse)
async def command(request: CommandRequest, _key: str = Depends(verify_api_key)):
    """Parse a natural-language command, execute it, and return the result."""
    devices = await _get_devices()
    if not devices:
        return CommandResponse(
            response="No devices are registered in the system.",
            executed=False,
        )

    intent = await intent_parser.parse(request.message, devices)
    if intent is None:
        raise HTTPException(status_code=500, detail="Intent parsing failed")

    if intent["type"] == "device_command" and intent.get("device_id"):
        executed = await _execute_device_command(
            intent["device_id"], intent.get("command", {})
        )
        return CommandResponse(
            response=intent.get("response", "Command sent."),
            executed=executed,
            device_id=intent["device_id"],
            command=intent.get("command"),
        )

    return CommandResponse(
        response=intent.get("response", "I'm not sure how to help with that."),
        executed=False,
    )
