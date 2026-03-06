"""File classification using OpenRouter (Gemini Flash) and extension-based fast path."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import build_extension_map, get_valid_categories
from .utils import extract_text_content, human_readable_size, sanitize_filename

logger = logging.getLogger("file_manager")

SYSTEM_PROMPT = """\
You are a file organization assistant. You categorize files into a folder hierarchy and suggest clean filenames.

You MUST respond with valid JSON only. No markdown, no explanation, no extra text.

The folder hierarchy is:
- 01 - Documents/Work
- 01 - Documents/Personal
- 01 - Documents/Finance/Invoices
- 01 - Documents/Finance/Receipts
- 01 - Documents/Finance/Statements
- 01 - Documents/Education
- 01 - Documents/Legal
- 01 - Documents/Medical
- 01 - Documents/Notes
- 02 - Images/Photos
- 02 - Images/Screenshots
- 02 - Images/Graphics
- 02 - Images/Icons
- 02 - Images/Wallpapers
- 03 - Videos/Recordings
- 03 - Videos/Tutorials
- 03 - Videos/Personal
- 04 - Audio/Music
- 04 - Audio/Podcasts
- 04 - Audio/Recordings
- 04 - Audio/Sound Effects
- 05 - Downloads/Installers
- 05 - Downloads/Archives
- 05 - Downloads/Packages
- 06 - Code/Scripts
- 06 - Code/Projects
- 06 - Code/Snippets
- 06 - Code/Data
- 07 - Design/PSD
- 07 - Design/Figma Exports
- 07 - Design/SVG
- 07 - Design/Mockups
- 08 - Miscellaneous

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
    ".mp3": "04 - Audio/Music",
    ".flac": "04 - Audio/Music",
    ".wav": "04 - Audio/Music",
    ".aac": "04 - Audio/Music",
    ".ogg": "04 - Audio/Music",
    ".m4a": "04 - Audio/Music",
    ".wma": "04 - Audio/Music",
    # Video
    ".mp4": "03 - Videos/Recordings",
    ".mov": "03 - Videos/Recordings",
    ".avi": "03 - Videos/Recordings",
    ".mkv": "03 - Videos/Recordings",
    ".wmv": "03 - Videos/Recordings",
    ".flv": "03 - Videos/Recordings",
    ".webm": "03 - Videos/Recordings",
    # Installers
    ".exe": "05 - Downloads/Installers",
    ".msi": "05 - Downloads/Installers",
    ".dmg": "05 - Downloads/Installers",
    ".pkg": "05 - Downloads/Installers",
    ".deb": "05 - Downloads/Installers",
    ".rpm": "05 - Downloads/Installers",
    ".appimage": "05 - Downloads/Installers",
    # Archives
    ".zip": "05 - Downloads/Archives",
    ".tar": "05 - Downloads/Archives",
    ".gz": "05 - Downloads/Archives",
    ".7z": "05 - Downloads/Archives",
    ".rar": "05 - Downloads/Archives",
    ".bz2": "05 - Downloads/Archives",
    ".xz": "05 - Downloads/Archives",
    # Design
    ".psd": "07 - Design/PSD",
    ".ai": "07 - Design/PSD",
    ".sketch": "07 - Design/Mockups",
    ".fig": "07 - Design/Figma Exports",
    ".xd": "07 - Design/Mockups",
    ".indd": "07 - Design/PSD",
    # Images — photos by default, AI refines
    ".ico": "02 - Images/Icons",
    ".heic": "02 - Images/Photos",
    ".bmp": "02 - Images/Photos",
    ".tiff": "02 - Images/Photos",
}


@dataclass
class ClassificationResult:
    """Result of classifying a file."""

    category: str
    suggested_name: str
    confidence: str  # "high", "medium", "low"
    reasoning: str


class FileClassifier:
    """Classifies files using extension fast-path and OpenRouter AI."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.ai_config = config["openrouter"]
        self.extension_map = build_extension_map(config)
        self.valid_categories = get_valid_categories(config)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.ai_config["api_key"],
        )

    def classify(self, filepath: Path) -> ClassificationResult:
        """Classify a file into the folder hierarchy.

        Tries extension-based fast path first, falls back to OpenRouter AI.
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
            logger.warning("OpenRouter classification failed for %s: %s", filepath.name, e)
            return self._fallback_classification(filepath)

    def _classify_with_ai(self, filepath: Path) -> ClassificationResult:
        """Use OpenRouter (Gemini Flash) to classify the file."""
        prompt = self._build_user_prompt(filepath)

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=256,
            temperature=0.1,
        )

        content = response.choices[0].message.content or ""
        parsed = self._parse_json_response(content)

        if parsed is None:
            logger.warning("Failed to parse OpenRouter response for %s: %s", filepath.name, content[:200])
            return self._fallback_classification(filepath)

        # Validate the category
        category = parsed.get("category", "08 - Miscellaneous")
        if category not in self.valid_categories:
            # Try just the top-level
            top = category.split("/")[0]
            if top in self.config["hierarchy"]:
                category = top
            else:
                category = "08 - Miscellaneous"

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
        """Build the user prompt for the AI model."""
        size = filepath.stat().st_size
        parts = [
            f"Categorize this file:",
            f"Filename: {filepath.name}",
            f"Extension: {filepath.suffix.lower() or '(none)'}",
            f"Size: {human_readable_size(size)}",
        ]

        if self.ai_config.get("analyze_content", True):
            content = extract_text_content(
                filepath,
                max_chars=self.ai_config.get("max_content_chars", 2000),
            )
            if content:
                parts.append(f"\nContent preview (first {len(content)} chars):\n{content}")

        parts.append('\nRespond with JSON: {"category": "...", "suggested_name": "...", "confidence": "...", "reasoning": "..."}')
        return "\n".join(parts)

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from AI response with multiple fallback strategies."""
        # Strip <think>...</think> blocks from reasoning models
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
        category = self.extension_map.get(ext, "08 - Miscellaneous")

        return ClassificationResult(
            category=category,
            suggested_name=sanitize_filename(filepath.name),
            confidence="low",
            reasoning=f"Fallback: extension {ext} mapped to {category}",
        )
