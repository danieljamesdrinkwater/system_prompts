"""Shared utilities for content extraction and filename handling."""

import os
import re
import time
from pathlib import Path

# Extensions that are safe to read as text
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
                   ".toml", ".ini", ".cfg", ".py", ".js", ".ts", ".java",
                   ".c", ".cpp", ".go", ".rs", ".rb", ".sh", ".bat", ".sql",
                   ".html", ".css", ".rtf"}


def extract_text_content(filepath: Path, max_chars: int = 2000) -> str:
    """Extract text content from a file for AI analysis.

    Args:
        filepath: Path to the file.
        max_chars: Maximum characters to extract.

    Returns:
        Extracted text, or empty string if not a text file.
    """
    ext = filepath.suffix.lower()

    if ext in TEXT_EXTENSIONS:
        try:
            with open(filepath, "r", errors="replace") as f:
                return f.read(max_chars)
        except (OSError, UnicodeDecodeError):
            return ""

    if ext == ".pdf":
        return _extract_pdf_text(filepath, max_chars)

    return ""


def _extract_pdf_text(filepath: Path, max_chars: int) -> str:
    """Try to extract text from a PDF using PyPDF2 if available."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) >= max_chars:
                break
        return text[:max_chars]
    except ImportError:
        return ""
    except Exception:
        return ""


def sanitize_filename(name: str) -> str:
    """Clean up a filename, keeping it readable.

    - Strips problematic characters
    - Normalizes whitespace to hyphens
    - Lowercases
    - Truncates to 60 chars (excluding extension)
    """
    stem = Path(name).stem
    ext = Path(name).suffix.lower()

    # Remove URL artifacts and UUIDs
    stem = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'https?://\S+', '', stem)
    stem = re.sub(r'%[0-9A-Fa-f]{2}', '', stem)

    # Replace problematic chars with hyphens
    stem = re.sub(r'[^\w\s.-]', '-', stem)
    # Normalize whitespace and underscores to hyphens
    stem = re.sub(r'[\s_]+', '-', stem)
    # Collapse multiple hyphens
    stem = re.sub(r'-{2,}', '-', stem)
    # Strip leading/trailing hyphens and dots
    stem = stem.strip('-.')

    stem = stem.lower()

    # Truncate
    if len(stem) > 60:
        stem = stem[:60].rstrip('-')

    if not stem:
        stem = "unnamed"

    return stem + ext


def is_file_stable(filepath: Path, delay: float = 1.0) -> bool:
    """Check if a file's size has stopped changing.

    Args:
        filepath: Path to check.
        delay: Seconds to wait between size checks.

    Returns:
        True if the file size is stable.
    """
    if not filepath.exists():
        return False

    try:
        size1 = filepath.stat().st_size
        time.sleep(delay)
        if not filepath.exists():
            return False
        size2 = filepath.stat().st_size
        return size1 == size2
    except OSError:
        return False


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
