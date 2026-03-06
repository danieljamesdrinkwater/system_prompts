"""Tests for file classification."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from file_manager.classifier import ClassificationResult, FileClassifier
from file_manager.config import load_config


def _make_config() -> dict:
    """Load config with a dummy API key for testing."""
    config = load_config(None)
    config["openrouter"]["api_key"] = "sk-or-test-fake-key"
    return config


def _make_temp_file(name: str, content: str = "test") -> Path:
    """Create a temporary file with the given name."""
    tmp_dir = Path(tempfile.mkdtemp())
    filepath = tmp_dir / name
    filepath.write_text(content)
    return filepath


def test_fast_path_mp3():
    """MP3 files should be classified via fast path without AI."""
    config = _make_config()
    classifier = FileClassifier(config)
    filepath = _make_temp_file("song.mp3")

    result = classifier.classify(filepath)
    assert result.category == "04 - Audio/01 - Music"
    assert result.confidence == "high"
    assert "song.mp3" == result.suggested_name


def test_fast_path_zip():
    """ZIP files should be classified as Downloads/Archives."""
    config = _make_config()
    classifier = FileClassifier(config)
    filepath = _make_temp_file("backup.zip")

    result = classifier.classify(filepath)
    assert result.category == "05 - Downloads/02 - Archives"
    assert result.confidence == "high"


def test_fast_path_exe():
    """EXE files should be classified as Downloads/Installers."""
    config = _make_config()
    classifier = FileClassifier(config)
    filepath = _make_temp_file("setup.exe")

    result = classifier.classify(filepath)
    assert result.category == "05 - Downloads/01 - Installers"


def test_parse_json_clean():
    """Classifier can parse clean JSON responses."""
    config = _make_config()
    classifier = FileClassifier(config)

    response = json.dumps({
        "category": "01 - Documents/01 - Work",
        "suggested_name": "quarterly-report.pdf",
        "confidence": "high",
        "reasoning": "Quarterly report document",
    })
    result = classifier._parse_json_response(response)
    assert result["category"] == "01 - Documents/01 - Work"


def test_parse_json_markdown_block():
    """Classifier can extract JSON from markdown code blocks."""
    config = _make_config()
    classifier = FileClassifier(config)

    response = '```json\n{"category": "02 - Images/01 - Photos", "suggested_name": "sunset.jpg", "confidence": "high", "reasoning": "photo"}\n```'
    result = classifier._parse_json_response(response)
    assert result["category"] == "02 - Images/01 - Photos"


def test_parse_json_with_text():
    """Classifier can find JSON embedded in surrounding text."""
    config = _make_config()
    classifier = FileClassifier(config)

    response = 'Here is the classification:\n{"category": "06 - Code/01 - Scripts", "suggested_name": "deploy.sh", "confidence": "medium", "reasoning": "shell script"}\nDone.'
    result = classifier._parse_json_response(response)
    assert result["category"] == "06 - Code/01 - Scripts"


def test_parse_json_with_think_tags():
    """Classifier strips <think> blocks from reasoning models."""
    config = _make_config()
    classifier = FileClassifier(config)

    response = '<think>\nLet me analyze this file. It has a .pdf extension and the name suggests it is a financial document.\n</think>\n{"category": "01 - Documents/03 - Finance/01 - Invoices", "suggested_name": "invoice-march.pdf", "confidence": "high", "reasoning": "invoice document"}'
    result = classifier._parse_json_response(response)
    assert result is not None
    assert result["category"] == "01 - Documents/03 - Finance/01 - Invoices"


def test_parse_json_invalid():
    """Invalid JSON returns None."""
    config = _make_config()
    classifier = FileClassifier(config)

    result = classifier._parse_json_response("not json at all")
    assert result is None


def test_fallback_classification():
    """Fallback uses extension map when AI fails."""
    config = _make_config()
    classifier = FileClassifier(config)
    filepath = _make_temp_file("report.pdf")

    result = classifier._fallback_classification(filepath)
    assert result.category == "01 - Documents"
    assert result.confidence == "low"


def test_fallback_unknown_extension():
    """Unknown extensions fall back to Miscellaneous."""
    config = _make_config()
    classifier = FileClassifier(config)
    filepath = _make_temp_file("mystery.xyz123")

    result = classifier._fallback_classification(filepath)
    assert result.category == "08 - Miscellaneous"


def test_ai_classification():
    """AI classification calls OpenRouter and parses the response."""
    config = _make_config()
    classifier = FileClassifier(config)

    # Mock the OpenAI client's chat completions
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "category": "01 - Documents/03 - Finance/01 - Invoices",
        "suggested_name": "2024-03-electricity-bill.pdf",
        "confidence": "high",
        "reasoning": "Electricity bill invoice",
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    classifier.client.chat.completions.create = MagicMock(return_value=mock_response)

    filepath = _make_temp_file("report.pdf", content="Electricity bill for March 2024")
    result = classifier._classify_with_ai(filepath)
    assert result.category == "01 - Documents/03 - Finance/01 - Invoices"
    assert "electricity" in result.suggested_name


def test_ai_invalid_category_falls_back():
    """AI returning an invalid category falls back to top-level or Miscellaneous."""
    config = _make_config()
    classifier = FileClassifier(config)

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "category": "01 - Documents/Cooking",
        "suggested_name": "recipe.pdf",
        "confidence": "high",
        "reasoning": "A recipe",
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    classifier.client.chat.completions.create = MagicMock(return_value=mock_response)

    filepath = _make_temp_file("recipe.pdf")
    result = classifier._classify_with_ai(filepath)
    # Should fall back to "01 - Documents" (valid top-level)
    assert result.category == "01 - Documents"
