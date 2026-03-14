"""Camera module schemas."""

from pydantic import BaseModel


class CameraCreate(BaseModel):
    name: str
    type: str  # rtsp, usb, onvif
    url: str | None = None
    device_path: str | None = None
    username: str | None = None
    password: str | None = None
    config: dict = {}


class CameraUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool | None = None
    config: dict | None = None


class DetectionEvent(BaseModel):
    camera_id: str
    event_type: str
    label: str | None = None
    confidence: float | None = None
    bbox: list[float] | None = None
    thumbnail_path: str | None = None
    detected_at: str | None = None
