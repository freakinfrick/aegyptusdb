"""Tier classifier — assign translation priority tiers T1–T5 to sentences."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from core.models import Sentence

logger = logging.getLogger(__name__)

# Tier definitions:
# T1: German translation + word-level glosses + thoth_lexicon coverage
# T2: German translation only (no word-level glosses)
# T3: Tokens + lexicon only (no German, no English)
# T4: Transliteration only (no tokens or very few with lemmaIDs)
# T5: Fragments / damaged / minimal


class TierClassifier:
    """Classify sentences into translation tiers T1–T5 based on available evidence."""

    def classify(self, sentence: Sentence, session: Session) -> str:
        """Classify a single Sentence ORM object into a tier."""
        translit = sentence.transliteration or ""
        translation = sentence.translation or {}
        tokens = sentence.tokens or []

        has_de = "de" in translation
        has_en = "en" in translation
        token_count = len(tokens)

        # T5: Fragments / damaged / minimal
        if len(translit.strip()) < 5:
            return "T5"

        # Count tokens with lemmaIDs
        lemma_count = 0
        has_cotext = False
        for tok in tokens:
            if not isinstance(tok, dict):
                continue
            lid = tok.get("lemmaID") or tok.get("lemma_id")
            if lid:
                lemma_count += 1
            if tok.get("cotext_translation") or tok.get("translation_de"):
                has_cotext = True

        lemma_ratio = lemma_count / token_count if token_count > 0 else 0.0

        # T4: Transliteration only (no tokens or very few with lemmaIDs)
        if token_count == 0 or lemma_ratio < 0.3:
            return "T4"

        # T1: German translation + word-level glosses
        if has_de and has_cotext:
            return "T1"

        # T2: German translation only (no word-level glosses)
        if has_de:
            return "T2"

        # T3: Tokens + lexicon only (no German, no English)
        if lemma_count > 0:
            return "T3"

        # Fallback — transliteration exists but nothing else useful
        return "T4"

    def classify_batch(self, sentence_ids: list[int], session: Session) -> dict[int, str]:
        """Classify many sentences efficiently using raw SQL.

        Returns {sentence_id: tier_string}.
        """
        if not sentence_ids:
            return {}

        # Batch query for classification criteria
        rows = session.execute(
            sa_text("""
                SELECT s.id,
                    s.transliteration,
                    CASE WHEN s.translation ? 'de' THEN true ELSE false END as has_de,
                    CASE WHEN s.translation ? 'en' THEN true ELSE false END as has_en,
                    jsonb_array_length(COALESCE(s.tokens, '[]'::jsonb)) as token_count,
                    s.tokens
                FROM sentences s
                WHERE s.id = ANY(:ids)
            """),
            {"ids": sentence_ids},
        ).fetchall()

        result: dict[int, str] = {}

        for row in rows:
            sid, translit, has_de, has_en, token_count, tokens = row
            translit = translit or ""
            tokens = tokens or []

            # T5: Fragments / damaged / minimal
            if len(translit.strip()) < 5:
                result[sid] = "T5"
                continue

            # Count lemmaIDs and check for cotext_translation
            lemma_count = 0
            has_cotext = False
            for tok in tokens:
                if not isinstance(tok, dict):
                    continue
                lid = tok.get("lemmaID") or tok.get("lemma_id")
                if lid:
                    lemma_count += 1
                if tok.get("cotext_translation") or tok.get("translation_de"):
                    has_cotext = True

            lemma_ratio = lemma_count / token_count if token_count > 0 else 0.0

            # T4: Transliteration only
            if token_count == 0 or lemma_ratio < 0.3:
                result[sid] = "T4"
                continue

            # T1: German translation + word-level glosses
            if has_de and has_cotext:
                result[sid] = "T1"
                continue

            # T2: German translation only
            if has_de:
                result[sid] = "T2"
                continue

            # T3: Tokens + lexicon only
            if lemma_count > 0:
                result[sid] = "T3"
                continue

            result[sid] = "T4"

        return result

    def get_tier_counts(self, session: Session) -> dict[str, int]:
        """Count untranslated sentences per tier.

        Only counts sentences that have transliteration but no English translation.
        """
        # Get a sample of untranslated sentence IDs for classification
        # Process in chunks to avoid memory issues
        counts: dict[str, int] = {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "T5": 0}
        chunk_size = 5000
        offset = 0

        while True:
            ids = [
                row[0]
                for row in session.execute(
                    sa_text("""
                        SELECT id FROM sentences
                        WHERE transliteration IS NOT NULL
                        AND (translation IS NULL OR NOT (translation ? 'en'))
                        ORDER BY id
                        LIMIT :lim OFFSET :off
                    """),
                    {"lim": chunk_size, "off": offset},
                ).fetchall()
            ]

            if not ids:
                break

            tiers = self.classify_batch(ids, session)
            for tier in tiers.values():
                counts[tier] = counts.get(tier, 0) + 1

            offset += chunk_size

            if len(ids) < chunk_size:
                break

        return counts
