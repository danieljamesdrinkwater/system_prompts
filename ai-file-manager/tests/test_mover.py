"""Tests for file move operations."""

import tempfile
from pathlib import Path

from file_manager.classifier import ClassificationResult
from file_manager.mover import FileMover


def _make_config(base_path: str) -> dict:
    return {"drop_zone": base_path}


def test_move_file():
    """File is moved to the correct category directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        mover = FileMover(config)

        # Create a source file
        source = Path(tmpdir) / "test.pdf"
        source.write_text("hello")

        classification = ClassificationResult(
            category="01 - Documents/Work",
            suggested_name="test.pdf",
            confidence="high",
            reasoning="test",
        )

        result = mover.move_file(source, classification)
        assert result is not None
        assert result.exists()
        assert result == Path(tmpdir) / "01 - Documents" / "Work" / "test.pdf"
        assert not source.exists()


def test_move_file_duplicate():
    """Duplicate filenames get a counter suffix."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        mover = FileMover(config)

        # Create target directory with existing file
        target_dir = Path(tmpdir) / "01 - Documents" / "Work"
        target_dir.mkdir(parents=True)
        (target_dir / "test.pdf").write_text("existing")

        # Create source file
        source = Path(tmpdir) / "test.pdf"
        source.write_text("new")

        classification = ClassificationResult(
            category="01 - Documents/Work",
            suggested_name="test.pdf",
            confidence="high",
            reasoning="test",
        )

        result = mover.move_file(source, classification)
        assert result is not None
        assert result.name == "test_2.pdf"
        assert result.exists()


def test_move_file_multiple_duplicates():
    """Multiple duplicates get incrementing counters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        mover = FileMover(config)

        target_dir = Path(tmpdir) / "02 - Images" / "Photos"
        target_dir.mkdir(parents=True)
        (target_dir / "photo.jpg").write_text("1")
        (target_dir / "photo_2.jpg").write_text("2")

        source = Path(tmpdir) / "photo.jpg"
        source.write_text("3")

        classification = ClassificationResult(
            category="02 - Images/Photos",
            suggested_name="photo.jpg",
            confidence="high",
            reasoning="test",
        )

        result = mover.move_file(source, classification)
        assert result is not None
        assert result.name == "photo_3.jpg"


def test_move_file_source_missing():
    """Moving a non-existent file returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        mover = FileMover(config)

        source = Path(tmpdir) / "gone.pdf"

        classification = ClassificationResult(
            category="01 - Documents/Work",
            suggested_name="gone.pdf",
            confidence="high",
            reasoning="test",
        )

        result = mover.move_file(source, classification)
        assert result is None


def test_move_creates_directories():
    """Move creates target directories if they don't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(tmpdir)
        mover = FileMover(config)

        source = Path(tmpdir) / "invoice.pdf"
        source.write_text("content")

        classification = ClassificationResult(
            category="01 - Documents/Finance/Invoices",
            suggested_name="invoice.pdf",
            confidence="high",
            reasoning="test",
        )

        result = mover.move_file(source, classification)
        assert result is not None
        assert result.exists()
        assert "Finance" in str(result)
        assert "Invoices" in str(result)
