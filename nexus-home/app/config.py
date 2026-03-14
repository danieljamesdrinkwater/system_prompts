"""Configuration loader — YAML config + environment variable overrides."""

import os
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel


class MQTTConfig(BaseModel):
    host: str = "mosquitto"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_prefix: str = "nexus"


class AIConfig(BaseModel):
    ollama_url: str = "http://ollama:11434"
    default_model: str = "llama3.2"


class VoiceConfig(BaseModel):
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    tts_model_path: str = "./models/en_US-lessac-medium.onnx"


class StorageConfig(BaseModel):
    base_path: str = "/mnt/storage"
    max_upload_mb: int = 500
    auto_mount: bool = True


class CalDAVConfig(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""


class GoogleCalendarConfig(BaseModel):
    credentials_file: str = ""
    calendar_id: str = "primary"


class CalendarConfig(BaseModel):
    caldav: CalDAVConfig = CalDAVConfig()
    google: GoogleCalendarConfig = GoogleCalendarConfig()
    sync_interval_minutes: int = 5


class IMAPConfig(BaseModel):
    host: str = ""
    port: int = 993
    username: str = ""
    password: str = ""
    use_ssl: bool = True


class SMTPConfig(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""


class MailConfig(BaseModel):
    imap: IMAPConfig = IMAPConfig()
    smtp: SMTPConfig = SMTPConfig()
    sync_interval_minutes: int = 2


class SIPConfig(BaseModel):
    server: str = ""
    port: int = 5060
    username: str = ""
    password: str = ""
    realm: str = ""


class TelephonyConfig(BaseModel):
    sip: SIPConfig = SIPConfig()
    voicemail_path: str = "/app/data/voicemail"
    auto_answer: bool = False
    ai_attendant: bool = True


class DetectionConfig(BaseModel):
    model: str = "yolov8n.pt"
    confidence_threshold: float = 0.5
    detection_fps: int = 5
    classes: list[str] = ["person", "car", "truck", "dog", "cat", "package"]


class CameraConfig(BaseModel):
    recording_path: str = "/mnt/storage/recordings"
    snapshot_path: str = "/app/data/snapshots"
    detection: DetectionConfig = DetectionConfig()
    retention_days: int = 30


class NotificationsConfig(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
    webhook_urls: list[str] = []
    ntfy_topic: str = ""


class EnergyConfig(BaseModel):
    enabled: bool = True
    retention_days: int = 90


class RoomConfig(BaseModel):
    name: str
    devices: list[str] = []


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    api_keys: list[str] = ["change-me-to-a-real-key"]
    log_level: str = "info"


class Settings(BaseModel):
    server: ServerConfig = ServerConfig()
    mqtt: MQTTConfig = MQTTConfig()
    ai: AIConfig = AIConfig()
    voice: VoiceConfig = VoiceConfig()
    storage: StorageConfig = StorageConfig()
    calendar: CalendarConfig = CalendarConfig()
    mail: MailConfig = MailConfig()
    telephony: TelephonyConfig = TelephonyConfig()
    cameras: CameraConfig = CameraConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    energy: EnergyConfig = EnergyConfig()
    rooms: list[RoomConfig] = []


def load_yaml_config(path: str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if path is None:
        path = os.environ.get("NEXUS_CONFIG_PATH", "config.yaml")
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings from YAML config."""
    raw = load_yaml_config()
    return Settings(**raw)
