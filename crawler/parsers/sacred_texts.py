"""Parser for sacred-texts.com/egy pages.

sacred-texts.com returns 403 to bot user agents, so this parser handles
pre-fetched content (e.g., manually downloaded or cached in MinIO).

Site structure:
  - Index at /egy/index.htm lists books/collections
  - Individual pages contain chapter-by-chapter English translations
  - Minimal HTML: <h1>/<h2> titles, <p> paragraphs, some <a> footnotes
  - Content is public domain (pre-1923 translations)
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import register_parser


@register_parser
class SacredTextsParser(BaseParser):
    DOMAINS = ["sacred-texts.com", "www.sacred-texts.com"]

    def parse(self, html: str, url: str) -> list[ParseResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        title = self._extract_title(soup, url)
        text_content, markers = self._extract_content(soup)

        if not text_content or len(text_content.strip()) < 50:
            return []

        text_content = self.clean_text(text_content)
        lang = detect_language(text_content)

        # sacred-texts.com hosts primarily English translations of Egyptian texts
        attribution = self._extract_attribution(soup)

        results.append(ParseResult(
            title=title,
            text_content=text_content,
            language=lang if lang != "unknown" else "en",
            content_type="translation",
            structural_markers=markers,
            source_url=url,
            source_attribution=attribution,
            extra_metadata={"site": "sacred-texts.com", "blocked": True},
        ))

        return results

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        # Try <title> tag first (most reliable on sacred-texts)
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Remove common suffixes
            for suffix in [" - sacred-texts.com", " Index", "Sacred Texts"]:
                title = title.removesuffix(suffix).strip()
            if title:
                return title

        # Try h1/h2
        for tag in ["h1", "h2"]:
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)

        # Fall back to URL path
        return url.rsplit("/", 1)[-1].replace(".htm", "").replace(".html", "").replace("_", " ").title()

    def _extract_content(self, soup: BeautifulSoup) -> tuple[str, dict]:
        markers: dict = {}

        # Remove navigation, scripts, styles
        for tag in soup.find_all(["script", "style", "nav", "noscript"]):
            tag.decompose()

        # sacred-texts uses simple <p> tags for content
        # Look for main content area -- often the body directly or a content div
        body = soup.find("body")
        if body is None:
            return "", markers

        paragraphs = []
        chapter_refs = []

        for p in body.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if not text:
                continue

            # Detect chapter/verse markers
            chap_match = re.match(r"^(?:Chapter|CHAPTER)\s+(\w+)", text)
            if chap_match:
                chapter_refs.append(chap_match.group(1))

            # Detect verse numbers (common pattern: "1. text..." or "[1] text...")
            verse_match = re.match(r"^(?:(\d+)\.\s|^\[(\d+)\]\s)", text)
            if verse_match:
                verse_num = verse_match.group(1) or verse_match.group(2)
                if "verse_numbers" not in markers:
                    markers["verse_numbers"] = []
                markers["verse_numbers"].append(int(verse_num))

            paragraphs.append(text)

        if chapter_refs:
            markers["chapters"] = chapter_refs

        return "\n\n".join(paragraphs), markers

    def _extract_attribution(self, soup: BeautifulSoup) -> str:
        # Look for translator/author info in the page
        # sacred-texts often has "translated by" or author info near the top
        body_text = soup.get_text()[:2000]
        for pattern in [
            r"[Tt]ranslated by\s+(.+?)(?:\.|,|\n)",
            r"[Bb]y\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"(?:Author|Translator):\s*(.+?)(?:\n|$)",
        ]:
            m = re.search(pattern, body_text)
            if m:
                return f"sacred-texts.com; {m.group(1).strip()}"
        return "sacred-texts.com"
