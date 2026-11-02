"""Parser for pyramidtextsonline.com.

Site structure:
  - Main page is an index linking to external PDFs and resources
  - The site organizes Pyramid Text utterances by pyramid
  - Content type is primarily index/link aggregation
  - Returns 403 to some bots -- parser handles pre-fetched content
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import register_parser


@register_parser
class PyramidTextsParser(BaseParser):
    DOMAINS = ["pyramidtextsonline.com", "www.pyramidtextsonline.com"]

    def parse(self, html: str, url: str) -> list[ParseResult]:
        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles
        for tag in soup.find_all(["script", "style", "noscript"]):
            tag.decompose()

        title = self._extract_title(soup, url)

        # Check if this is an index/library page
        links = self._extract_resource_links(soup)
        text_content, markers = self._extract_content(soup)

        if links:
            markers["external_links"] = links[:100]

        if not text_content or len(text_content.strip()) < 30:
            # Even if text is sparse, the link inventory is valuable
            if links:
                text_content = f"Index page with {len(links)} resource links.\n\n"
                text_content += "\n".join(
                    f"- {link['text']}: {link['href']}" for link in links[:20]
                )

        if not text_content:
            return []

        text_content = self.clean_text(text_content)
        lang = detect_language(text_content)

        # Detect utterance numbers (Pyramid Texts are organized by utterance)
        utterances = self._extract_utterances(text_content)
        if utterances:
            markers["utterance_numbers"] = utterances

        content_type = "index" if links else "translation"

        return [ParseResult(
            title=title,
            text_content=text_content,
            language=lang if lang != "unknown" else "en",
            content_type=content_type,
            structural_markers=markers,
            source_url=url,
            source_attribution="pyramidtextsonline.com",
            extra_metadata={"site": "pyramidtextsonline.com"},
        )]

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return "Pyramid Texts Online"

    def _extract_content(self, soup: BeautifulSoup) -> tuple[str, dict]:
        markers: dict = {}
        body = soup.find("body")
        if body is None:
            return "", markers

        paragraphs = []
        for p in body.find_all(["p", "div", "td"]):
            text = p.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                paragraphs.append(text)

        return "\n\n".join(paragraphs), markers

    def _extract_resource_links(self, soup: BeautifulSoup) -> list[dict]:
        """Extract outbound links to PDFs and other resources."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            # Focus on substantive links (PDFs, external resources)
            is_pdf = href.lower().endswith(".pdf")
            is_external = href.startswith("http") and "pyramidtextsonline" not in href.lower()
            if is_pdf or is_external:
                links.append({"href": href, "text": text, "is_pdf": is_pdf})
        return links

    def _extract_utterances(self, text: str) -> list[int]:
        """Extract Pyramid Text utterance numbers from content."""
        # Patterns: "Utterance 123", "Utt. 123", "PT 123"
        matches = re.findall(
            r"(?:Utterance|Utt\.?|PT)\s*(\d+)", text, re.IGNORECASE
        )
        return sorted(set(int(m) for m in matches))
