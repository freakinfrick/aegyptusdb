"""PDF classification, text extraction, and OCR pipeline.

Handles both text-searchable PDFs (direct extraction) and scanned PDFs (Tesseract OCR).
Produces structured records ready for entity resolution.
"""

from .classifier import PDFClassifier, PDFType
from .extractor import PDFExtractor, ExtractionResult
from .structure import BlockClassifier, TextBlock, BlockType
from .pipeline import OCRPipeline

__all__ = [
    "PDFClassifier",
    "PDFType",
    "PDFExtractor",
    "ExtractionResult",
    "BlockClassifier",
    "TextBlock",
    "BlockType",
    "OCRPipeline",
]
