"""Parser for attalus.org/egypt pages.

Site structure:
  - Index at /egypt/index.html lists ~200 texts organized by category
  - Categories: mythology, magic, tales, biographies, letters, legal, historical, misc
  - Individual pages: h2 title, plain <p> paragraphs, minimal markup
  - Footnotes use img+em pattern, subheadings in italics
  - Attribution often via asterisk (*) = André Dollinger's translations
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import register_parser

# Categories from the attalus.org index
_CATEGORIES = {
    "mythology": "mythology, hymns, and rituals",
    "magic": "magic, dreams and oracles",
    "tales": "tales, teachings and instructions",
    "biographies": "biographies, memorials",
    "letters": "letters and documents",
    "legal": "legal and economic matters",
    "historical": "historical and political writings",
    "miscellaneous": "miscellaneous documents",
}


@register_parser
class AttalusParser(BaseParser):
    DOMAINS = ["attalus.org", "www.attalus.org"]

    def parse(self, html: str, url: str) -> list[ParseResult]:
        soup = BeautifulSoup(html, "html.parser")

        # Check if this is the index page
        if self._is_index_page(soup, url):
            return self._parse_index(soup, url)

        return self._parse_text_page(soup, url)

    def _is_index_page(self, soup: BeautifulSoup, url: str) -> bool:
        if "index" in url.lower():
            return True
        # Index page has multiple h2 sections with category headers
        h2s = soup.find_all("h2")
        return len(h2s) >= 5

    def _parse_index(self, soup: BeautifulSoup, url: str) -> list[ParseResult]:
        """Parse the index page -- extract metadata about available texts."""
        entries = []
        current_category = ""

        for h2 in soup.find_all("h2"):
            category_text = h2.get_text(strip=True).lower()
            for key, label in _CATEGORIES.items():
                if key in category_text:
                    current_category = label
                    break

        # Index pages are metadata-only -- return a single result describing the collection
        text = soup.get_text(separator="\n", strip=True)
        return [ParseResult(
            title="Attalus Egypt Index",
            text_content=self.clean_text(text),
            language="en",
            content_type="index",
            structural_markers={"type": "index", "categories": list(_CATEGORIES.values())},
            source_url=url,
            source_attribution="attalus.org (André Dollinger and others)",
        )]

    def _parse_text_page(self, soup: BeautifulSoup, url: str) -> list[ParseResult]:
        # Remove navigation/scripts
        for tag in soup.find_all(["script", "style", "noscript"]):
            tag.decompose()

        title = self._extract_title(soup, url)
        text_content, markers = self._extract_body(soup)

        if not text_content or len(text_content.strip()) < 30:
            return []

        text_content = self.clean_text(text_content)
        lang = detect_language(text_content)

        # Detect content type from markers or title
        content_type = self._classify_content(title, text_content)
        attribution = self._extract_attribution(soup)

        # Extract date if present in parenthetical
        date_info = self._extract_date(soup)
        if date_info:
            markers["date_note"] = date_info

        return [ParseResult(
            title=title,
            text_content=text_content,
            language=lang if lang != "unknown" else "en",
            content_type=content_type,
            structural_markers=markers,
            source_url=url,
            source_attribution=attribution,
            extra_metadata={"site": "attalus.org"},
        )]

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        # Attalus uses <h2> for the main title on text pages
        h2 = soup.find("h2")
        if h2:
            title = h2.get_text(strip=True)
            # Remove leading numbers (from section numbering)
            title = re.sub(r"^\[\d+\]\s*", "", title)
            if title:
                return title

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        return url.rsplit("/", 1)[-1].replace(".html", "").replace("_", " ").title()

    def _extract_body(self, soup: BeautifulSoup) -> tuple[str, dict]:
        markers: dict = {}
        body = soup.find("body")
        if body is None:
            return "", markers

        paragraphs = []
        line_refs = []

        for p in body.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if not text:
                continue

            # Skip navigation-like paragraphs
            if text.startswith("Source:") or text.startswith("Back to"):
                continue

            # Check for line references like "[line 5]" or "(col. II, line 3)"
            ref_matches = re.findall(r"(?:line|col\.?|column)\s*[\w.]+", text, re.IGNORECASE)
            if ref_matches:
                line_refs.extend(ref_matches)

            paragraphs.append(text)

        if line_refs:
            markers["line_references"] = line_refs[:50]  # Cap to avoid noise

        return "\n\n".join(paragraphs), markers

    def _extract_attribution(self, soup: BeautifulSoup) -> str:
        # Look for source/attribution info
        body_text = soup.get_text()[:3000]
        for pattern in [
            r"(?:Source|Adapted from|Based on):\s*(.+?)(?:\n|$)",
            r"[Tt]ranslat(?:ed|ion) by\s+(.+?)(?:\.|,|\n)",
        ]:
            m = re.search(pattern, body_text)
            if m:
                return f"attalus.org; {m.group(1).strip()}"
        return "attalus.org"

    def _classify_content(self, title: str, text: str) -> str:
        title_lower = title.lower()
        if any(w in title_lower for w in ["hymn", "prayer", "ritual", "liturgy"]):
            return "translation"
        if any(w in title_lower for w in ["tale", "story", "instruction", "teaching"]):
            return "translation"
        if any(w in title_lower for w in ["letter", "document", "decree"]):
            return "translation"
        if any(w in title_lower for w in ["biography", "memorial"]):
            return "translation"
        return "translation"  # Attalus is primarily English translations

    def _extract_date(self, soup: BeautifulSoup) -> str | None:
        # Dates are often in parentheses near the title
        body_text = soup.get_text()[:1000]
        m = re.search(r"\(c\.\s*\d+\s*(?:B\.?C\.?|A\.?D\.?)\)", body_text)
        if m:
            return m.group(0)
        return None
