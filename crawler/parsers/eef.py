"""Parser for EEF (Egyptologists' Electronic Forum) pages.

Site structure:
  - EEFtexts.html: curated list of digitized source texts
  - EEFSourcetexts.html: link index organized by historical period
  - These are link aggregation pages, not direct text content
  - Organized by period: OK/FIP, MK/SIP, NK/TIP, LP/Greco-Roman
  - Each entry has text name, museum/collection info, and multiple resource links
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import register_parser

# EEF period markers
_PERIODS = [
    "OK", "FIP", "Old Kingdom", "First Intermediate",
    "MK", "SIP", "Middle Kingdom", "Second Intermediate",
    "NK", "TIP", "New Kingdom", "Third Intermediate",
    "LP", "Greco-Roman", "Late Period", "Ptolemaic",
]


@register_parser
class EEFParser(BaseParser):
    DOMAINS = ["egyptologyforum.org", "www.egyptologyforum.org"]

    def parse(self, html: str, url: str) -> list[ParseResult]:
        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles
        for tag in soup.find_all(["script", "style", "noscript"]):
            tag.decompose()

        title = self._extract_title(soup, url)
        entries = self._extract_entries(soup, url)
        text_content = soup.get_text(separator="\n", strip=True)

        if not text_content:
            return []

        text_content = self.clean_text(text_content)

        # Classify periods found on the page
        periods_found = []
        for period in _PERIODS:
            if period in text_content:
                periods_found.append(period)

        markers: dict = {}
        if periods_found:
            markers["periods"] = periods_found
        if entries:
            markers["resource_entries"] = len(entries)
            markers["external_links"] = entries[:100]

        lang = detect_language(text_content)

        return [ParseResult(
            title=title,
            text_content=text_content,
            language=lang if lang != "unknown" else "en",
            content_type="index",
            structural_markers=markers,
            source_url=url,
            source_attribution="Egyptologists' Electronic Forum (EEF)",
            extra_metadata={
                "site": "egyptologyforum.org",
                "entry_count": len(entries),
            },
        )]

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        if "EEFtexts" in url:
            return "EEF Guide to Internet Resources for Ancient Egyptian Texts"
        if "EEFSource" in url:
            return "EEF Digitized Source Texts"
        return "EEF Resource Page"

    def _extract_entries(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """Extract structured resource entries from the EEF page."""
        entries = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            # Skip internal anchors and mailto
            if href.startswith("#") or href.startswith("mailto:"):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)

            # Detect resource type
            href_lower = href.lower()
            if href_lower.endswith(".pdf"):
                rtype = "pdf"
            elif any(d in href_lower for d in ["jstor", "persee", "archive.org"]):
                rtype = "journal"
            elif any(d in href_lower for d in ["museum", "british", "louvre", "cairo"]):
                rtype = "museum"
            else:
                rtype = "web"

            entries.append({
                "text": text[:200],
                "href": full_url,
                "type": rtype,
            })

        return entries
