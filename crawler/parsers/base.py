"""Base parser class and ParseResult data structure.

All site-specific parsers inherit from BaseParser and produce ParseResult objects.
The parser registry maps domains to parser classes for automatic dispatch.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar

from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Structured output from any HTML parser."""

    title: str
    text_content: str
    language: str  # ISO 639-1 code (en, de, fr, etc.)
    content_type: str  # transcription, transliteration, translation, commentary, index, mixed
    structural_markers: dict = field(default_factory=dict)
    source_url: str = ""
    source_attribution: str = ""
    extra_metadata: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Minimum quality check: must have title and meaningful text."""
        return bool(self.title.strip()) and len(self.text_content.strip()) >= 50


def detect_language(text: str) -> str:
    """Detect language of extracted text. Returns ISO 639-1 code or 'unknown'."""
    if not text or len(text.strip()) < 20:
        return "unknown"
    try:
        # Take a reasonable sample for detection
        sample = text[:5000]
        return detect(sample)
    except LangDetectException:
        return "unknown"


class BaseParser:
    """Abstract base for site-specific HTML parsers.

    Subclasses must implement:
        - parse(html: str, url: str) -> list[ParseResult]
        - DOMAINS: class variable listing handled domains
    """

    DOMAINS: ClassVar[list[str]] = []

    def parse(self, html: str, url: str) -> list[ParseResult]:
        """Parse HTML and return structured results. Multiple results if the page contains multiple distinct texts."""
        raise NotImplementedError

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize whitespace and strip non-content characters."""
        if not text:
            return ""
        # Collapse whitespace runs
        text = re.sub(r"[ \t]+", " ", text)
        # Normalize line endings
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def extract_text_from_soup(soup, selector: str | None = None) -> str:
        """Extract text from a BeautifulSoup object, optionally from a CSS selector."""
        if selector:
            el = soup.select_one(selector)
            if el is None:
                return ""
            return el.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)
