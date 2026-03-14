"""Storage module schemas."""

from pydantic import BaseModel


class FileInfo(BaseModel):
    name: str
    path: str
    type: str  # file or directory
    size: int = 0
    modified: str | None = None


class DiskInfo(BaseModel):
    name: str
    size: str
    fstype: str | None = None
    mountpoint: str | None = None
    label: str | None = None
    uuid: str | None = None
    used: int | None = None
    available: int | None = None
    use_percent: str | None = None


class MountRequest(BaseModel):
    device: str
    mount_point: str | None = None


class UnmountRequest(BaseModel):
    mount_point: str
