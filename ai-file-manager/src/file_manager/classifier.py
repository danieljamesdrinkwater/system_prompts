"""File classification using Ollama LLM and extension-based fast path."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ollama

from .config import build_extension_map, get_valid_categories
from .utils import extract_text_content, human_readable_size, sanitize_filename

logger = logging.getLogger("file_manager")

SYSTEM_PROMPT = """\
You are a file organization assistant. You categorize files into a folder hierarchy and suggest clean filenames.

You MUST respond with valid JSON only. No markdown, no explanation, no extra text.

The folder hierarchy is:
- Documents/Work
- Documents/Personal
- Documents/Finance/Invoices
- Documents/Finance/Receipts
- Documents/Finance/Statements
- Documents/Education
- Documents/Legal
- Documents/Medical
- Documents/Notes
- Images/Photos
- Images/Screenshots
- Images/Graphics
- Images/Icons
- Images/Wallpapers
- Videos/Recordings
- Videos/Tutorials
- Videos/Personal
- Audio/Music
- Audio/Podcasts
- Audio/Recordings
- Audio/Sound Effects
- Downloads/Installers
- Downloads/Archives
- Downloads/Packages
- Code/Scripts
- Code/Projects
- Code/Snippets
- Code/Data
- Design/PSD
- Design/Figma Exports
- Design/SVG
- Design/Mockups
- Miscellaneous

Rules for suggested filenames:
- Use lowercase with hyphens as separators
- Include dates in YYYY-MM format when detectable
- Keep the original file extension
- Remove random strings, UUIDs, and URL artifacts
- Keep meaningful words from the original name
- Maximum 60 characters (excluding extension)

Respond ONLY with JSON in this format:
{"category": "Category/Subcategory", "suggested_name": "clean-filename.ext", "confidence": "high|medium|low", "reasoning": "brief explanation"}"""

# Extension-to-subcategory fast mappings for unambiguous file types
EXTENSION_FAST_MAP: dict[str, str] = {
    # Audio
    ".mp3": "Audio/Music",
    ".flac": "Audio/Music",
    ".wav": "Audio/Music",
    ".aac": "Audio/Music",
    ".ogg": "Audio/Music",
    ".m4a": "Audio/Music",
    ".wma": "Audio/Music",
    # Video
    ".mp4": "Videos/Recordings",
    ".mov": "Videos/Recordings",
    ".avi": "Videos/Recordings",
    ".mkv": "Videos/Recordings",
    ".wmv": "Videos/Recordings",
    ".flv": "Videos/Recordings",
    ".webm": "Videos/Recordings",
    # Installers
    ".exe": "Downloads/Installers",
    ".msi": "Downloads/Installers",
    ".dmg": "Downloads/Installers",
    ".pkg": "Downloads/Installers",
    ".deb": "Downloads/Installers",
    ".rpm": "Downloads/Installers",
    ".appimage": "Downloads/Installers",
    # Archives
    ".zip": "Downloads/Archives",
    ".tar": "Downloads/Archives",
    ".gz": "Downloads/Archives",
    ".7z": "Downloads/Archives",
    ".rar": "Downloads/Archives",
    ".bz2": "Downloads/Archives",
    ".xz": "Downloads/Archives",
    # Design
    ".psd": "Design/PSD",
    ".ai": "Design/PSD",
    ".sketch": "Design/Mockups",
    ".fig": "Design/Figma Exports",
    ".xd": "Design/Mockups",
    ".indd": "Design/PSD",
    # Images — photos by default, AI refines
    ".ico": "Images/Icons",
    ".heic": "Images/Photos",
    ".bmp": "Images/Photos",
    ".tiff": "Images/Photos",
}


@dataclass
class ClassificationResult:
    """Result of classifying a file."""

    category: str
    suggested_name: str
    confidence: str  # "high", "medium", "low"
    reasoning: str


class FileClassifier:
    """Classifies files using extension fast-path and Ollama AI."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.ollama_config = config["ollama"]
        self.extension_map = build_extension_map(config)
        self.valid_categories = get_valid_categories(config)

    def classify(self, filepath: Path) -> ClassificationResult:
        """Classify a file into the folder hierarchy.

        Tries extension-based fast path first, falls back to Ollama AI.
        """
        ext = filepath.suffix.lower()

        # Fast path for unambiguous file types
        if ext in EXTENSION_FAST_MAP:
            category = EXTENSION_FAST_MAP[ext]
            return ClassificationResult(
                category=category,
                suggested_name=sanitize_filename(filepath.name),
                confidence="high",
                reasoning=f"Extension {ext} mapped to {category}",
            )

        # AI path for ambiguous files
        try:
            return self._classify_with_ai(filepath)
        except Exception as e:
            logger.warning("Ollama classification failed for %s: %s", filepath.name, e)
            return self._fallback_classification(filepath)

    def _classify_with_ai(self, filepath: Path) -> ClassificationResult:
        """Use Ollama to classify the file."""
        prompt = self._build_user_prompt(filepath)

        response = ollama.chat(
            model=self.ollama_config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"num_predict": 1024},
        )

        content = response["message"]["content"]
        parsed = self._parse_json_response(content)

        if parsed is None:
            logger.warning("Failed to parse Ollama response for %s: %s", filepath.name, content[:200])
            return self._fallback_classification(filepath)

        # Validate the category
        category = parsed.get("category", "Miscellaneous")
        if category not in self.valid_categories:
            # Try just the top-level
            top = category.split("/")[0]
            if top in self.config["hierarchy"]:
                category = top
            else:
                category = "Miscellaneous"

        suggested_name = parsed.get("suggested_name", sanitize_filename(filepath.name))
        # Ensure the extension is preserved
        if not suggested_name.endswith(filepath.suffix.lower()):
            suggested_name = Path(suggested_name).stem + filepath.suffix.lower()

        return ClassificationResult(
            category=category,
            suggested_name=sanitize_filename(suggested_name),
            confidence=parsed.get("confidence", "medium"),
            reasoning=parsed.get("reasoning", "AI classification"),
        )

    def _build_user_prompt(self, filepath: Path) -> str:
        """Build the user prompt for Ollama."""
        size = filepath.stat().st_size
        parts = [
            f"Categorize this file:",
            f"Filename: {filepath.name}",
            f"Extension: {filepath.suffix.lower() or '(none)'}",
            f"Size: {human_readable_size(size)}",
        ]

        if self.ollama_config.get("analyze_content", True):
            content = extract_text_content(
                filepath,
                max_chars=self.ollama_config.get("max_content_chars", 2000),
            )
            if content:
                parts.append(f"\nContent preview (first {len(content)} chars):\n{content}")

        parts.append('\nRespond with JSON: {"category": "...", "suggested_name": "...", "confidence": "...", "reasoning": "..."}')
        return "\n".join(parts)

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from Ollama response with multiple fallback strategies."""
        # Strip <think>...</think> blocks from reasoning models (e.g. deepseek-r1)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find first { to last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _fallback_classification(self, filepath: Path) -> ClassificationResult:
        """Classify using extension only when AI fails."""
        ext = filepath.suffix.lower()
        category = self.extension_map.get(ext, "Miscellaneous")

        return ClassificationResult(
            category=category,
            suggested_name=sanitize_filename(filepath.name),
            confidence="low",
            reasoning=f"Fallback: extension {ext} mapped to {category}",
        )
