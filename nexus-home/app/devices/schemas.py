"""Pydantic schemas for device API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    name: str
    type: str
    room: str | None = None
    mqtt_topic: str | None = None
    protocol: str = "mqtt"
    mac_address: str | None = None
    ip_address: str | None = None
    metadata: dict = Field(default_factory=dict)


class DeviceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    room: str | None = None
    mqtt_topic: str | None = None
    protocol: str | None = None
    mac_address: str | None = None
    ip_address: str | None = None
    metadata: dict | None = None


class DeviceCommand(BaseModel):
    command: dict


class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    room: str | None = None
    mqtt_topic: str | None = None
    protocol: str = "mqtt"
    mac_address: str | None = None
    ip_address: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    state: dict | None = None


class DiscoveredDevice(BaseModel):
    name: str
    ip: str
    mac: str | None = None
    type: str
    service_info: dict = Field(default_factory=dict)
