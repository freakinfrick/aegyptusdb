"""PDF classification: text-searchable vs scanned image.

Checks for embedded text layers using pdfminer.six. If a meaningful
amount of extractable text exists, the PDF is text-searchable.
"""

from __future__ import annotations

import logging
from enum import Enum
from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

logger = logging.getLogger(__name__)

# Minimum characters to consider a page as having real text (not just artifacts)
MIN_TEXT_CHARS = 30
# Fraction of pages that must have text to classify as text-searchable
TEXT_PAGE_THRESHOLD = 0.5


class PDFType(Enum):
    TEXT_SEARCHABLE = "text_searchable"
    SCANNED = "scanned"
    MIXED = "mixed"  # Some pages text, some scanned
    EMPTY = "empty"


class PDFClassifier:
    """Classifies PDFs as text-searchable, scanned, or mixed."""

    def __init__(
        self,
        min_text_chars: int = MIN_TEXT_CHARS,
        text_page_threshold: float = TEXT_PAGE_THRESHOLD,
    ):
        self.min_text_chars = min_text_chars
        self.text_page_threshold = text_page_threshold

    def classify(self, pdf_path: str | Path) -> PDFType:
        """Classify a PDF as text-layer or image-only."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            return self._classify_by_text_extraction(pdf_path)
        except Exception as e:
            logger.warning("Classification failed for %s: %s", pdf_path, e)
            # If we can't even parse it, assume scanned
            return PDFType.SCANNED

    def classify_bytes(self, pdf_bytes: bytes) -> PDFType:
        """Classify a PDF from bytes (e.g., from MinIO)."""
        try:
            return self._classify_bytes_by_text(pdf_bytes)
        except Exception as e:
            logger.warning("Classification of PDF bytes failed: %s", e)
            return PDFType.SCANNED

    def _classify_by_text_extraction(self, pdf_path: Path) -> PDFType:
        with open(pdf_path, "rb") as f:
            return self._classify_stream(f)

    def _classify_bytes_by_text(self, pdf_bytes: bytes) -> PDFType:
        return self._classify_stream(BytesIO(pdf_bytes))

    def _classify_stream(self, stream) -> PDFType:
        """Core classification: try to extract text from each page."""
        stream.seek(0)
        parser = PDFParser(stream)
        document = PDFDocument(parser)

        pages_with_text = 0
        total_pages = 0

        stream.seek(0)
        for page in PDFPage.create_pages(document):
            total_pages += 1

        if total_pages == 0:
            return PDFType.EMPTY

        # Extract text page by page (sample up to 20 pages for large PDFs)
        max_sample = min(total_pages, 20)
        stream.seek(0)
        for i, page in enumerate(PDFPage.create_pages(document)):
            if i >= max_sample:
                break
            try:
                stream.seek(0)
                text = extract_text(stream, page_numbers=[i], maxpages=1)
                clean = text.strip()
                if len(clean) >= self.min_text_chars:
                    pages_with_text += 1
            except Exception:
                pass

        if pages_with_text == 0:
            return PDFType.SCANNED

        ratio = pages_with_text / max_sample
        if ratio >= self.text_page_threshold:
            return PDFType.TEXT_SEARCHABLE
        else:
            return PDFType.MIXED

    def get_page_count(self, pdf_path: str | Path) -> int:
        """Return the number of pages in a PDF."""
        pdf_path = Path(pdf_path)
        with open(pdf_path, "rb") as f:
            parser = PDFParser(f)
            document = PDFDocument(parser)
            return sum(1 for _ in PDFPage.create_pages(document))
