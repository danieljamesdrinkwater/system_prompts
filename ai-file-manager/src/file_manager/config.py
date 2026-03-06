"""Configuration loading and validation."""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "drop_zone": "~/Desktop/File Manager",
    "openrouter": {
        "api_key": "",
        "model": "google/gemini-2.0-flash-001",
        "timeout": 30,
        "analyze_content": True,
        "max_content_chars": 2000,
    },
    "stabilization_delay": 2.0,
    "logging": {
        "level": "INFO",
        "file": "~/.file-manager/file_manager.log",
        "max_bytes": 10_485_760,
        "backup_count": 3,
    },
    "hierarchy": {
        "01 - Documents": {
            "subcategories": [
                "01 - Work", "02 - Personal",
                "03 - Finance/01 - Invoices", "03 - Finance/02 - Receipts",
                "03 - Finance/03 - Statements",
                "04 - Education", "05 - Legal", "06 - Medical", "07 - Notes",
            ],
            "extensions": [
                ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                ".odt", ".rtf", ".txt", ".md", ".csv",
            ],
        },
        "02 - Images": {
            "subcategories": [
                "01 - Photos", "02 - Screenshots", "03 - Graphics",
                "04 - Icons", "05 - Wallpapers",
            ],
            "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".ico", ".svg"],
        },
        "03 - Videos": {
            "subcategories": ["01 - Recordings", "02 - Tutorials", "03 - Personal"],
            "extensions": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"],
        },
        "04 - Audio": {
            "subcategories": [
                "01 - Music", "02 - Podcasts", "03 - Recordings", "04 - Sound Effects",
            ],
            "extensions": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
        },
        "05 - Downloads": {
            "subcategories": ["01 - Installers", "02 - Archives", "03 - Packages"],
            "extensions": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz"],
        },
        "06 - Code": {
            "subcategories": ["01 - Scripts", "02 - Projects", "03 - Snippets", "04 - Data"],
            "extensions": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".rb", ".sh", ".bat", ".ps1", ".sql", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        },
        "07 - Design": {
            "subcategories": [
                "01 - PSD", "02 - Figma Exports", "03 - SVG", "04 - Mockups",
            ],
            "extensions": [".psd", ".ai", ".sketch", ".fig", ".xd", ".indd"],
        },
        "08 - Miscellaneous": {
            "subcategories": [],
            "extensions": [],
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_paths(config: dict) -> dict:
    """Expand ~ in path-like config values."""
    config["drop_zone"] = str(Path(config["drop_zone"]).expanduser())
    config["logging"]["file"] = str(Path(config["logging"]["file"]).expanduser())
    return config


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from a YAML file, merged with defaults.

    Args:
        config_path: Path to config.yaml. If None, uses defaults only.

    Returns:
        Fully resolved configuration dictionary.
    """
    config = DEFAULT_CONFIG.copy()

    if config_path is not None:
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}
            config = _deep_merge(DEFAULT_CONFIG, user_config)

    config = _resolve_paths(config)
    return config


def get_valid_categories(config: dict) -> set[str]:
    """Return the set of all valid category paths from the hierarchy.

    E.g., {"Documents", "Documents/Work", "Documents/Finance/Invoices", ...}
    """
    categories = set()
    for top_level, info in config["hierarchy"].items():
        categories.add(top_level)
        for sub in info.get("subcategories", []):
            categories.add(f"{top_level}/{sub}")
    return categories


def build_extension_map(config: dict) -> dict[str, str]:
    """Build a mapping from file extension to top-level category.

    Returns:
        Dict like {".pdf": "Documents", ".mp3": "Audio", ...}
    """
    ext_map = {}
    for top_level, info in config["hierarchy"].items():
        for ext in info.get("extensions", []):
            if ext not in ext_map:  # first category wins for ambiguous extensions
                ext_map[ext] = top_level
    return ext_map
