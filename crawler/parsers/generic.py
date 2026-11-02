"""Generic fallback parser using readability-style extraction.

Used for unknown domains where no site-specific parser is registered.
Applies heuristics to find the main content area and extract clean text.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import register_parser

# Tags that typically contain boilerplate, not content
_BOILERPLATE_TAGS = {
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "iframe", "object", "embed",
}

# CSS class/id patterns that indicate boilerplate
_BOILERPLATE_PATTERNS = re.compile(
    r"(?:nav|menu|sidebar|footer|header|comment|widget|ad[sv]|social|share|related|popup|modal|cookie|banner)",
    re.IGNORECASE,
)


@register_parser
class GenericParser(BaseParser):
    # No DOMAINS -- this is the fallback, obtained via get_parser() when no match
    DOMAINS = []

    def parse(self, html: str, url: str) -> list[ParseResult]:
        soup = BeautifulSoup(html, "html.parser")

        # Strip boilerplate
        self._remove_boilerplate(soup)

        title = self._extract_title(soup, url)
        content_el = self._find_main_content(soup)

        if content_el is None:
            content_el = soup.find("body") or soup

        text_content = content_el.get_text(separator="\n", strip=True)
        text_content = self.clean_text(text_content)

        if not text_content or len(text_content.strip()) < 50:
            return []

        lang = detect_language(text_content)
        content_type = self._classify_content(text_content, url)

        markers: dict = {}
        # Count structural elements
        headings = content_el.find_all(re.compile(r"h[1-6]"))
        if headings:
            markers["heading_count"] = len(headings)
            markers["headings"] = [h.get_text(strip=True)[:100] for h in headings[:20]]

        # Look for links to resources
        links = content_el.find_all("a", href=True)
        ext_links = [
            a["href"] for a in links
            if a["href"].startswith("http") and len(a.get_text(strip=True)) > 3
        ]
        if ext_links:
            markers["link_count"] = len(ext_links)

        return [ParseResult(
            title=title,
            text_content=text_content,
            language=lang,
            content_type=content_type,
            structural_markers=markers,
            source_url=url,
            source_attribution=self._extract_domain(url),
            extra_metadata={"parser": "generic"},
        )]

    def _remove_boilerplate(self, soup: BeautifulSoup) -> None:
        """Remove navigation, ads, and other non-content elements."""
        # Remove known boilerplate tags
        for tag_name in _BOILERPLATE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove elements with boilerplate class/id patterns
        for tag in soup.find_all(True):
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "")
            if _BOILERPLATE_PATTERNS.search(classes) or _BOILERPLATE_PATTERNS.search(tag_id):
                tag.decompose()

    def _find_main_content(self, soup: BeautifulSoup) -> Tag | None:
        """Find the main content container using common patterns."""
        # Try semantic elements first
        for selector in ["main", "article", "[role='main']"]:
            el = soup.select_one(selector)
            if el:
                return el

        # Try common content class/id patterns
        for selector in [
            "#content", "#main-content", "#main", ".content", ".main-content",
            ".post-content", ".entry-content", ".article-body", ".page-content",
        ]:
            el = soup.select_one(selector)
            if el:
                return el

        # Heuristic: find the div with the most text content
        body = soup.find("body")
        if body is None:
            return None

        best_el = None
        best_len = 0
        for div in body.find_all(["div", "section"]):
            text_len = len(div.get_text(strip=True))
            # Penalize elements that are just thin wrappers
            child_divs = div.find_all(["div", "section"], recursive=False)
            if len(child_divs) == 1 and child_divs[0] == div:
                continue
            if text_len > best_len:
                best_len = text_len
                best_el = div

        return best_el

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Remove common suffixes
            title = re.sub(r"\s*[|–-]\s*[^|–-]*$", "", title).strip()
            if title:
                return title
        for tag in ["h1", "h2"]:
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        return url.rsplit("/", 1)[-1].split("?")[0].replace("-", " ").replace("_", " ").title()

    def _classify_content(self, text: str, url: str) -> str:
        """Heuristic content type classification."""
        text_lower = text[:2000].lower()
        url_lower = url.lower()

        # Check for index/list pages
        if any(w in url_lower for w in ["index", "list", "catalog", "collection"]):
            return "index"
        if text_lower.count("http") > 10:
            return "index"

        # Check for academic/commentary content
        if any(w in text_lower for w in ["bibliography", "footnote", "cf.", "ibid"]):
            return "commentary"

        # Check for transliteration markers
        if any(w in text_lower for w in ["transliteration", "hieroglyphic", "hieratic"]):
            return "transliteration"

        return "mixed"

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or url
