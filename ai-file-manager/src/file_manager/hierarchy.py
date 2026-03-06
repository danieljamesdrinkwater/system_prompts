"""Folder hierarchy creation and validation."""

from pathlib import Path
from typing import Any


def create_hierarchy(base_path: str | Path, config: dict[str, Any]) -> None:
    """Create the full folder hierarchy under the base path.

    Args:
        base_path: Root drop zone path (e.g., ~/Desktop/File Manager).
        config: Full application config dict.
    """
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)

    for top_level, info in config["hierarchy"].items():
        (base / top_level).mkdir(exist_ok=True)
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
