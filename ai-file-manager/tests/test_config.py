"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import yaml

from file_manager.config import build_extension_map, get_valid_categories, load_config


def test_load_defaults():
    """Loading with no config file returns sensible defaults."""
    config = load_config(None)
    assert "drop_zone" in config
    assert "hierarchy" in config
    assert "Documents" in config["hierarchy"]
    assert config["openrouter"]["model"] == "google/gemini-2.0-flash-001"


def test_load_config_file():
    """User config overrides defaults."""
    user_config = {
        "openrouter": {"model": "google/gemini-2.5-flash"},
        "stabilization_delay": 5.0,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(user_config, f)
        f.flush()
        config = load_config(f.name)

    assert config["openrouter"]["model"] == "google/gemini-2.5-flash"
    assert config["stabilization_delay"] == 5.0
    # Defaults should still be present for non-overridden keys
    assert config["openrouter"]["timeout"] == 30
    assert "Documents" in config["hierarchy"]


def test_paths_expanded():
    """Tilde in paths should be expanded."""
    config = load_config(None)
    assert "~" not in config["drop_zone"]
    assert "~" not in config["logging"]["file"]


def test_get_valid_categories():
    """Valid categories includes top-level and subcategories."""
    config = load_config(None)
    categories = get_valid_categories(config)
    assert "Documents" in categories
    assert "Documents/Work" in categories
    assert "Documents/Finance/Invoices" in categories
    assert "Miscellaneous" in categories


def test_build_extension_map():
    """Extension map covers expected extensions."""
    config = load_config(None)
    ext_map = build_extension_map(config)
    assert ext_map[".pdf"] == "Documents"
    assert ext_map[".mp3"] == "Audio"
    assert ext_map[".py"] == "Code"
    assert ext_map[".jpg"] == "Images"
    assert ext_map[".zip"] == "Downloads"
