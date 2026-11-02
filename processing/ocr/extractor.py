"""PDF text extraction: pdftotext/pdfminer for text-searchable, Tesseract for scanned.

Handles graceful degradation when Tesseract is not installed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.layout import LAParams

from .classifier import PDFClassifier, PDFType

logger = logging.getLogger(__name__)

# Check for system tools at import time
TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
PDFTOTEXT_AVAILABLE = shutil.which("pdftotext") is not None
PDF2IMAGE_AVAILABLE = False

try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    pass

if TESSERACT_AVAILABLE:
    try:
        import pytesseract
    except ImportError:
        TESSERACT_AVAILABLE = False

if not TESSERACT_AVAILABLE:
    logger.info(
        "Tesseract OCR not available. Scanned PDFs will produce empty text. "
        "Install with: sudo apt-get install tesseract-ocr"
    )


@dataclass
class ExtractionResult:
    """Result of text extraction from a PDF."""

    text: str
    pages: list[PageResult] = field(default_factory=list)
    pdf_type: PDFType = PDFType.SCANNED
    method: str = ""  # pdftotext, pdfminer, tesseract
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.text.strip())


@dataclass
class PageResult:
    """Extraction result for a single page."""

    page_num: int
    text: str
    method: str
    confidence: float = 0.0  # OCR confidence if available


class PDFExtractor:
    """Extracts text from PDFs using the best available method."""

    def __init__(self, classifier: PDFClassifier | None = None):
        self.classifier = classifier or PDFClassifier()

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        """Extract text from a PDF file.

        Automatically classifies and routes to the best extraction method.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        pdf_type = self.classifier.classify(pdf_path)
        logger.info("PDF %s classified as %s", pdf_path.name, pdf_type.value)

        if pdf_type == PDFType.EMPTY:
            return ExtractionResult(
                text="", pdf_type=pdf_type, method="none",
                warnings=["PDF appears empty (no pages)"],
            )

        if pdf_type in (PDFType.TEXT_SEARCHABLE, PDFType.MIXED):
            result = self._extract_text_layer(pdf_path)
            result.pdf_type = pdf_type
            if result.success:
                return result
            # Fall through to OCR if text extraction produced nothing useful
            logger.info("Text extraction produced no content, falling back to OCR")

        # Scanned or text extraction failed
        return self._extract_ocr(pdf_path, pdf_type)

    def extract_bytes(self, pdf_bytes: bytes, filename: str = "input.pdf") -> ExtractionResult:
        """Extract text from PDF bytes (e.g., from MinIO object store)."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            result = self.extract(tmp.name)
        return result

    def _extract_text_layer(self, pdf_path: Path) -> ExtractionResult:
        """Extract embedded text layer using pdftotext or pdfminer."""
        # Try pdftotext first (faster, better layout preservation)
        if PDFTOTEXT_AVAILABLE:
            try:
                result = self._extract_pdftotext(pdf_path)
                if result.success:
                    return result
            except Exception as e:
                logger.debug("pdftotext failed: %s, trying pdfminer", e)

        # Fallback to pdfminer.six
        return self._extract_pdfminer(pdf_path)

    def _extract_pdftotext(self, pdf_path: Path) -> ExtractionResult:
        """Use poppler's pdftotext for extraction."""
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                page_count = self.classifier.get_page_count(pdf_path)
                return ExtractionResult(
                    text=proc.stdout,
                    pdf_type=PDFType.TEXT_SEARCHABLE,
                    method="pdftotext",
                    page_count=page_count,
                )
        except subprocess.TimeoutExpired:
            logger.warning("pdftotext timed out on %s", pdf_path)

        return ExtractionResult(text="", method="pdftotext", warnings=["pdftotext produced no output"])

    def _extract_pdfminer(self, pdf_path: Path) -> ExtractionResult:
        """Use pdfminer.six for extraction (handles more complex PDFs)."""
        laparams = LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5,
        )
        try:
            text = pdfminer_extract(str(pdf_path), laparams=laparams)
            page_count = self.classifier.get_page_count(pdf_path)
            return ExtractionResult(
                text=text,
                pdf_type=PDFType.TEXT_SEARCHABLE,
                method="pdfminer",
                page_count=page_count,
            )
        except Exception as e:
            logger.error("pdfminer extraction failed: %s", e)
            return ExtractionResult(
                text="", method="pdfminer",
                warnings=[f"pdfminer failed: {e}"],
            )

    def _extract_ocr(self, pdf_path: Path, pdf_type: PDFType) -> ExtractionResult:
        """Run Tesseract OCR on scanned pages."""
        if not TESSERACT_AVAILABLE or not PDF2IMAGE_AVAILABLE:
            missing = []
            if not TESSERACT_AVAILABLE:
                missing.append("tesseract-ocr")
            if not PDF2IMAGE_AVAILABLE:
                missing.append("pdf2image + poppler-utils")
            warning = (
                f"OCR unavailable (missing: {', '.join(missing)}). "
                f"Install: sudo apt-get install tesseract-ocr poppler-utils && pip install pdf2image pytesseract"
            )
            logger.warning(warning)
            return ExtractionResult(
                text="", pdf_type=pdf_type, method="none",
                warnings=[warning],
            )

        return self._run_tesseract(pdf_path, pdf_type)

    def _run_tesseract(self, pdf_path: Path, pdf_type: PDFType) -> ExtractionResult:
        """Convert PDF pages to images and OCR with Tesseract."""
        import pytesseract as tess

        pages_text = []
        page_results = []
        warnings = []

        try:
            images = convert_from_path(str(pdf_path), dpi=300)
        except Exception as e:
            return ExtractionResult(
                text="", pdf_type=pdf_type, method="tesseract",
                warnings=[f"PDF to image conversion failed: {e}"],
            )

        for i, img in enumerate(images):
            try:
                # Get text with confidence data
                data = tess.image_to_data(img, output_type=tess.Output.DICT)
                page_text = tess.image_to_string(img)

                # Calculate average confidence for non-empty words
                confidences = [
                    int(c) for c, t in zip(data["conf"], data["text"])
                    if str(c) != "-1" and t.strip()
                ]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

                page_results.append(PageResult(
                    page_num=i + 1,
                    text=page_text,
                    method="tesseract",
                    confidence=avg_conf / 100.0,
                ))
                pages_text.append(page_text)

            except Exception as e:
                warnings.append(f"OCR failed on page {i + 1}: {e}")
                logger.warning("Tesseract failed on page %d of %s: %s", i + 1, pdf_path, e)

        full_text = "\n\n".join(pages_text)
        return ExtractionResult(
            text=full_text,
            pages=page_results,
            pdf_type=pdf_type,
            method="tesseract",
            page_count=len(images),
            warnings=warnings,
        )
