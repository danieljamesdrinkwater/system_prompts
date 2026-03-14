"""Shared Pydantic models used across modules."""

from datetime import datetime
from pydantic import BaseModel


class Device(BaseModel):
    id: str
    name: str
    type: str
    room: str | None = None
    mqtt_topic: str | None = None
    protocol: str = "mqtt"
    mac_address: str | None = None
    ip_address: str | None = None
    metadata: dict = {}
    created_at: datetime | None = None


class DeviceState(BaseModel):
    device_id: str
    state: dict
    updated_at: datetime | None = None


class AutomationRule(BaseModel):
    id: str
    name: str
    enabled: bool = True
    trigger_type: str
    trigger_config: dict = {}
    conditions: list[dict] = []
    actions: list[dict] = []
    created_at: datetime | None = None


class Scene(BaseModel):
    id: str
    name: str
    actions: list[dict] = []
    created_at: datetime | None = None


class Schedule(BaseModel):
    id: str
    name: str
    cron_expr: str
    action_type: str
    action_config: dict = {}
    enabled: bool = True
    created_at: datetime | None = None


class EnergyReading(BaseModel):
    id: int | None = None
    device_id: str
    watts: float
    recorded_at: datetime | None = None


class CalendarEvent(BaseModel):
    id: str
    source: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    all_day: bool = False


class MailMessage(BaseModel):
    id: int | None = None
    uid: str
    folder: str = "INBOX"
    from_addr: str | None = None
    to_addr: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    is_read: bool = False
    received_at: datetime | None = None


class CallRecord(BaseModel):
    id: int | None = None
    direction: str
    remote_number: str | None = None
    remote_name: str | None = None
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    recording_path: str | None = None
    voicemail: bool = False


class Camera(BaseModel):
    id: str
    name: str
    type: str  # rtsp, usb, onvif
    url: str | None = None
    device_path: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool = True
    config: dict = {}
    created_at: datetime | None = None


class CameraEvent(BaseModel):
    id: int | None = None
    camera_id: str
    event_type: str
    label: str | None = None
    confidence: float | None = None
    bbox: list[float] | None = None
    thumbnail_path: str | None = None
    detected_at: datetime | None = None


class AuditEntry(BaseModel):
    id: int | None = None
    timestamp: datetime | None = None
    user_key: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: str | None = None
