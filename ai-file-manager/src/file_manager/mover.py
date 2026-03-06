"""File move, rename, and deduplication operations."""

import logging
import shutil
from pathlib import Path
from typing import Any

from .classifier import ClassificationResult

logger = logging.getLogger("file_manager")


class FileMover:
    """Handles moving classified files into the folder hierarchy."""

    def __init__(self, config: dict[str, Any]):
        self.base_path = Path(config["drop_zone"])

    def move_file(self, source: Path, classification: ClassificationResult) -> Path | None:
        """Move a file to its classified destination.

        Args:
            source: Original file path in the drop zone.
            classification: Result from the classifier.

        Returns:
            New file path, or None if the move failed.
        """
        if not source.exists():
            logger.warning("Source file no longer exists: %s", source)
            return None

        target_dir = self.base_path / classification.category
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / classification.suggested_name
        target_path = self._resolve_duplicate(target_path)

        try:
            shutil.move(str(source), str(target_path))
            logger.info(
                'MOVED "%s" -> "%s/%s" (confidence: %s, reason: %s)',
                source.name,
                classification.category,
                target_path.name,
                classification.confidence,
                classification.reasoning,
            )
            return target_path
        except OSError as e:
            logger.error("Failed to move %s -> %s: %s", source, target_path, e)
            return None

    def _resolve_duplicate(self, target: Path) -> Path:
        """If target exists, append _2, _3, etc. until a unique name is found."""
        if not target.exists():
            return target

        stem = target.stem
        ext = target.suffix
        parent = target.parent
        counter = 2

        while True:
            candidate = parent / f"{stem}_{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1
