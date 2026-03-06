"""Folder hierarchy creation and validation."""

import platform
import subprocess
from pathlib import Path
from typing import Any

ORANGE_ICON = Path(__file__).resolve().parent.parent.parent / "assets" / "folder-orange.svg"

# macOS Finder orange label index (used by AppleScript)
_MACOS_ORANGE_LABEL = 1


def _set_folder_icon(folder: Path) -> None:
    """Set an orange folder icon/label, supporting both macOS and Linux."""
    if platform.system() == "Darwin":
        _set_macos_label(folder)
    else:
        _set_linux_icon(folder)


def _set_macos_label(folder: Path) -> None:
    """Set the macOS Finder label to orange via AppleScript."""
    script = (
        f'tell application "Finder" to set label index of '
        f'(POSIX file "{folder}" as alias) to {_MACOS_ORANGE_LABEL}'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _set_linux_icon(folder: Path) -> None:
    """Write a .directory file so Linux file managers show an orange folder icon."""
    if not ORANGE_ICON.exists():
        return
    dotdir = folder / ".directory"
    if not dotdir.exists():
        dotdir.write_text(f"[Desktop Entry]\nIcon={ORANGE_ICON}\n")


def create_hierarchy(base_path: str | Path, config: dict[str, Any]) -> None:
    """Create the full folder hierarchy under the base path.

    Args:
        base_path: Root drop zone path (e.g., ~/Desktop/File Manager).
        config: Full application config dict.
    """
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)

    for top_level, info in config["hierarchy"].items():
        top_dir = base / top_level
        top_dir.mkdir(exist_ok=True)
        _set_folder_icon(top_dir)
        for sub in info.get("subcategories", []):
            (base / top_level / sub).mkdir(parents=True, exist_ok=True)


def get_managed_dirs(base_path: str | Path, config: dict[str, Any]) -> set[Path]:
    """Return the set of top-level managed directory paths.

    Used by the watcher to ignore events inside managed subdirectories.
    """
    base = Path(base_path)
    managed = set()
    for top_level in config["hierarchy"]:
        managed.add(base / top_level)
    return managed


def is_valid_category(category: str, config: dict[str, Any]) -> bool:
    """Check if a category path is valid within the configured hierarchy.

    Args:
        category: Category path like "Documents/Finance/Invoices".
        config: Full application config dict.
    """
    parts = category.split("/", 1)
    top_level = parts[0]

    if top_level not in config["hierarchy"]:
        return False

    if len(parts) == 1:
        return True

    subcategory = parts[1]
    valid_subs = config["hierarchy"][top_level].get("subcategories", [])
    return subcategory in valid_subs
