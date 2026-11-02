"""OCR post-correction service for Egyptological texts.

Pipeline: raw OCR text -> rule-based cleanup -> model-based correction -> confidence scoring.

Handles the main OCR failure modes for Egyptological content:
1. Transliteration diacritics: h-underdot misread as h, etc.
2. Gardiner code garbling: sign names corrupted
3. Mixed-script segmentation: transliteration vs modern language text incorrectly merged
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .translit_models import TranslitModel, TranslitModelLoader

# Single Gardiner code pattern (used as label, not as text to transliterate)
_GARDINER_SINGLE_CODE = re.compile(r"^[A-Z][a-z]?\d{1,3}[A-Za-z]?$")

logger = logging.getLogger(__name__)


@dataclass
class WordCorrection:
    """Correction applied to a single word."""

    original: str
    corrected: str
    stage: str  # "rule_based" or "model_based"
    confidence: float  # 0.0-1.0
    rule_applied: str = ""  # Which rule or model was used


@dataclass
class CorrectionResult:
    """Result of post-correction on a text."""

    original_text: str
    corrected_text: str
    corrections: list[WordCorrection] = field(default_factory=list)
    overall_confidence: float = 0.0
    stages_applied: list[str] = field(default_factory=list)

    @property
    def correction_count(self) -> int:
        return len(self.corrections)

    @property
    def changed(self) -> bool:
        return self.original_text != self.corrected_text


# Common OCR misrecognition patterns for Egyptological transliteration
# Format: (compiled_regex, replacement, rule_name)
RULE_BASED_CORRECTIONS: list[tuple[re.Pattern, str, str]] = [
    # h-underdot misrecognition: plain h where ḥ is expected
    # Only in contexts that look like transliteration
    (re.compile(r"\bHtp\b"), "Ḥtp", "h_underdot_htp"),
    (re.compile(r"\bHm\b"), "Ḥm", "h_underdot_hm"),
    (re.compile(r"\bHr\b"), "Ḥr", "h_underdot_hr"),

    # Common Gardiner code garbling patterns
    # OCR often reads 'l' as '1', 'O' as '0', etc.
    (re.compile(r"\b([A-Z])l(\d)"), r"\g<1>1\2", "gardiner_l_to_1"),
    (re.compile(r"\b([A-Z])O(\d)"), r"\g<1>0\2", "gardiner_O_to_0"),

    # MdC transliteration character confusions
    # S (shin) vs s (samekh) - OCR often loses the distinction
    # Only flag these, don't auto-correct (ambiguous)

    # Stray OCR artifacts in transliteration context
    (re.compile(r"(?<=\w)[|l](?=\w)"), "", "ocr_artifact_pipe"),

    # Common Unicode normalization issues
    (re.compile(r"ḥ̣"), "ḥ", "double_underdot"),  # Double underdot artifact
    (re.compile(r"s̆"), "š", "s_caron_normalize"),  # Decomposed š

    # Whitespace normalization in transliteration
    (re.compile(r"\s*=\s*"), "=", "normalize_enclitic"),  # n =f -> n=f
    (re.compile(r"\s*\.\s*"), ".", "normalize_dot"),  # n . t -> n.t (within words)
]

# Common MdC transliteration word patterns (for identifying transliteration text)
_MDC_TRANSLIT_WORDS = re.compile(
    r"^(?:jw|jr|jn|nfr|wn|nb|Hm|Htp|nTr|nsw|bjt|mAat|anx|wAs|Dd)$",
    re.IGNORECASE,
)

# Patterns that indicate transliteration context (vs modern language)
TRANSLIT_CONTEXT_PATTERNS = [
    re.compile(r"[ꜣꜥḥḫẖšṯḏ]"),  # Transliteration-specific chars
    re.compile(r"\b(?:jw|jr|jn|nfr|wn|nb|nTr|nsw|bjt|anx|wAs|Dd)\b"),  # MdC words
    re.compile(r"\b[a-z][.=-][a-z]"),  # Dotted/hyphenated letter sequences
]

# Patterns that indicate modern language context
MODERN_CONTEXT_PATTERNS = [
    re.compile(r"\b(?:the|and|of|is|was|that|for|with|this|from)\b", re.IGNORECASE),
    re.compile(r"\b(?:der|die|das|und|von|ist|mit|des|dem|den)\b", re.IGNORECASE),
    re.compile(r"\b(?:le|la|les|de|du|des|et|un|une|dans|pour)\b", re.IGNORECASE),
]


class CorrectionService:
    """Full OCR post-correction pipeline.

    Usage:
        service = CorrectionService()
        result = service.correct("raw OCR text here")
        print(result.corrected_text)
        print(result.corrections)  # What was changed
    """

    def __init__(self, model: TranslitModel | None = None, auto_load_model: bool = True):
        self.model = model
        self._model_loaded = model is not None

        if auto_load_model and model is None:
            self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load the combined TranslitModels model."""
        try:
            loader = TranslitModelLoader()
            self.model = loader.load_combined()
            self._model_loaded = True
            logger.info("Loaded TranslitModels for post-correction")
        except FileNotFoundError:
            logger.info("TranslitModels not available, using rule-based corrections only")
        except Exception as e:
            logger.warning("Failed to load TranslitModels: %s", e)

    def correct(self, text: str) -> CorrectionResult:
        """Run the full correction pipeline on OCR text.

        Pipeline:
        1. Segment text into transliteration vs modern language regions
        2. Apply rule-based corrections to transliteration regions
        3. Apply model-based correction (if available)
        4. Score confidence
        """
        if not text.strip():
            return CorrectionResult(
                original_text=text,
                corrected_text=text,
                overall_confidence=1.0,
            )

        all_corrections = []
        stages = []

        # Stage 1: Segment into regions
        regions = self._segment_text(text)

        # Stage 2: Rule-based corrections on transliteration regions
        corrected_regions = []
        for region_text, is_translit in regions:
            if is_translit:
                corrected, corrections = self._apply_rule_corrections(region_text)
                all_corrections.extend(corrections)
                corrected_regions.append(corrected)
            else:
                corrected_regions.append(region_text)

        if all_corrections:
            stages.append("rule_based")

        corrected_text = "".join(corrected_regions)

        # Stage 3: Model-based correction
        if self._model_loaded and self.model:
            model_corrected, model_corrections = self._apply_model_corrections(corrected_text)
            if model_corrections:
                corrected_text = model_corrected
                all_corrections.extend(model_corrections)
                stages.append("model_based")

        # Stage 4: Confidence scoring
        confidence = self._score_confidence(text, corrected_text, all_corrections)

        return CorrectionResult(
            original_text=text,
            corrected_text=corrected_text,
            corrections=all_corrections,
            overall_confidence=confidence,
            stages_applied=stages,
        )

    def _segment_text(self, text: str) -> list[tuple[str, bool]]:
        """Segment text into transliteration and modern-language regions.

        Returns list of (text, is_transliteration) tuples.
        """
        lines = text.split("\n")
        regions = []
        current_lines = []
        current_is_translit = None

        for line in lines:
            is_translit = self._is_transliteration(line)

            if current_is_translit is None:
                current_is_translit = is_translit

            if is_translit == current_is_translit:
                current_lines.append(line)
            else:
                if current_lines:
                    regions.append(("\n".join(current_lines), current_is_translit))
                current_lines = [line]
                current_is_translit = is_translit

        if current_lines:
            regions.append(("\n".join(current_lines), current_is_translit or False))

        return regions

    def _is_transliteration(self, text: str) -> bool:
        """Heuristic: is this text likely transliteration?"""
        if not text.strip():
            return False

        translit_score = sum(
            1 for p in TRANSLIT_CONTEXT_PATTERNS if p.search(text)
        )
        modern_score = sum(
            1 for p in MODERN_CONTEXT_PATTERNS if p.search(text)
        )

        return translit_score > modern_score

    def _apply_rule_corrections(self, text: str) -> tuple[str, list[WordCorrection]]:
        """Apply rule-based corrections to transliteration text."""
        corrections = []
        corrected = text

        for pattern, replacement, rule_name in RULE_BASED_CORRECTIONS:
            matches = list(pattern.finditer(corrected))
            if matches:
                for match in matches:
                    original_word = match.group()
                    new_text = pattern.sub(replacement, original_word)
                    if original_word != new_text:
                        corrections.append(WordCorrection(
                            original=original_word,
                            corrected=new_text,
                            stage="rule_based",
                            confidence=0.7,
                            rule_applied=rule_name,
                        ))
                corrected = pattern.sub(replacement, corrected)

        return corrected, corrections

    def _apply_model_corrections(self, text: str) -> tuple[str, list[WordCorrection]]:
        """Apply TranslitModels-based corrections.

        Uses the model to validate transliteration words. If a word appears
        in the model as an MdC encoding AND the word looks like an MdC code
        (not already a transliteration), suggest the most likely transliteration.

        We are conservative: only correct words that are clearly MdC encodings
        appearing in a transliteration context (not Gardiner code references
        in commentary).
        """
        if not self.model:
            return text, []

        corrections = []
        words = text.split()
        corrected_words = []

        for word in words:
            # Skip words that are already valid transliteration
            # (contain transliteration-specific chars or common translit patterns)
            if self._is_translit_word(word):
                corrected_words.append(word)
                continue

            # Skip words that look like Gardiner code references in commentary
            # (single sign codes like A1, D36 used as labels, not as text to transliterate)
            if _GARDINER_SINGLE_CODE.match(word):
                corrected_words.append(word)
                continue

            # Only consider multi-sign MdC sequences for correction
            # These are sequences of Gardiner codes that represent actual words
            if " " not in word:
                corrected_words.append(word)
                continue

            entry = self.model.lookup(word)
            if entry and entry.best_transliteration:
                best = entry.best_transliteration
                if best != word:
                    top_interp = max(entry.interpretations, key=lambda i: i.freq)
                    # Only correct with high confidence
                    if top_interp.rel_freq >= 70.0:
                        corrections.append(WordCorrection(
                            original=word,
                            corrected=best,
                            stage="model_based",
                            confidence=top_interp.rel_freq / 100.0,
                            rule_applied=f"translit_model:{self.model.name}",
                        ))
                        corrected_words.append(best)
                        continue

            corrected_words.append(word)

        return " ".join(corrected_words), corrections

    @staticmethod
    def _is_translit_word(word: str) -> bool:
        """Check if a word is already a transliteration (not an MdC encoding)."""
        # Contains transliteration-specific Unicode chars
        if any(c in word for c in "ꜣꜥḥḫẖšṯḏ"):
            return True
        # Contains dots, equals, or hyphens typical of transliteration
        if re.match(r"^[a-zA-Z][.=-]", word):
            return True
        # Looks like a common transliteration word
        if _MDC_TRANSLIT_WORDS.match(word):
            return True
        return False

    def _score_confidence(
        self,
        original: str,
        corrected: str,
        corrections: list[WordCorrection],
    ) -> float:
        """Score overall confidence in the corrected text.

        Higher confidence means:
        - Fewer corrections needed (text was already good)
        - Corrections applied with high individual confidence
        - Text matches known transliteration patterns
        """
        if not corrections:
            # No corrections needed -- could mean good OCR or unknown content
            return 0.8 if self._has_translit_markers(corrected) else 0.5

        # Weight by individual correction confidences
        avg_correction_conf = (
            sum(c.confidence for c in corrections) / len(corrections)
        )

        # Penalize heavy correction (lots of changes = low trust)
        word_count = max(len(original.split()), 1)
        correction_ratio = len(corrections) / word_count
        density_penalty = max(0, 1.0 - correction_ratio * 2)

        return min(avg_correction_conf * density_penalty, 1.0)

    def _has_translit_markers(self, text: str) -> bool:
        """Check if text contains transliteration markers."""
        return any(p.search(text) for p in TRANSLIT_CONTEXT_PATTERNS)
