"""Mechanical translator — CPU-only, no LLM, dictionary-based translation.

Translates sentences that have word-level German glosses (AED-TEI, ORAEC, AES)
by mapping each token's German gloss through a corpus-derived DE→EN bridge
dictionary built from the Thoth Lexicon.

Coverage: 99.7% of AED-TEI tokens, 119K+ sentences.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Editorial/damage markers → English equivalents
_EDITORIAL_MAP = {
    "[Zerstörung]": "[destroyed]",
    "[zerstört]": "[destroyed]",
    "[teilzerstört]": "[partially destroyed]",
    "[teilzerstörtes Wort]": "[partially destroyed word]",
    "(Hieroglyphenspuren)[Zerstörung]": "[traces of hieroglyphs, destroyed]",
    "[nicht zuweisbar]": "[unassignable]",
    "[nicht rekonstruierbar]": "[not reconstructable]",
    "[Bestandteil eines PN]": "[part of a personal name]",
    "[Zahl/Q]": "[number]",
    "-?-": "[?]",
    "?": "[?]",
    "???": "[?]",
    "[ ]": "[...]",
}

# German grammatical/function words → English
_FUNCTION_WORDS = {
    "in": "in",
    "für (jmd.)": "for (someone)",
    "ich [pron. suff. 1. sg.]": "I",
    "er [pron. suff. 3. masc. sg.]": "he/his",
    "sie [pron. suff. 3. fem. sg.]": "she/her",
    "sie [pron. suff. 3. pl.]": "they/their",
    "du [pron. suff. 2. masc. sg.]": "you/your",
    "wir [pron. suff. 1. pl.]": "we/our",
    "sein, ihr [pron. suff. 3. pl.]": "their",
    "mein [pron. suff. 1. sg.]": "my",
    "dein [pron. suff. 2. sg.]": "your",
    "sein [pron. suff. 3. masc. sg.]": "his",
    "ihr [pron. suff. 3. fem. sg.]": "her",
    "nicht": "not",
    "und": "and",
    "oder": "or",
    "mit": "with",
    "zu": "to",
    "von": "of/from",
    "auf": "on/upon",
    "aus": "from/out of",
    "an": "at/to",
    "unter": "under",
    "über": "over/above",
    "vor": "before",
    "nach": "after",
    "zwischen": "between",
    "durch": "through",
    "gegen": "against",
    "ohne": "without",
    "um": "around",
    "neben": "beside",
    "hinter": "behind",
    "dieser": "this",
    "jener": "that",
    "welcher": "which",
    "Alles": "everything",
    "alles": "everything",
    "danach aber": "but afterwards",
    "fröhlich, friedlich": "joyful, peaceful",
    "friedlich, in Frieden": "peacefully, in peace",
    "fröhlich; friedlich": "joyful; peaceful",
    "weshalb?": "why?",
    "abends": "in the evening",
    "(masc. des Ordinalbildungssuffixes)": "[ordinal suffix (masc.)]",
}

# Pattern for god/place name markers: GN/Name, ON/Name
_NAME_RE = re.compile(r"^(GN|PN|ON|KN|TN)/(.+)$")

# Pattern for bracketed annotations: [something]
_BRACKET_RE = re.compile(r"^\[(.+)\]$")


@dataclass
class MechanicalResult:
    """Result of a mechanical translation."""

    sentence_id: int
    english: str
    token_glosses: list[str]
    coverage: float  # fraction of tokens successfully bridged
    method: str = "mechanical"
    confidence: str = "MEDIUM"
    unbridged: list[str] = field(default_factory=list)


class MechanicalTranslator:
    """CPU-only translator using corpus-derived DE→EN dictionary."""

    def __init__(self, session: Session):
        self.session = session
        self._bridge: dict[str, str] = {}
        self._bridge_lower: dict[str, str] = {}
        self._built = False

    def build_bridge(self) -> int:
        """Build the DE→EN bridge dictionary from Thoth Lexicon.

        Sources (in priority order):
        1. definition_de → definition_en (direct dictionary pairs)
        2. glosses_de keys → definition_en / glosses_en / glosses_bridged_en
        3. Static editorial/function word maps
        4. Name pattern handlers (GN/Osiris → Osiris)

        Returns number of bridge entries.
        """
        bridge: dict[str, str] = {}

        # Phase 1: Direct definition pairs (highest confidence)
        rows = self.session.execute(
            sa_text("""
                SELECT definition_de, definition_en
                FROM thoth_lexicon
                WHERE definition_de IS NOT NULL AND definition_en IS NOT NULL
            """)
        ).fetchall()

        for de_def, en_def in rows:
            de_clean = de_def.strip()
            en_clean = en_def.strip()
            if de_clean and en_clean:
                bridge[de_clean] = en_clean

        phase1 = len(bridge)
        logger.info("Bridge phase 1 (definitions): %d entries", phase1)

        # Phase 2: glosses_de keys → best English via same lemma
        rows2 = self.session.execute(
            sa_text("""
                SELECT glosses_de, definition_en, glosses_en, glosses_bridged_en
                FROM thoth_lexicon
                WHERE glosses_de IS NOT NULL
                  AND (definition_en IS NOT NULL
                       OR glosses_en IS NOT NULL
                       OR glosses_bridged_en IS NOT NULL)
            """)
        ).fetchall()

        for gde_raw, def_en, gen_raw, ben_raw in rows2:
            gde = gde_raw if isinstance(gde_raw, dict) else {}
            gen = gen_raw if isinstance(gen_raw, dict) else {}
            ben = ben_raw if isinstance(ben_raw, dict) else {}

            # Best English: definition > mined glosses > bridged glosses
            best_en = def_en
            if not best_en and gen:
                best_en = next(iter(gen), None)
            if not best_en and ben:
                best_en = next(iter(ben), None)
            if not best_en:
                continue

            for de_term in gde:
                de_clean = de_term.strip()
                if de_clean and de_clean not in bridge:
                    bridge[de_clean] = best_en.strip()

        phase2 = len(bridge) - phase1
        logger.info("Bridge phase 2 (corpus glosses): %d entries", phase2)

        # Phase 3: Static maps
        bridge.update(_EDITORIAL_MAP)
        bridge.update(_FUNCTION_WORDS)

        phase3 = len(bridge) - phase1 - phase2
        logger.info("Bridge phase 3 (static): %d entries", phase3)

        self._bridge = bridge
        self._bridge_lower = {k.lower(): v for k, v in bridge.items()}
        self._built = True

        logger.info("Total bridge: %d entries", len(bridge))
        return len(bridge)

    def _lookup(self, de_gloss: str) -> Optional[str]:
        """Look up a German gloss in the bridge. Multi-strategy matching."""
        if not de_gloss:
            return None

        clean = de_gloss.strip()
        if not clean:
            return None

        # 1. Exact match
        if clean in self._bridge:
            return self._bridge[clean]

        # 2. Case-insensitive
        if clean.lower() in self._bridge_lower:
            return self._bridge_lower[clean.lower()]

        # 3. Name pattern: GN/Osiris → Osiris, ON/Heliopolis → Heliopolis
        name_match = _NAME_RE.match(clean)
        if name_match:
            return name_match.group(2)

        # 4. Strip outer brackets: [König] → try König
        bracket_match = _BRACKET_RE.match(clean)
        if bracket_match:
            inner = bracket_match.group(1)
            if inner in self._bridge:
                return f"[{self._bridge[inner]}]"
            if inner.lower() in self._bridge_lower:
                return f"[{self._bridge_lower[inner.lower()]}]"

        # 5. Try first part before semicolon: "König; Herrscher" → try "König"
        if ";" in clean:
            first = clean.split(";")[0].strip()
            if first in self._bridge:
                return self._bridge[first]
            if first.lower() in self._bridge_lower:
                return self._bridge_lower[first.lower()]

        # 6. Try first part before comma
        if "," in clean and ";" not in clean:
            first = clean.split(",")[0].strip()
            if first in self._bridge:
                return self._bridge[first]
            if first.lower() in self._bridge_lower:
                return self._bridge_lower[first.lower()]

        # 7. Numbers pass through
        if re.match(r"^[\d./]+$", clean):
            return clean

        # 8. Proper names (capitalized, no brackets, no German grammar words)
        if (
            clean[0].isupper()
            and len(clean) < 30
            and not clean.startswith("[")
            and " " not in clean
            and not any(c in clean for c in "();")
        ):
            return clean  # Proper name passthrough

        return None

    def translate_sentence(
        self, sentence_id: int, tokens: list[dict[str, str | None]], translation: dict[str, str | dict] | None = None
    ) -> MechanicalResult:
        """Translate a single sentence mechanically from token DE glosses."""
        if not self._built:
            raise RuntimeError("Call build_bridge() first")

        glosses_en: list[str] = []
        unbridged: list[str] = []
        bridged_count = 0
        total_count = 0

        for tok in tokens:
            if not isinstance(tok, dict):
                continue

            # Get German gloss from token (AED-TEI uses translation_de,
            # ORAEC/AES use cotext_translation)
            de_gloss = (
                tok.get("translation_de")
                or tok.get("cotext_translation")
                or ""
            )

            total_count += 1
            en = self._lookup(de_gloss)

            if en:
                # Clean up: take first meaning before semicolons for fluency
                # but keep full form in token_glosses
                short = en.split(";")[0].strip()
                # Remove metalinguistic brackets for fluency: "[preposition]" → ""
                # but keep semantic brackets: "[destroyed]"
                if short.startswith("[") and short.endswith("]"):
                    inner = short[1:-1]
                    if inner in (
                        "preposition", "auxiliary", "particle",
                        "suffix pronoun", "demonstrative pronoun",
                        "interrogative pronoun", "relative pronoun",
                        "conjunction", "interjection", "negation particle",
                    ):
                        short = ""  # Skip grammatical markers in fluent output
                glosses_en.append(short)
                bridged_count += 1
            else:
                # Keep German as fallback, italicized marker
                if de_gloss.strip():
                    glosses_en.append(f"«{de_gloss.strip()}»")
                    unbridged.append(de_gloss.strip())
                else:
                    glosses_en.append("[...]")

        words = [g for g in glosses_en if g]
        english = _cleanup_english(" ".join(words))

        coverage = bridged_count / total_count if total_count > 0 else 0.0

        if coverage >= 0.95:
            confidence = "HIGH"
        elif coverage >= 0.75:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return MechanicalResult(
            sentence_id=sentence_id,
            english=english,
            token_glosses=glosses_en,
            coverage=coverage,
            confidence=confidence,
            unbridged=unbridged,
        )

    def translate_batch(
        self,
        source: str | None = None,
        limit: int = 0,
        min_tokens: int = 1,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Translate untranslated sentences using the DE→EN bridge. Returns stats dict."""
        if not self._built:
            self.build_bridge()

        conditions = [
            "(s.translation IS NULL OR NOT (s.translation ? 'en'))",
            "s.tokens IS NOT NULL",
            "s.tokens != 'null'::jsonb",
            "jsonb_typeof(s.tokens) = 'array'",
        ]
        if min_tokens > 0:
            conditions.append(f"jsonb_array_length(s.tokens) >= {min_tokens}")
        if source:
            conditions.append(f"s.source = '{source}'")

        where = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit > 0 else ""

        count_q = f"SELECT COUNT(*) FROM sentences s WHERE {where}"
        total_eligible = self.session.execute(sa_text(count_q)).scalar()

        if dry_run:
            return {
                "eligible": total_eligible,
                "dry_run": True,
                "bridge_size": len(self._bridge),
            }

        stats = {
            "eligible": total_eligible,
            "translated": 0,
            "skipped": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total_coverage": 0.0,
            "bridge_size": len(self._bridge),
        }

        batch_size = 500
        last_id = 0
        translated_total = 0

        while True:
            rows = self.session.execute(
                sa_text(
                    f"SELECT s.id, s.tokens, s.translation, s.canonical_id "
                    f"FROM sentences s WHERE {where} "
                    f"AND s.id > :last_id "
                    f"ORDER BY s.id "
                    f"LIMIT {batch_size}"
                ),
                {"last_id": last_id},
            ).fetchall()

            if not rows:
                break

            for sid, tokens, translation, canonical_id in rows:
                last_id = sid

                if not isinstance(tokens, list) or len(tokens) < min_tokens:
                    stats["skipped"] += 1
                    continue

                result = self.translate_sentence(sid, tokens, translation)

                if not result.english.strip():
                    stats["skipped"] += 1
                    continue

                # Save translation
                self._save_translation(
                    sid, result, translation or {}, canonical_id
                )

                stats["translated"] += 1
                stats["total_coverage"] += result.coverage
                stats[result.confidence.lower()] += 1

                translated_total += 1
                if limit > 0 and translated_total >= limit:
                    break

            self.session.commit()

            if limit > 0 and translated_total >= limit:
                break

            if translated_total % 5000 < batch_size:
                logger.info(
                    "Mechanical translation progress: %d/%d",
                    translated_total,
                    total_eligible,
                )

        if stats["translated"] > 0:
            stats["avg_coverage"] = round(
                stats["total_coverage"] / stats["translated"], 4
            )
        del stats["total_coverage"]

        self.session.commit()
        logger.info("Mechanical translation complete: %s", stats)
        return stats

    def _save_translation(
        self,
        sentence_id: int,
        result: MechanicalResult,
        existing_translation: dict[str, str | dict],
        canonical_id: str,
    ):
        """Save mechanical translation to sentences.translation."""
        translation = dict(existing_translation)
        translation["en"] = result.english
        translation["_rosetta"] = {
            "source": "mechanical",
            "method": "de_en_bridge",
            "tier": "T0",  # mechanical = tier 0 (no LLM)
            "confidence": result.confidence,
            "coverage": round(result.coverage, 4),
            "bridge_size": len(self._bridge),
            "unbridged_count": len(result.unbridged),
            "needs_review": result.confidence != "HIGH",
            "translated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.session.execute(
            sa_text(
                "UPDATE sentences SET translation = :trans WHERE id = :sid"
            ),
            {"sid": sentence_id, "trans": json.dumps(translation, ensure_ascii=False)},
        )


def _cleanup_english(text: str) -> str:
    """Post-process mechanical English for basic fluency."""
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    # Remove trailing/leading punctuation artifacts
    text = text.strip("·|")

    # Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    # Ensure ends with period if no terminal punctuation
    if text and text[-1] not in ".!?»]":
        text = text + "."

    # Clean up bracket/quote artifacts
    text = text.replace("« »", "").replace("«»", "")
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+,", ",", text)

    return text
