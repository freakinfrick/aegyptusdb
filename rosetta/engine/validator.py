"""Rosetta Validator — validate translations against witness evidence."""

from __future__ import annotations

import re
import logging
from typing import Optional

from rosetta.witness.dossier import WitnessDossier

logger = logging.getLogger(__name__)


class RosettaValidator:
    """Validate Rosetta translations against witness evidence."""

    ENGLISH_STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "of", "in", "to", "for",
        "with", "on", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "both", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "and", "but", "or", "if", "while", "that", "this",
        "these", "those", "it", "its", "he", "she", "his", "her", "him",
        "they", "them", "their", "who", "whom", "which", "what", "i", "my",
        "me", "we", "our", "us", "you", "your",
    })

    def validate(
        self, result, dossier: WitnessDossier
    ) -> tuple[bool, str, str]:
        """Validate translation against witness evidence.

        Returns (is_valid, reason, adjusted_confidence).
        """
        translation = (result.translation_en or "").strip()
        confidence = (result.confidence_llm or "LOW").upper()

        if not translation:
            return False, "empty translation", "LOW"

        # --- 1. Length check ---
        token_count = len(dossier.tokens) if dossier.tokens else 1
        if len(translation) < 2 * token_count and token_count > 2:
            return False, f"too short ({len(translation)} chars for {token_count} tokens)", "LOW"
        if len(translation) > 200 * token_count:
            return False, f"too long ({len(translation)} chars for {token_count} tokens)", "LOW"

        # --- 2. Echo detection ---
        if dossier.transliteration and translation.lower() == dossier.transliteration.lower():
            return False, "echoed transliteration", "LOW"
        if dossier.german_translation and translation.strip() == dossier.german_translation.strip():
            return False, "echoed german translation verbatim", "LOW"

        # --- 3. Formatting artifact check ---
        stripped = re.sub(r"[#*\-=\s]", "", translation)
        if len(stripped) < 2:
            return False, "only formatting artifacts", "LOW"

        # --- 4. Hallucination check: proper nouns ---
        words = translation.split()
        proper_nouns: set[str] = set()
        for i, w in enumerate(words):
            clean = re.sub(r"[^\w]", "", w)
            if not clean:
                continue
            # Skip sentence-start words and all-caps words (likely abbreviations)
            if i == 0:
                continue
            if clean[0].isupper() and not clean.isupper() and len(clean) > 1:
                proper_nouns.add(clean.lower())

        if proper_nouns:
            # Check if proper nouns appear in any witness
            witness_text = self._collect_witness_text(dossier).lower()
            unattested = {pn for pn in proper_nouns if pn not in witness_text}
            if unattested and len(unattested) > len(proper_nouns) * 0.5:
                return (
                    False,
                    f"hallucinated proper nouns: {', '.join(sorted(unattested))}",
                    "LOW",
                )

        # --- 5. Confidence calibration ---
        coverage = dossier.token_coverage

        if confidence == "HIGH":
            if coverage < 0.5:
                confidence = "MEDIUM"
            elif not dossier.has_german and not dossier.parallel_examples:
                confidence = "MEDIUM"
        elif confidence == "MEDIUM":
            if coverage < 0.3:
                confidence = "LOW"

        return True, "ok", confidence

    def _collect_witness_text(self, dossier: WitnessDossier) -> str:
        """Collect all text from witnesses for hallucination checking."""
        parts: list[str] = []

        if dossier.transliteration:
            parts.append(dossier.transliteration)
        if dossier.german_translation:
            parts.append(dossier.german_translation)
        if dossier.german_interlinear:
            parts.append(dossier.german_interlinear)

        for tw in dossier.token_witnesses:
            if tw.en_gloss:
                parts.append(tw.en_gloss)
            if tw.de_gloss:
                parts.append(tw.de_gloss)
            if tw.form:
                parts.append(tw.form)

        for px in dossier.parallel_examples:
            if px.translation_en:
                parts.append(px.translation_en)
            if px.translation_de:
                parts.append(px.translation_de)
            if px.transliteration:
                parts.append(px.transliteration)

        return " ".join(parts)
