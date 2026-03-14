"""Tests for storage module."""

import os
import pytest
from pathlib import Path
from app.storage.service import _safe_resolve, list_files, write_file, delete_file


def test_safe_resolve_blocks_traversal(tmp_path):
    """Path traversal attempts should be rejected."""
    with pytest.raises(PermissionError):
        _safe_resolve(str(tmp_path), "../../../etc/passwd")


def test_safe_resolve_allows_valid_path(tmp_path):
    """Valid paths within base should be allowed."""
    sub = tmp_path / "docs"
    sub.mkdir()
    result = _safe_resolve(str(tmp_path), "docs")
    assert str(result) == str(sub)


@pytest.mark.asyncio
async def test_list_files_empty(tmp_path, monkeypatch):
    """Empty directory should return empty list."""
    from app.config import get_settings, Settings, StorageConfig
    settings = Settings(storage=StorageConfig(base_path=str(tmp_path)))
    monkeypatch.setattr("app.storage.service.get_settings", lambda: settings)

    files = await list_files("")
    assert files == []


@pytest.mark.asyncio
async def test_write_and_list(tmp_path, monkeypatch):
    """Writing a file should make it appear in listings."""
    from app.config import Settings, StorageConfig
    settings = Settings(storage=StorageConfig(base_path=str(tmp_path)))
    monkeypatch.setattr("app.storage.service.get_settings", lambda: settings)

    await write_file("test.txt", b"hello world")
    files = await list_files("")
    assert len(files) == 1
    assert files[0].name == "test.txt"
    assert files[0].type == "file"
