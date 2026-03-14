"""File operations with path traversal protection."""

import os
import stat
from datetime import datetime
from pathlib import Path

import aiofiles

from app.config import get_settings
from app.storage.schemas import FileInfo


def _safe_resolve(base_path: str, relative_path: str) -> Path:
    """Resolve a path and ensure it's within the base directory."""
    base = Path(base_path).resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError("Path traversal detected")
    return target


async def list_files(relative_path: str = "") -> list[FileInfo]:
    """List files in a directory."""
    settings = get_settings()
    target = _safe_resolve(settings.storage.base_path, relative_path)
    if not target.exists():
        return []

    files = []
    for entry in sorted(target.iterdir()):
        try:
            st = entry.stat()
            files.append(FileInfo(
                name=entry.name,
                path=str(entry.relative_to(Path(settings.storage.base_path).resolve())),
                type="directory" if entry.is_dir() else "file",
                size=st.st_size if entry.is_file() else 0,
                modified=datetime.fromtimestamp(st.st_mtime).isoformat(),
            ))
        except (PermissionError, OSError):
            continue
    return files


async def read_file(relative_path: str) -> Path:
    """Get the resolved path for file download."""
    settings = get_settings()
    target = _safe_resolve(settings.storage.base_path, relative_path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")
    return target


async def write_file(relative_path: str, content: bytes) -> str:
    """Write uploaded content to a file."""
    settings = get_settings()
    max_size = settings.storage.max_upload_mb * 1024 * 1024
    if len(content) > max_size:
        raise ValueError(f"File exceeds {settings.storage.max_upload_mb}MB limit")

    target = _safe_resolve(settings.storage.base_path, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(target, "wb") as f:
        await f.write(content)
    return str(target.relative_to(Path(settings.storage.base_path).resolve()))


async def delete_file(relative_path: str) -> None:
    """Delete a file."""
    settings = get_settings()
    target = _safe_resolve(settings.storage.base_path, relative_path)
    if target.is_file():
        target.unlink()
    elif target.is_dir():
        target.rmdir()
    else:
        raise FileNotFoundError(f"Not found: {relative_path}")
