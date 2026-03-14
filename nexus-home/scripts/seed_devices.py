#!/usr/bin/env python3
"""Seed sample device data for development."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, get_db


SAMPLE_DEVICES = [
    {
        "id": "light-01",
        "name": "Living Room Light",
        "type": "light",
        "room": "Living Room",
        "mqtt_topic": "cmnd/living_light/POWER",
        "protocol": "mqtt",
        "ip_address": "192.168.1.101",
    },
    {
        "id": "switch-01",
        "name": "Kitchen Switch",
        "type": "switch",
        "room": "Kitchen",
        "mqtt_topic": "cmnd/kitchen_switch/POWER",
        "protocol": "mqtt",
        "ip_address": "192.168.1.102",
    },
    {
        "id": "sensor-01",
        "name": "Bedroom Temp Sensor",
        "type": "sensor",
        "room": "Bedroom",
        "mqtt_topic": "tele/bedroom_sensor/SENSOR",
        "protocol": "mqtt",
        "ip_address": "192.168.1.103",
    },
    {
        "id": "plug-01",
        "name": "Office Smart Plug",
        "type": "plug",
        "room": "Office",
        "mqtt_topic": "cmnd/office_plug/POWER",
        "protocol": "mqtt",
        "ip_address": "192.168.1.104",
        "mac_address": "AA:BB:CC:DD:EE:01",
    },
]

SAMPLE_SCENES = [
    {
        "id": "scene-movie",
        "name": "Movie Night",
        "actions": '[{"type":"device_command","device_id":"light-01","command":{"on":true,"brightness":20}}]',
    },
    {
        "id": "scene-away",
        "name": "Away Mode",
        "actions": '[{"type":"device_command","device_id":"light-01","command":{"on":false}},{"type":"device_command","device_id":"switch-01","command":{"on":false}}]',
    },
]


async def seed():
    await init_db()
    async with get_db() as db:
        for dev in SAMPLE_DEVICES:
            await db.execute(
                """INSERT OR IGNORE INTO devices (id, name, type, room, mqtt_topic, protocol, ip_address, mac_address)
                VALUES (:id, :name, :type, :room, :mqtt_topic, :protocol, :ip_address, :mac_address)""",
                {**{"mac_address": None}, **dev},
            )
        for scene in SAMPLE_SCENES:
            await db.execute(
                "INSERT OR IGNORE INTO scenes (id, name, actions) VALUES (:id, :name, :actions)",
                scene,
            )
        await db.commit()
    print(f"Seeded {len(SAMPLE_DEVICES)} devices and {len(SAMPLE_SCENES)} scenes")


if __name__ == "__main__":
    asyncio.run(seed())
