"""Inverted index for parallel sentence retrieval by lemma overlap."""

import logging
from typing import TypedDict

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
CANDIDATE_LIMIT = 200


class ParallelRow(TypedDict):
    """Result row from find_parallel_sentences."""
    sentence_id: int
    canonical_id: str
    transliteration: str | None
    translation_en: str | None
    translation_de: str | None
    similarity_score: float


class InvertedIndexBuilder:
    """Build and query the rosetta_lemma_index for parallel sentence retrieval."""

    def __init__(self, session: Session):
        self.session = session

    def build_index(self) -> int:
        """Scan all sentences with tokens, insert (lemma_id, sentence_id)
        into rosetta_lemma_index.  Idempotent via ON CONFLICT DO NOTHING.
        Returns total entries created."""

        total_created = 0
        offset = 0

        while True:
            rows = self.session.execute(
                sa_text(
                    "SELECT id, tokens FROM sentences "
                    "WHERE tokens IS NOT NULL "
                    "ORDER BY id "
                    "LIMIT :batch OFFSET :offset"
                ),
                {"batch": BATCH_SIZE, "offset": offset},
            ).fetchall()

            if not rows:
                break

            pairs: list[dict[str, str | int]] = []
            for row in rows:
                sentence_id = row[0]
                tokens = row[1]
                if not isinstance(tokens, list):
                    continue
                seen_lemmas: set[str] = set()
                for tok in tokens:
                    if not isinstance(tok, dict):
                        continue
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    if not lemma_id or lemma_id in seen_lemmas:
                        continue
                    # Normalize: tokens use bare numeric IDs, lexicon uses 'tla' prefix
                    lemma_id = lemma_id if lemma_id.startswith('tla') else f'tla{lemma_id}'
                    seen_lemmas.add(lemma_id)
                    pairs.append({"lid": lemma_id, "sid": sentence_id})

            if pairs:
                # Bulk insert with conflict handling
                values_clause = ", ".join(
                    f"(:lid_{i}, :sid_{i})" for i in range(len(pairs))
                )
                params: dict[str, str | int] = {}
                for i, p in enumerate(pairs):
                    params[f"lid_{i}"] = p["lid"]
                    params[f"sid_{i}"] = p["sid"]

                result = self.session.execute(
                    sa_text(
                        f"INSERT INTO rosetta_lemma_index (lemma_id, sentence_id) "
                        f"VALUES {values_clause} "
                        f"ON CONFLICT DO NOTHING"
                    ),
                    params,
                )
                total_created += result.rowcount

            offset += BATCH_SIZE
            if offset % 10_000 < BATCH_SIZE:
                logger.info("Index build progress: %d sentences scanned, %d entries", offset, total_created)

        self.session.commit()
        logger.info("Index build complete: %d entries created", total_created)
        return total_created

    def get_sentence_lemmas(self, sentence_id: int) -> set[str]:
        """Get lemma IDs for a sentence.  Uses index first, falls back to tokens."""

        rows = self.session.execute(
            sa_text(
                "SELECT lemma_id FROM rosetta_lemma_index "
                "WHERE sentence_id = :sid"
            ),
            {"sid": sentence_id},
        ).fetchall()

        if rows:
            return {r[0] for r in rows}

        # Fallback: read tokens directly
        row = self.session.execute(
            sa_text("SELECT tokens FROM sentences WHERE id = :sid"),
            {"sid": sentence_id},
        ).fetchone()

        if not row or not row[0]:
            return set()

        lemmas: set[str] = set()
        for tok in row[0]:
            if not isinstance(tok, dict):
                continue
            lid = tok.get("lemmaID") or tok.get("lemma_id")
            if lid:
                lemmas.add(lid if lid.startswith('tla') else f'tla{lid}')
        return lemmas

    def find_parallel_sentences(
        self, sentence_id: int, top_k: int = 5
    ) -> list[ParallelRow]:
        """Find most similar already-translated sentences by Jaccard overlap."""

        query_lemmas = self.get_sentence_lemmas(sentence_id)
        if not query_lemmas:
            return []

        # SQL: candidates sharing ≥2 lemmas with English translation
        rows = self.session.execute(
            sa_text("""
                WITH query_lemmas AS (
                    SELECT lemma_id
                    FROM rosetta_lemma_index
                    WHERE sentence_id = :sid
                ),
                candidates AS (
                    SELECT ri.sentence_id, COUNT(*) as shared
                    FROM rosetta_lemma_index ri
                    JOIN query_lemmas ql ON ri.lemma_id = ql.lemma_id
                    WHERE ri.sentence_id != :sid
                    GROUP BY ri.sentence_id
                    HAVING COUNT(*) >= 2
                    ORDER BY COUNT(*) DESC
                    LIMIT :candidate_limit
                )
                SELECT c.sentence_id, c.shared, s.canonical_id, s.transliteration,
                       s.translation->>'en' as en, s.translation->>'de' as de
                FROM candidates c
                JOIN sentences s ON s.id = c.sentence_id
                WHERE s.translation ? 'en'
                ORDER BY c.shared DESC
                LIMIT :top_k
            """),
            {
                "sid": sentence_id,
                "candidate_limit": CANDIDATE_LIMIT,
                "top_k": top_k * 3,  # over-fetch for Jaccard re-ranking
            },
        ).fetchall()

        # Compute Jaccard for each candidate
        results: list[ParallelRow] = []
        for row in rows:
            cand_id = row[0]
            cand_lemmas = self.get_sentence_lemmas(cand_id)
            if not cand_lemmas:
                continue
            intersection = len(query_lemmas & cand_lemmas)
            union = len(query_lemmas | cand_lemmas)
            jaccard = intersection / union if union else 0.0

            results.append({
                "sentence_id": cand_id,
                "canonical_id": row[2],
                "transliteration": row[3],
                "translation_en": row[4],
                "translation_de": row[5],
                "similarity_score": round(jaccard, 4),
            })

        results.sort(key=lambda r: float(r["similarity_score"] or 0.0), reverse=True)
        return results[:top_k]



    def index_stats(self) -> dict[str, int]:
        """Return stats: total_entries, unique_lemmas, unique_sentences."""

        row = self.session.execute(
            sa_text(
                "SELECT COUNT(*), "
                "COUNT(DISTINCT lemma_id), "
                "COUNT(DISTINCT sentence_id) "
                "FROM rosetta_lemma_index"
            )
        ).fetchone()

        return {
            "total_entries": row[0] if row else 0,
            "unique_lemmas": row[1] if row else 0,
            "unique_sentences": row[2] if row else 0,
        }
