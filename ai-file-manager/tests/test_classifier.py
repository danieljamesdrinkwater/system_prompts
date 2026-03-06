"""Tests for file classification."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from file_manager.classifier import ClassificationResult, FileClassifier
from file_manager.config import load_config


def _make_temp_file(name: str, content: str = "test") -> Path:
    """Create a temporary file with the given name."""
    tmp_dir = Path(tempfile.mkdtemp())
    filepath = tmp_dir / name
    filepath.write_text(content)
    return filepath


def test_fast_path_mp3():
    """MP3 files should be classified via fast path without AI."""
    config = load_config(None)
    classifier = FileClassifier(config)
    filepath = _make_temp_file("song.mp3")

    result = classifier.classify(filepath)
    assert result.category == "Audio/Music"
    assert result.confidence == "high"
    assert "song.mp3" == result.suggested_name


def test_fast_path_zip():
    """ZIP files should be classified as Downloads/Archives."""
    config = load_config(None)
    classifier = FileClassifier(config)
    filepath = _make_temp_file("backup.zip")

    result = classifier.classify(filepath)
    assert result.category == "Downloads/Archives"
    assert result.confidence == "high"


def test_fast_path_exe():
    """EXE files should be classified as Downloads/Installers."""
    config = load_config(None)
    classifier = FileClassifier(config)
    filepath = _make_temp_file("setup.exe")

    result = classifier.classify(filepath)
    assert result.category == "Downloads/Installers"


def test_parse_json_clean():
    """Classifier can parse clean JSON responses."""
    config = load_config(None)
    classifier = FileClassifier(config)

    response = json.dumps({
        "category": "Documents/Work",
        "suggested_name": "quarterly-report.pdf",
        "confidence": "high",
        "reasoning": "Quarterly report document",
    })
    result = classifier._parse_json_response(response)
    assert result["category"] == "Documents/Work"


def test_parse_json_markdown_block():
    """Classifier can extract JSON from markdown code blocks."""
    config = load_config(None)
    classifier = FileClassifier(config)

    response = '```json\n{"category": "Images/Photos", "suggested_name": "sunset.jpg", "confidence": "high", "reasoning": "photo"}\n```'
    result = classifier._parse_json_response(response)
    assert result["category"] == "Images/Photos"


def test_parse_json_with_text():
    """Classifier can find JSON embedded in surrounding text."""
    config = load_config(None)
    classifier = FileClassifier(config)

    response = 'Here is the classification:\n{"category": "Code/Scripts", "suggested_name": "deploy.sh", "confidence": "medium", "reasoning": "shell script"}\nDone.'
    result = classifier._parse_json_response(response)
    assert result["category"] == "Code/Scripts"


def test_parse_json_invalid():
    """Invalid JSON returns None."""
    config = load_config(None)
    classifier = FileClassifier(config)

    result = classifier._parse_json_response("not json at all")
    assert result is None


def test_fallback_classification():
    """Fallback uses extension map when AI fails."""
    config = load_config(None)
    classifier = FileClassifier(config)
    filepath = _make_temp_file("report.pdf")

    result = classifier._fallback_classification(filepath)
    assert result.category == "Documents"
    assert result.confidence == "low"


def test_fallback_unknown_extension():
    """Unknown extensions fall back to Miscellaneous."""
    config = load_config(None)
    classifier = FileClassifier(config)
    filepath = _make_temp_file("mystery.xyz123")

    result = classifier._fallback_classification(filepath)
    assert result.category == "Miscellaneous"


@patch("file_manager.classifier.ollama")
def test_ai_classification(mock_ollama):
    """AI classification calls Ollama and parses the response."""
    config = load_config(None)
    classifier = FileClassifier(config)

    mock_ollama.chat.return_value = {
        "message": {
            "content": json.dumps({
                "category": "Documents/Finance/Invoices",
                "suggested_name": "2024-03-electricity-bill.pdf",
                "confidence": "high",
                "reasoning": "Electricity bill invoice",
            })
        }
    }

    filepath = _make_temp_file("report.pdf", content="Electricity bill for March 2024")
    result = classifier._classify_with_ai(filepath)
    assert result.category == "Documents/Finance/Invoices"
    assert "electricity" in result.suggested_name


@patch("file_manager.classifier.ollama")
def test_ai_invalid_category_falls_back(mock_ollama):
    """AI returning an invalid category falls back to top-level or Miscellaneous."""
    config = load_config(None)
    classifier = FileClassifier(config)

    mock_ollama.chat.return_value = {
        "message": {
            "content": json.dumps({
                "category": "Documents/Cooking",
                "suggested_name": "recipe.pdf",
                "confidence": "high",
                "reasoning": "A recipe",
            })
        }
    }

    filepath = _make_temp_file("recipe.pdf")
    result = classifier._classify_with_ai(filepath)
    # Should fall back to "Documents" (valid top-level)
    assert result.category == "Documents"
