"""Entity Resolution Engine.

Determines whether an incoming text record matches an existing corpus entry.
Applies 4 matching strategies in order of decreasing confidence:
  1. Exact ID match (TLA, TM, ORAEC IDs via concordance table)
  2. Shelfmark match (normalized shelfmark via aliases table)
  3. Title/alias match (fuzzy match against aliases table)
  4. Content match (n-gram similarity on transliteration sequences)

Returns MatchResult on match, NoMatch on failure. Callers use this to decide
whether to merge layers or create a new canonical record.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Successful match against an existing corpus record."""

    canonical_id: str
    strategy: str  # exact_id, shelfmark, alias, content
    confidence: float  # 0.0 - 1.0
    match_detail: str = ""  # Human-readable explanation


@dataclass
class NoMatch:
    """No match found in the corpus."""

    attempted_strategies: list[str]
    best_candidate: str | None = None
    best_score: float = 0.0
    reason: str = ""


# Type alias for resolution result
ResolutionResult = MatchResult | NoMatch


# Default thresholds
ALIAS_FUZZY_THRESHOLD = 85.0  # rapidfuzz score 0-100
CONTENT_NGRAM_THRESHOLD = 0.70  # 0.0-1.0 similarity
CONTENT_REVIEW_THRESHOLD = 0.50  # Flag for human review if above this


