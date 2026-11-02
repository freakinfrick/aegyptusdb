"""Text block structure classification using font/layout heuristics.

Identifies extracted text blocks as:
- Hieroglyphic transcription (MdC or Unicode hieroglyphs)
- Transliteration (Leiden conventions, MdC transliteration characters)
- Translation (modern language text)
- Commentary/footnotes
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BlockType(Enum):
    HIEROGLYPHIC = "hieroglyphic"
    TRANSLITERATION = "transliteration"
    TRANSLATION = "translation"
    COMMENTARY = "commentary"
    FOOTNOTE = "footnote"
    BIBLIOGRAPHY = "bibliography"
    UNKNOWN = "unknown"


@dataclass
class TextBlock:
    """A classified block of text from a PDF."""

    text: str
    block_type: BlockType
    confidence: float  # 0.0-1.0
    page_num: int = 0
    line_start: int = 0
    line_end: int = 0
    metadata: dict = field(default_factory=dict)


# Unicode ranges for Egyptian hieroglyphs
# U+13000-U+1342F: Egyptian Hieroglyphs
# U+13430-U+1345F: Egyptian Hieroglyph Format Controls
HIEROGLYPH_RANGE = re.compile(r"[\U00013000-\U0001345F]")

# Manuel de Codage patterns: Gardiner sign codes like A1, B2, D36, etc.
GARDINER_PATTERN = re.compile(
    r"\b[A-Z][a-z]?\d{1,3}[A-Za-z]?\b"
)

# Transliteration characters: special diacritics used in Egyptological transliteration
# Includes: ꜣ ꜥ ḥ ḫ ẖ š ṯ ḏ plus common MdC equivalents
TRANSLIT_CHARS = re.compile(
    r"[ꜣꜥḥḫẖšṯḏȜȝŠṯḤḪẖḎ]"
    r"|"
    # MdC-style transliteration: sequences of a A i y w b p f m n r h H x X s S q k g t T d D
    # with dots and hyphens typical of transliteration
    r"\b[aAiywbpfmnrhHxXsSqkgtTdD][.=-][aAiywbpfmnrhHxXsSqkgtTdD]"
)

# Common MdC transliteration word patterns
MDC_TRANSLIT_PATTERN = re.compile(
    r"\b(?:jw|jr|jn|nfr|wn|nb|Hm|Htp|nTr|nsw|bjt|mAat|anx|wAs|Dd)\b",
    re.IGNORECASE,
)

# Footnote indicators
FOOTNOTE_PATTERN = re.compile(
    r"^\s*(?:\d+[\.\)]\s|[\*†‡§]\s|\[\d+\])",
    re.MULTILINE,
)

# Bibliography patterns
BIBLIOGRAPHY_PATTERN = re.compile(
    r"(?:(?:ibid|op\.?\s*cit|loc\.?\s*cit|et\s+al|eds?\.|vol\.|pp?\.\s*\d)|"
    r"(?:\(\d{4}[a-z]?\))|"
    r"(?:Journal|Zeitschrift|Revue|Proceedings|Annales))",
    re.IGNORECASE,
)


class BlockClassifier:
    """Classifies text blocks by content type using heuristics."""

    def __init__(self):
        # Thresholds for classification
        self.min_hieroglyph_ratio = 0.1  # 10% hieroglyphic chars
        self.min_translit_score = 3  # Minimum transliteration signals
        self.min_footnote_ratio = 0.3  # 30% of lines look like footnotes

    def classify_text(self, text: str, page_num: int = 0) -> list[TextBlock]:
        """Split text into blocks and classify each.

        For now, splits on double-newlines and classifies each paragraph.
        More sophisticated layout analysis would use PDF coordinates.
        """
        if not text.strip():
            return []

        blocks = []
        paragraphs = re.split(r"\n\s*\n", text)

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            block_type, confidence = self._classify_paragraph(para)
            blocks.append(TextBlock(
                text=para,
                block_type=block_type,
                confidence=confidence,
                page_num=page_num,
                line_start=i,  # Approximate
            ))

        return blocks

    def classify_full_document(self, text: str, page_texts: list[str] | None = None) -> list[TextBlock]:
        """Classify all text in a document.

        If page_texts is provided, processes page by page for better
        page number tracking.
        """
        if page_texts:
            all_blocks = []
            for page_num, page_text in enumerate(page_texts, 1):
                blocks = self.classify_text(page_text, page_num=page_num)
                all_blocks.extend(blocks)
            return all_blocks

        return self.classify_text(text)

    def _classify_paragraph(self, text: str) -> tuple[BlockType, float]:
        """Classify a single paragraph.

        Returns (BlockType, confidence) tuple.
        """
        if not text.strip():
            return BlockType.UNKNOWN, 0.0

        scores = {
            BlockType.HIEROGLYPHIC: self._score_hieroglyphic(text),
            BlockType.TRANSLITERATION: self._score_transliteration(text),
            BlockType.FOOTNOTE: self._score_footnote(text),
            BlockType.BIBLIOGRAPHY: self._score_bibliography(text),
            BlockType.TRANSLATION: self._score_translation(text),
            BlockType.COMMENTARY: self._score_commentary(text),
        }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score < 0.1:
            return BlockType.UNKNOWN, 0.0

        # Normalize to 0-1 confidence
        confidence = min(best_score, 1.0)
        return best_type, confidence

    def _score_hieroglyphic(self, text: str) -> float:
        """Score likelihood of hieroglyphic content."""
        if not text:
            return 0.0

        # Check for Unicode hieroglyphs
        hieroglyph_chars = len(HIEROGLYPH_RANGE.findall(text))
        if hieroglyph_chars > 0:
            ratio = hieroglyph_chars / len(text)
            if ratio >= self.min_hieroglyph_ratio:
                return 0.9

        # Check for dense Gardiner codes (MdC notation)
        gardiner_matches = GARDINER_PATTERN.findall(text)
        words = text.split()
        if words and len(gardiner_matches) / max(len(words), 1) > 0.3:
            return 0.7

        return 0.0

    def _score_transliteration(self, text: str) -> float:
        """Score likelihood of transliteration content."""
        score = 0.0

        # Check for transliteration-specific characters
        translit_chars = len(TRANSLIT_CHARS.findall(text))
        if translit_chars > 0:
            score += min(translit_chars / 5, 0.4)

        # Check for MdC transliteration patterns
        mdc_matches = len(MDC_TRANSLIT_PATTERN.findall(text))
        if mdc_matches > 0:
            score += min(mdc_matches / 3, 0.4)

        # Check for transliteration formatting: lots of hyphens, dots, equals signs
        # between single characters (e.g., "j-n-k n.t r=f")
        translit_format = len(re.findall(r"[a-zA-Z][.=-][a-zA-Z]", text))
        words = text.split()
        if words and translit_format / max(len(words), 1) > 0.2:
            score += 0.3

        return min(score, 1.0)

    def _score_footnote(self, text: str) -> float:
        """Score likelihood of footnote content."""
        lines = text.strip().split("\n")
        if not lines:
            return 0.0

        footnote_lines = sum(1 for line in lines if FOOTNOTE_PATTERN.match(line))
        ratio = footnote_lines / len(lines)

        if ratio >= self.min_footnote_ratio:
            return 0.7 + (ratio * 0.3)

        # Small font size hint: lines are very short
        avg_len = sum(len(line) for line in lines) / len(lines)
        if avg_len < 40 and footnote_lines > 0:
            return 0.5

        return ratio * 0.4

    def _score_bibliography(self, text: str) -> float:
        """Score likelihood of bibliography content."""
        bib_matches = len(BIBLIOGRAPHY_PATTERN.findall(text))
        if bib_matches == 0:
            return 0.0

        words = text.split()
        density = bib_matches / max(len(words), 1)
        return min(0.3 + density * 5, 1.0)

    def _score_translation(self, text: str) -> float:
        """Score likelihood of modern-language translation content.

        Translations are "normal" prose in a modern language. We score this
        as a default when nothing else matches strongly.
        """
        if not text.strip():
            return 0.0

        # If it looks like mostly normal prose (high ratio of common words)
        words = text.split()
        if len(words) < 3:
            return 0.1

        # Check for sentence structure: capitalization, punctuation
        sentences = re.split(r"[.!?]+", text)
        if len(sentences) >= 1 and any(len(s.split()) > 4 for s in sentences):
            score = 0.4

            # Boost if no transliteration or hieroglyphic signals
            if self._score_transliteration(text) < 0.2 and self._score_hieroglyphic(text) < 0.1:
                score += 0.2

            # Check for translation markers
            if re.search(r"(?:translated?|version|rendering)", text, re.IGNORECASE):
                score += 0.1

            return min(score, 0.8)

        return 0.2

    def _score_commentary(self, text: str) -> float:
        """Score likelihood of scholarly commentary."""
        score = 0.0

        # Commentary often references other texts, uses parenthetical citations
        if re.search(r"\((?:cf\.|see|compare|note)\s", text, re.IGNORECASE):
            score += 0.3

        # Mix of transliteration terms within modern prose
        translit_score = self._score_transliteration(text)
        translation_score = self._score_translation(text)
        if 0.1 < translit_score < 0.5 and translation_score > 0.2:
            score += 0.3

        # Section numbering common in commentary
        if re.match(r"^\s*(?:§\s*\d|[IVX]+\.\s|\d+\.\d+)", text):
            score += 0.2

        return min(score, 0.8)
