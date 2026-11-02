"""End-to-end PDF OCR pipeline.

Takes a PDF (file path or bytes from MinIO) and produces StagingRecords
ready for the entity resolution merge pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .classifier import PDFClassifier, PDFType
from .extractor import PDFExtractor, ExtractionResult
from .structure import BlockClassifier, BlockType, TextBlock

logger = logging.getLogger(__name__)


@dataclass
class PDFProcessingResult:
    """Complete result of processing a PDF through the OCR pipeline."""

    source_url: str
    source_filename: str
    extraction: ExtractionResult
    blocks: list[TextBlock]
    staging_records: list[dict]  # Dicts matching StagingRecord fields
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.extraction.success and len(self.staging_records) > 0


class OCRPipeline:
    """Full PDF processing pipeline: classify -> extract -> structure -> stage.

    Usage:
        pipeline = OCRPipeline()
        result = pipeline.process_file("/path/to/pdf")
        for record in result.staging_records:
            merger.process_record(StagingRecord(**record))
    """

    def __init__(
        self,
        classifier: PDFClassifier | None = None,
        extractor: PDFExtractor | None = None,
        block_classifier: BlockClassifier | None = None,
    ):
        self.classifier = classifier or PDFClassifier()
        self.extractor = extractor or PDFExtractor(self.classifier)
        self.block_classifier = block_classifier or BlockClassifier()

    def process_file(
        self,
        pdf_path: str | Path,
        source_url: str = "",
        title_hint: str | None = None,
        shelfmark_hint: str | None = None,
    ) -> PDFProcessingResult:
        """Process a PDF through the full classify → extract → structure → ingest pipeline."""
        pdf_path = Path(pdf_path)
        logger.info("Processing PDF: %s", pdf_path.name)

        # Step 1+2: Classify and extract
        extraction = self.extractor.extract(pdf_path)
        if not extraction.success:
            return PDFProcessingResult(
                source_url=source_url,
                source_filename=pdf_path.name,
                extraction=extraction,
                blocks=[],
                staging_records=[],
                warnings=extraction.warnings + ["No text extracted from PDF"],
            )

        # Step 3: Structure extraction — classify text blocks
        if extraction.pages:
            page_texts = [p.text for p in extraction.pages]
            blocks = self.block_classifier.classify_full_document(
                extraction.text, page_texts=page_texts,
            )
        else:
            blocks = self.block_classifier.classify_text(extraction.text)

        # Step 4: Build staging records from classified blocks
        staging_records = self._build_staging_records(
            blocks=blocks,
            source_url=source_url,
            filename=pdf_path.name,
            extraction=extraction,
            title_hint=title_hint,
            shelfmark_hint=shelfmark_hint,
        )

        warnings = list(extraction.warnings)
        if not staging_records:
            warnings.append("No meaningful content blocks identified")

        return PDFProcessingResult(
            source_url=source_url,
            source_filename=pdf_path.name,
            extraction=extraction,
            blocks=blocks,
            staging_records=staging_records,
            warnings=warnings,
        )

    def process_bytes(
        self,
        pdf_bytes: bytes,
        source_url: str = "",
        filename: str = "input.pdf",
        title_hint: str | None = None,
        shelfmark_hint: str | None = None,
    ) -> PDFProcessingResult:
        """Process PDF bytes (e.g., from MinIO) through the pipeline."""
        extraction = self.extractor.extract_bytes(pdf_bytes, filename)
        if not extraction.success:
            return PDFProcessingResult(
                source_url=source_url,
                source_filename=filename,
                extraction=extraction,
                blocks=[],
                staging_records=[],
                warnings=extraction.warnings + ["No text extracted from PDF bytes"],
            )

        blocks = self.block_classifier.classify_text(extraction.text)

        staging_records = self._build_staging_records(
            blocks=blocks,
            source_url=source_url,
            filename=filename,
            extraction=extraction,
            title_hint=title_hint,
            shelfmark_hint=shelfmark_hint,
        )

        return PDFProcessingResult(
            source_url=source_url,
            source_filename=filename,
            extraction=extraction,
            blocks=blocks,
            staging_records=staging_records,
            warnings=extraction.warnings,
        )

    def _build_staging_records(
        self,
        blocks: list[TextBlock],
        source_url: str,
        filename: str,
        extraction: ExtractionResult,
        title_hint: str | None = None,
        shelfmark_hint: str | None = None,
    ) -> list[dict]:
        """Convert classified text blocks into staging record dicts.

        Groups blocks by type and creates one StagingRecord per content type
        (transliteration, translation, etc.). This avoids creating dozens
        of tiny records for each paragraph.
        """
        # Group blocks by type
        grouped: dict[BlockType, list[TextBlock]] = {}
        for block in blocks:
            if block.block_type in (BlockType.UNKNOWN, BlockType.BIBLIOGRAPHY):
                continue  # Skip non-content blocks
            grouped.setdefault(block.block_type, []).append(block)

        records = []
        title = title_hint or self._extract_title(extraction.text, filename)

        for block_type, type_blocks in grouped.items():
            # Merge all blocks of the same type into one record
            combined_text = "\n\n".join(b.text for b in type_blocks)
            if len(combined_text.strip()) < 20:
                continue  # Skip trivially short content

            avg_confidence = (
                sum(b.confidence for b in type_blocks) / len(type_blocks)
                if type_blocks else 0.0
            )

            content_type = self._block_type_to_content_type(block_type)
            language = self._detect_language(block_type, combined_text)

            record = {
                "title": title,
                "shelfmark": shelfmark_hint,
                "text_content": combined_text,
                "transliteration": combined_text if block_type == BlockType.TRANSLITERATION else None,
                "language": language,
                "content_type": content_type,
                "source": "pdf_ocr",
                "source_url": source_url,
                "source_attribution": f"Extracted from {filename} via {extraction.method}",
                "extra_metadata": {
                    "pdf_type": extraction.pdf_type.value,
                    "extraction_method": extraction.method,
                    "block_count": len(type_blocks),
                    "avg_confidence": round(avg_confidence, 3),
                    "page_count": extraction.page_count,
                },
            }
            records.append(record)

        return records

    def _extract_title(self, text: str, filename: str) -> str:
        """Try to extract a title from the first lines of text."""
        lines = text.strip().split("\n")
        for line in lines[:10]:
            line = line.strip()
            # Skip empty lines and very short lines
            if len(line) < 5:
                continue
            # Skip lines that look like page numbers or headers
            if re.match(r"^\d+$", line):
                continue
            # First substantial line is likely the title
            if len(line) < 200:
                return line

        # Fallback to filename
        return Path(filename).stem.replace("_", " ").replace("-", " ")

    def _block_type_to_content_type(self, block_type: BlockType) -> str:
        """Map BlockType to the content_type string used by StagingRecord."""
        mapping = {
            BlockType.HIEROGLYPHIC: "hieroglyphic",
            BlockType.TRANSLITERATION: "transliteration",
            BlockType.TRANSLATION: "translation",
            BlockType.COMMENTARY: "commentary",
            BlockType.FOOTNOTE: "commentary",
        }
        return mapping.get(block_type, "mixed")

    def _detect_language(self, block_type: BlockType, text: str) -> str | None:
        """Detect language based on block type and content."""
        if block_type == BlockType.HIEROGLYPHIC:
            return "egy"  # Ancient Egyptian
        if block_type == BlockType.TRANSLITERATION:
            return "egy-Latn"  # Egyptian in Latin script transliteration

        # For translations and commentary, try langdetect
        try:
            from langdetect import detect
            if len(text) > 50:
                return detect(text)
        except Exception:
            pass

        return None