class EntityResolver:
    """Resolve incoming text identifiers against the existing corpus."""

    def __init__(
        self,
        session: Session,
        alias_threshold: float = ALIAS_FUZZY_THRESHOLD,
        content_threshold: float = CONTENT_NGRAM_THRESHOLD,
    ):
        self.session = session
        self.alias_threshold = alias_threshold
        self.content_threshold = content_threshold

    def resolve(
        self,
        *,
        tla_id: str | None = None,
        tm_id: str | None = None,
        oraec_id: str | None = None,
        shelfmark: str | None = None,
        title: str | None = None,
        transliteration: str | None = None,
    ) -> ResolutionResult:
        """Run all matching strategies in order. Returns on first match."""
        attempted = []

        # Strategy 1: Exact ID match
        result = self._match_by_id(tla_id=tla_id, tm_id=tm_id, oraec_id=oraec_id)
        attempted.append("exact_id")
        if isinstance(result, MatchResult):
            return result

        # Strategy 2: Shelfmark match
        if shelfmark:
            result = self._match_by_shelfmark(shelfmark)
            attempted.append("shelfmark")
            if isinstance(result, MatchResult):
                return result

        # Strategy 3: Title/alias fuzzy match
        if title:
            result = self._match_by_alias(title)
            attempted.append("alias")
            if isinstance(result, MatchResult):
                return result

        # Strategy 4: Content match (transliteration n-gram similarity)
        if transliteration:
            result = self._match_by_content(transliteration)
            attempted.append("content")
            if isinstance(result, MatchResult):
                return result

        return NoMatch(
            attempted_strategies=attempted,
            reason="No match found across all strategies",
        )

    def _match_by_id(
        self,
        *,
        tla_id: str | None = None,
        tm_id: str | None = None,
        oraec_id: str | None = None,
    ) -> ResolutionResult:
        """Strategy 1: Look up exact IDs in the concordance table."""
        lookups = []
        if tla_id:
            lookups.append(("TLA", tla_id))
        if tm_id:
            lookups.append(("TM", str(tm_id)))
            lookups.append(("Trismegistos", str(tm_id)))
        if oraec_id:
            lookups.append(("ORAEC", str(oraec_id)))

        if not lookups:
            return NoMatch(attempted_strategies=["exact_id"], reason="No IDs provided")

        for system, ext_id in lookups:
            row = self.session.execute(
                sql_text(
                    "SELECT canonical_id FROM concordance "
                    "WHERE external_system = :system AND external_id = :ext_id "
                    "LIMIT 1"
                ),
                {"system": system, "ext_id": ext_id},
            ).fetchone()

            if row:
                canonical_id = row[0]
                logger.info(
                    "Exact ID match: %s:%s -> %s", system, ext_id, canonical_id
                )
                return MatchResult(
                    canonical_id=canonical_id,
                    strategy="exact_id",
                    confidence=1.0,
                    match_detail=f"{system}:{ext_id}",
                )

        # Also try canonical_id patterns directly
        if oraec_id:
            cid = f"aeg_oraec_{oraec_id}"
            exists = self.session.execute(
                sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
                {"cid": cid},
            ).fetchone()
            if exists:
                return MatchResult(
                    canonical_id=cid,
                    strategy="exact_id",
                    confidence=1.0,
                    match_detail=f"canonical_id pattern: {cid}",
                )

        if tla_id:
            # TLA IDs may be encoded in canonical_id as aeg_tla_hf_{id}
            cid = f"aeg_tla_hf_{tla_id}"
            exists = self.session.execute(
                sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
                {"cid": cid},
            ).fetchone()
            if exists:
                return MatchResult(
                    canonical_id=cid,
                    strategy="exact_id",
                    confidence=1.0,
                    match_detail=f"canonical_id pattern: {cid}",
                )

        return NoMatch(attempted_strategies=["exact_id"], reason="No ID match in concordance")

    def _match_by_shelfmark(self, shelfmark: str) -> ResolutionResult:
        """Strategy 2: Normalize shelfmark and match against aliases table."""
        normalized = normalize_shelfmark(shelfmark)
        if not normalized:
            return NoMatch(attempted_strategies=["shelfmark"], reason="Empty after normalization")

        # Try exact normalized match
        rows = self.session.execute(
            sql_text(
                "SELECT canonical_id, alias_text FROM aliases "
                "WHERE alias_type = 'shelfmark' AND alias_normalized = :norm"
            ),
            {"norm": normalized},
        ).fetchall()

        if rows:
            canonical_id = rows[0][0]
            alias_text = rows[0][1]
            logger.info(
                "Shelfmark match: '%s' (normalized: '%s') -> %s (via alias '%s')",
                shelfmark, normalized, canonical_id, alias_text,
            )
            return MatchResult(
                canonical_id=canonical_id,
                strategy="shelfmark",
                confidence=0.95,
                match_detail=f"shelfmark '{shelfmark}' normalized to '{normalized}', matched alias '{alias_text}'",
            )

        # Try suffix match to handle prefix normalization inconsistencies
        # e.g., stored "pchesterbeatty 8" vs normalized "chesterbeatty 8"
        rows = self.session.execute(
            sql_text(
                "SELECT canonical_id, alias_text, alias_normalized FROM aliases "
                "WHERE alias_type = 'shelfmark' "
                "AND (alias_normalized LIKE :suffix_pattern OR alias_normalized = :lower_raw)"
            ),
            {"suffix_pattern": f"%{normalized}", "lower_raw": shelfmark.lower().strip()},
        ).fetchall()

        if rows:
            # Score by how closely the normalized forms match
            best_row = None
            best_score = 0.0
            for cid, atext, anorm in rows:
                score = fuzz.ratio(normalized, anorm) / 100.0
                if score > best_score:
                    best_score = score
                    best_row = (cid, atext, anorm)
            if best_row and best_score >= 0.75:
                canonical_id, alias_text, alias_norm = best_row
                logger.info(
                    "Shelfmark suffix match: '%s' -> %s (alias='%s', score=%.2f)",
                    shelfmark, canonical_id, alias_text, best_score,
                )
                return MatchResult(
                    canonical_id=canonical_id,
                    strategy="shelfmark",
                    confidence=best_score,
                    match_detail=f"shelfmark suffix match: '{normalized}' ~ '{alias_norm}'",
                )

        return NoMatch(attempted_strategies=["shelfmark"], reason=f"No shelfmark match for '{normalized}'")

    def _match_by_alias(self, title: str) -> ResolutionResult:
        """Strategy 3: Fuzzy match title against aliases table."""
        normalized = normalize_conventional_name(title)
        if not normalized:
            return NoMatch(attempted_strategies=["alias"], reason="Empty after normalization")

        # First try exact normalized match
        rows = self.session.execute(
            sql_text(
                "SELECT canonical_id, alias_text, alias_normalized FROM aliases "
                "WHERE alias_normalized = :norm "
                "LIMIT 5"
            ),
            {"norm": normalized},
        ).fetchall()

        if rows:
            canonical_id = rows[0][0]
            logger.info("Exact alias match: '%s' -> %s", title, canonical_id)
            return MatchResult(
                canonical_id=canonical_id,
                strategy="alias",
                confidence=0.95,
                match_detail=f"exact alias match: '{title}' == '{rows[0][1]}'",
            )

        # Fuzzy match: fetch candidate aliases and score
        # Use trigram similarity or prefix match to narrow candidates
        # For performance, limit to aliases with shared prefix tokens
        tokens = normalized.split()
        if not tokens:
            return NoMatch(attempted_strategies=["alias"], reason="No tokens to match")

        # Use the first significant token (skip short stopwords)
        search_token = next(
            (t for t in tokens if len(t) >= 3),
            tokens[0],
        )

        candidates = self.session.execute(
            sql_text(
                "SELECT canonical_id, alias_text, alias_normalized FROM aliases "
                "WHERE alias_normalized LIKE :prefix "
                "LIMIT 200"
            ),
            {"prefix": f"%{search_token}%"},
        ).fetchall()

        best_score = 0.0
        best_candidate = None

        for canonical_id, alias_text, alias_norm in candidates:
            # Use token_sort_ratio for order-independent matching
            score = fuzz.token_sort_ratio(normalized, alias_norm)
            if score > best_score:
                best_score = score
                best_candidate = (canonical_id, alias_text, alias_norm)

        if best_candidate and best_score >= self.alias_threshold:
            canonical_id, alias_text, alias_norm = best_candidate
            logger.info(
                "Fuzzy alias match: '%s' ~ '%s' (score=%.1f) -> %s",
                title, alias_text, best_score, canonical_id,
            )
            return MatchResult(
                canonical_id=canonical_id,
                strategy="alias",
                confidence=best_score / 100.0,
                match_detail=f"fuzzy match: '{title}' ~ '{alias_text}' (score={best_score:.1f})",
            )

        no_match = NoMatch(
            attempted_strategies=["alias"],
            reason=f"Best fuzzy score {best_score:.1f} below threshold {self.alias_threshold}",
        )
        if best_candidate:
            no_match.best_candidate = best_candidate[0]
            no_match.best_score = best_score / 100.0
        return no_match

    def _match_by_content(self, transliteration: str) -> ResolutionResult:
        """Strategy 4: N-gram similarity on transliteration sequences.

        Compares incoming transliteration against existing sentences.
        High-similarity matches are flagged for human review.
        """
        if not transliteration or len(transliteration.strip()) < 20:
            return NoMatch(
                attempted_strategies=["content"],
                reason="Transliteration too short for content matching",
            )

        incoming_ngrams = self._char_ngrams(transliteration, n=3)
        if not incoming_ngrams:
            return NoMatch(attempted_strategies=["content"], reason="No n-grams extracted")

        # Sample existing transliterations (full scan would be too slow)
        # Focus on sentences with transliteration data
        rows = self.session.execute(
            sql_text(
                "SELECT canonical_id, transliteration FROM sentences "
                "WHERE transliteration IS NOT NULL AND length(transliteration) > 20 "
                "ORDER BY random() LIMIT 500"
            )
        ).fetchall()

        best_score = 0.0
        best_canonical = None
        best_translit = None

        for canonical_id, existing_translit in rows:
            existing_ngrams = self._char_ngrams(existing_translit, n=3)
            if not existing_ngrams:
                continue
            score = self._jaccard_similarity(incoming_ngrams, existing_ngrams)
            if score > best_score:
                best_score = score
                best_canonical = canonical_id
                best_translit = existing_translit[:100]

        if best_canonical and best_score >= self.content_threshold:
            logger.info(
                "Content match: similarity=%.3f -> %s", best_score, best_canonical
            )
            return MatchResult(
                canonical_id=best_canonical,
                strategy="content",
                confidence=best_score,
                match_detail=f"n-gram similarity={best_score:.3f} against '{best_translit}...'",
            )

        no_match = NoMatch(
            attempted_strategies=["content"],
            reason=f"Best content similarity {best_score:.3f} below threshold {self.content_threshold}",
        )
        if best_canonical:
            no_match.best_candidate = best_canonical
            no_match.best_score = best_score
        return no_match

    @staticmethod
    def _char_ngrams(text: str, n: int = 3) -> set[str]:
        """Extract character n-grams from text."""
        # Normalize for comparison: lowercase, strip diacritics-light, collapse whitespace
        text = re.sub(r"\s+", " ", text.lower().strip())
        if len(text) < n:
            return set()
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """Jaccard similarity between two sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
