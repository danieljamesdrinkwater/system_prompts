"""Device CRUD operations and command dispatch."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.devices.schemas import DeviceCreate, DeviceUpdate
from app.devices.mqtt_client import mqtt_manager


async def list_devices(
    db: aiosqlite.Connection,
    room: str | None = None,
    type: str | None = None,
) -> list[dict]:
    """List devices with optional room/type filters."""
    query = "SELECT * FROM devices WHERE 1=1"
    params: list[str] = []

    if room:
        query += " AND room = ?"
        params.append(room)
    if type:
        query += " AND type = ?"
        params.append(type)

    query += " ORDER BY name"
    rows = await db.execute_fetchall(query, params)
    return [_row_to_dict(row) for row in rows]


async def get_device(db: aiosqlite.Connection, device_id: str) -> dict | None:
    """Get a single device by ID, including its latest state."""
    row = await db.execute_fetchall(
        "SELECT * FROM devices WHERE id = ?", (device_id,)
    )
    if not row:
        return None

    device = _row_to_dict(row[0])

    state_row = await db.execute_fetchall(
        "SELECT state, updated_at FROM device_states "
        "WHERE device_id = ? ORDER BY updated_at DESC LIMIT 1",
        (device_id,),
    )
    if state_row:
        device["state"] = json.loads(state_row[0][0])
    else:
        device["state"] = None

    return device


async def create_device(db: aiosqlite.Connection, device: DeviceCreate) -> dict:
    """Create a new device and return it."""
    device_id = str(uuid.uuid4())
    metadata_json = json.dumps(device.metadata)

    await db.execute(
        "INSERT INTO devices (id, name, type, room, mqtt_topic, protocol, "
        "mac_address, ip_address, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            device_id,
            device.name,
            device.type,
            device.room,
            device.mqtt_topic,
            device.protocol,
            device.mac_address,
            device.ip_address,
            metadata_json,
        ),
    )
    await db.commit()

    return await get_device(db, device_id)


async def update_device(
    db: aiosqlite.Connection, device_id: str, updates: DeviceUpdate
) -> dict | None:
    """Update device fields. Returns updated device or None if not found."""
    existing = await get_device(db, device_id)
    if not existing:
        return None

    fields = updates.model_dump(exclude_unset=True)
    if not fields:
        return existing

    set_clauses = []
    params = []
    for key, value in fields.items():
        set_clauses.append(f"{key} = ?")
        params.append(json.dumps(value) if key == "metadata" else value)

    params.append(device_id)
    await db.execute(
        f"UPDATE devices SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    await db.commit()

    return await get_device(db, device_id)


async def delete_device(db: aiosqlite.Connection, device_id: str) -> bool:
    """Delete a device. Returns True if deleted, False if not found."""
    cursor = await db.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    await db.commit()
    return cursor.rowcount > 0


async def send_command(device_id: str, command: dict) -> dict:
    """Look up device MQTT topic and publish the command."""
    from app.database import get_db

    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT mqtt_topic, protocol FROM devices WHERE id = ?", (device_id,)
        )
        if not row:
            raise ValueError(f"Device {device_id} not found")

        mqtt_topic = row[0][0]
        protocol = row[0][1]

        if not mqtt_topic:
            raise ValueError(f"Device {device_id} has no MQTT topic configured")

        # Build the command topic based on protocol
        if protocol == "tasmota":
            cmd_topic = f"cmnd/{mqtt_topic.split('/')[-1]}/POWER"
        elif protocol == "esphome":
            cmd_topic = f"{mqtt_topic}/command"
        else:
            cmd_topic = f"{mqtt_topic}/set"

        await mqtt_manager.publish_command(cmd_topic, command)

    return {"status": "sent", "topic": cmd_topic, "command": command}


async def get_device_state(db: aiosqlite.Connection, device_id: str) -> dict | None:
    """Get the latest state for a device."""
    row = await db.execute_fetchall(
        "SELECT state, updated_at FROM device_states "
        "WHERE device_id = ? ORDER BY updated_at DESC LIMIT 1",
        (device_id,),
    )
    if not row:
        return None
    return {"state": json.loads(row[0][0]), "updated_at": row[0][1]}


async def get_device_history(
    db: aiosqlite.Connection, device_id: str, hours: int = 24
) -> list[dict]:
    """Get state history for a device within the given time window."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = await db.execute_fetchall(
        "SELECT state, updated_at FROM device_states "
        "WHERE device_id = ? AND updated_at >= ? ORDER BY updated_at DESC",
        (device_id, since),
    )
    return [
        {"state": json.loads(r[0]), "updated_at": r[1]}
        for r in rows
    ]


async def log_audit(
    db: aiosqlite.Connection,
    action: str,
    entity_type: str,
    entity_id: str,
    details: str | None = None,
    user_key: str | None = None,
) -> None:
    """Write an entry to the audit log."""
    await db.execute(
        "INSERT INTO audit_log (user_key, action, entity_type, entity_id, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_key, action, entity_type, entity_id, details),
    )
    await db.commit()


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to a dictionary, parsing JSON fields."""
    d = dict(row)
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except json.JSONDecodeError:
            d["metadata"] = {}
    return d
