"""LexiconBuilder — orchestrate Thoth Lexicon construction from corpus evidence."""

from __future__ import annotations

import logging

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from .bridge import GermanEnglishBridge
from .coptic import CopticLinker
from .miner import TokenMiner

logger = logging.getLogger(__name__)


class LexiconBuilder:
    """Build and enrich the Thoth Lexicon from corpus evidence.

    Orchestrates phases 1a through 1g of the Rosetta spec.
    """

    def __init__(self, session: Session):
        self.session = session
        self._miner = TokenMiner(session)
        self._bridge = GermanEnglishBridge()
        self._coptic = CopticLinker(session)

    def build_all(self) -> dict[str, int]:
        """Run all phases in order. Return stats dict."""
        stats: dict[str, int] = {}
        stats["seeded"] = self.seed_from_lemmata()
        stats["german_glosses"] = self.enrich_german_glosses()
        stats["english_contexts"] = self.enrich_english_contexts()
        stats["bridged"] = self.bridge_german_to_english()
        stats["coptic"] = self.link_coptic_cognates()
        stats["attestation"] = self.compute_stats()
        stats["confidence"] = self.set_confidence_tiers()
        logger.info("Lexicon build complete: %s", stats)
        return stats

    def seed_from_lemmata(self) -> int:
        """Phase 1a: Copy from lemmata table into thoth_lexicon.

        INSERT from lemmata with translation->>'de', translation->>'en', pos.
        ON CONFLICT DO NOTHING — idempotent.
        """
        result = self.session.execute(
            sa_text("""
                INSERT INTO thoth_lexicon (lemma_id, definition_de, definition_en, pos, sources)
                SELECT id, translation->>'de', translation->>'en', pos, '["aed"]'::jsonb
                FROM lemmata
                ON CONFLICT (lemma_id) DO NOTHING
            """)
        )
        self.session.commit()
        count = result.rowcount
        logger.info("Phase 1a: seeded %d lemmas from lemmata", count)
        return count

    def enrich_german_glosses(self) -> int:
        """Phase 1b: Mine German glosses and update thoth_lexicon.glosses_de."""
        glosses = self._miner.mine_german_glosses()
        if not glosses:
            logger.info("Phase 1b: no German glosses found")
            return 0

        count = 0
        batch: list[dict[str, str | dict[str, int]]] = []
        for lemma_id, gloss_map in glosses.items():
            # Normalize: tokens use bare numeric IDs, lemmata table uses 'tla' prefix
            norm_id = lemma_id if lemma_id.startswith('tla') else f'tla{lemma_id}'
            batch.append({"lid": norm_id, "glosses": dict(gloss_map)})
            if len(batch) >= 500:
                count += self._batch_update_glosses_de(batch)
                batch.clear()

        if batch:
            count += self._batch_update_glosses_de(batch)

        self.session.commit()
        logger.info("Phase 1b: enriched %d lemmas with German glosses", count)
        return count

    def _batch_update_glosses_de(self, batch: list[dict[str, str | dict[str, int]]]) -> int:
        """Update glosses_de for a batch of lemmas."""
        import json

        count = 0
        for item in batch:
            result = self.session.execute(
                sa_text("""
                    UPDATE thoth_lexicon SET glosses_de = :glosses, updated_at = NOW()
                    WHERE lemma_id = :lid
                """),
                {"lid": item["lid"], "glosses": json.dumps(item["glosses"])},
            )
            count += result.rowcount
        return count

    def enrich_english_contexts(self) -> int:
        """Phase 1c: Mine English contexts and update thoth_lexicon.glosses_en."""
        contexts = self._miner.mine_english_contexts()
        if not contexts:
            logger.info("Phase 1c: no English contexts found")
            return 0

        import json

        count = 0
        for lemma_id, en_map in contexts.items():
            # Normalize: tokens use bare numeric IDs, lemmata table uses 'tla' prefix
            norm_id = lemma_id if lemma_id.startswith('tla') else f'tla{lemma_id}'
            # Keep top 20 terms by score
            top = dict(sorted(en_map.items(), key=lambda x: -x[1])[:20])
            result = self.session.execute(
                sa_text("""
                    UPDATE thoth_lexicon SET glosses_en = :glosses, updated_at = NOW()
                    WHERE lemma_id = :lid
                """),
                {"lid": norm_id, "glosses": json.dumps(top)},
            )
            count += result.rowcount

        self.session.commit()
        logger.info("Phase 1c: enriched %d lemmas with English contexts", count)
        return count

    def bridge_german_to_english(self) -> int:
        """Phase 1d: Bridge German->English for lemmas with DE but no EN.

        Query thoth_lexicon WHERE glosses_de IS NOT NULL
        AND definition_en IS NULL AND glosses_en IS NULL.
        """
        rows = self.session.execute(
            sa_text("""
                SELECT lemma_id, glosses_de FROM thoth_lexicon
                WHERE glosses_de IS NOT NULL
                  AND definition_en IS NULL
                  AND glosses_en IS NULL
            """)
        ).fetchall()

        if not rows:
            logger.info("Phase 1d: no lemmas need bridging")
            return 0

        # Build input: {lemma_id: {german_gloss: freq}}
        german_glosses: dict[str, dict[str, int]] = {}
        for row in rows:
            lemma_id = row[0]
            glosses = row[1]
            if isinstance(glosses, dict):
                german_glosses[lemma_id] = glosses

        if not german_glosses:
            return 0

        bridged = self._bridge.bridge_glosses(german_glosses)

        import json

        count = 0
        for lemma_id, en_map in bridged.items():
            result = self.session.execute(
                sa_text("""
                    UPDATE thoth_lexicon SET glosses_bridged_en = :bridged, updated_at = NOW()
                    WHERE lemma_id = :lid
                """),
                {"lid": lemma_id, "bridged": json.dumps(en_map)},
            )
            count += result.rowcount

        self.session.commit()
        logger.info("Phase 1d: bridged %d lemmas DE->EN", count)
        return count

    def link_coptic_cognates(self) -> int:
        """Phase 1e: Link Coptic cognates."""
        cognates = self._coptic.find_cognates()

        if not cognates:
            logger.info("Phase 1e: no Coptic cognates found")
            return 0

        import json

        count = 0
        for lemma_id, entries in cognates.items():
            result = self.session.execute(
                sa_text("""
                    UPDATE thoth_lexicon SET coptic_cognates = :cognates, updated_at = NOW()
                    WHERE lemma_id = :lid
                """),
                {"lid": lemma_id, "cognates": json.dumps(entries)},
            )
            count += result.rowcount

        self.session.commit()
        logger.info("Phase 1e: linked %d lemmas with Coptic cognates", count)
        return count

    def compute_stats(self) -> int:
        """Phase 1f: Compute attestation statistics.

        For each lemma in thoth_lexicon:
        - Count frequency from sentence token scan
        - Get period_range from parent texts
        - Get text_types distribution
        - Select up to 3 best example sentences (has EN translation, shortest)
        """
        import json

        # Get all lexicon lemma IDs
        lex_rows = self.session.execute(
            sa_text("SELECT lemma_id FROM thoth_lexicon")
        ).fetchall()
        lemma_ids = {row[0] for row in lex_rows}

        if not lemma_ids:
            return 0

        # Build frequency map from rosetta_lemma_index if populated,
        # otherwise fall back to token scan
        freq_map = self._count_frequencies(lemma_ids)

        # Get period and text_type info per lemma via sentences -> texts join
        period_map, type_map = self._get_text_metadata(lemma_ids)

        # Get example sentences
        examples_map = self._get_examples(lemma_ids)

        count = 0
        for lid in lemma_ids:
            freq = freq_map.get(lid, 0)
            periods = period_map.get(lid)
            types = type_map.get(lid)
            examples = examples_map.get(lid)

            result = self.session.execute(
                sa_text("""
                    UPDATE thoth_lexicon SET
                        frequency = :freq,
                        period_range = :periods,
                        text_types = :types,
                        examples = :examples,
                        updated_at = NOW()
                    WHERE lemma_id = :lid
                """),
                {
                    "lid": lid,
                    "freq": freq,
                    "periods": json.dumps(periods) if periods else None,
                    "types": json.dumps(types) if types else None,
                    "examples": json.dumps(examples) if examples else None,
                },
            )
            count += result.rowcount

        self.session.commit()
        logger.info("Phase 1f: computed stats for %d lemmas", count)
        return count

    def _count_frequencies(self, lemma_ids: set[str]) -> dict[str, int]:
        """Count lemma frequencies from rosetta_lemma_index or token scan."""
        # Try rosetta_lemma_index first
        check = self.session.execute(
            sa_text("SELECT COUNT(*) FROM rosetta_lemma_index LIMIT 1")
        ).scalar()

        if check and check > 0:
            rows = self.session.execute(
                sa_text("""
                    SELECT lemma_id, COUNT(*) AS freq
                    FROM rosetta_lemma_index
                    GROUP BY lemma_id
                """)
            ).fetchall()
            return {row[0]: row[1] for row in rows}

        # Fallback: POS distribution already mined includes counts
        pos_dist = self._miner.mine_pos_distribution()
        freq_map: dict[str, int] = {}
        for lid, pos_counts in pos_dist.items():
            # Normalize: tokens use bare numeric IDs, lexicon uses 'tla' prefix
            norm_id = lid if lid.startswith('tla') else f'tla{lid}'
            freq_map[norm_id] = sum(pos_counts.values())
        return freq_map

    def _get_text_metadata(
        self, lemma_ids: set[str]
    ) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
        """Get period_range and text_type distributions per lemma via sentence->text join."""
        from collections import defaultdict

        period_map: dict[str, dict[str, int]] = {}
        type_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Use rosetta_lemma_index if populated for efficiency
        check = self.session.execute(
            sa_text("SELECT COUNT(*) FROM rosetta_lemma_index LIMIT 1")
        ).scalar()

        if check and check > 0:
            rows = self.session.execute(
                sa_text("""
                    SELECT rli.lemma_id, t.period_label, t.text_type,
                           t.date_earliest, t.date_latest
                    FROM rosetta_lemma_index rli
                    JOIN sentences s ON rli.sentence_id = s.id
                    JOIN texts t ON s.canonical_id = t.canonical_id
                """)
            ).fetchall()

            date_ranges: dict[str, list[int]] = defaultdict(list)
            for row in rows:
                lid, period, ttype, d_early, d_late = row
                if period:
                    type_map[lid][period] = type_map[lid].get(period, 0) + 1
                if ttype:
                    type_map[lid][ttype] = type_map[lid].get(ttype, 0) + 1
                if d_early is not None:
                    date_ranges[lid].append(d_early)
                if d_late is not None:
                    date_ranges[lid].append(d_late)

            for lid, dates in date_ranges.items():
                if dates:
                    period_map[lid] = {"earliest": min(dates), "latest": max(dates)}

        return period_map, dict(type_map)

    def _get_examples(self, lemma_ids: set[str], max_per_lemma: int = 3) -> dict[str, list[dict[str, str | int | None]]]:
        """Select up to N best example sentences per lemma.

        Prefers sentences with EN translation, sorted by length (shortest first).
        """
        # Use rosetta_lemma_index if populated
        check = self.session.execute(
            sa_text("SELECT COUNT(*) FROM rosetta_lemma_index LIMIT 1")
        ).scalar()

        if not check or check == 0:
            return {}

        result: dict[str, list[dict[str, str | int | None]]] = {}

        # Process in chunks to avoid massive IN clauses
        lid_list = list(lemma_ids)
        for i in range(0, len(lid_list), 100):
            chunk = lid_list[i : i + 100]
            # Use a lateral join to get top N per lemma
            rows = self.session.execute(
                sa_text("""
                    SELECT rli.lemma_id, s.id, s.transliteration,
                           s.translation->>'en' AS en
                    FROM rosetta_lemma_index rli
                    JOIN sentences s ON rli.sentence_id = s.id
                    WHERE rli.lemma_id = ANY(:lids)
                      AND s.translation ? 'en'
                    ORDER BY rli.lemma_id, LENGTH(s.translation->>'en')
                """),
                {"lids": chunk},
            ).fetchall()

            for row in rows:
                lid = row[0]
                if lid not in result:
                    result[lid] = []
                if len(result[lid]) < max_per_lemma:
                    result[lid].append({
                        "sentence_id": row[1],
                        "transliteration": row[2],
                        "en": row[3],
                    })

        return result

    def set_confidence_tiers(self) -> dict[str, int]:
        """Phase 1g: Set confidence tiers.

        Gold: definition_en IS NOT NULL AND definition_de IS NOT NULL AND frequency >= 10
        Silver: definition_de IS NOT NULL AND (glosses_bridged_en OR glosses_en) AND frequency >= 3
        Bronze: everything else
        """
        gold = self.session.execute(
            sa_text("""
                UPDATE thoth_lexicon SET confidence = 'gold', updated_at = NOW()
                WHERE definition_en IS NOT NULL
                  AND definition_de IS NOT NULL
                  AND frequency >= 10
            """)
        ).rowcount

        silver = self.session.execute(
            sa_text("""
                UPDATE thoth_lexicon SET confidence = 'silver', updated_at = NOW()
                WHERE confidence IS DISTINCT FROM 'gold'
                  AND definition_de IS NOT NULL
                  AND (glosses_bridged_en IS NOT NULL OR glosses_en IS NOT NULL)
                  AND frequency >= 3
            """)
        ).rowcount

        bronze = self.session.execute(
            sa_text("""
                UPDATE thoth_lexicon SET confidence = 'bronze', updated_at = NOW()
                WHERE confidence IS NULL
                   OR confidence NOT IN ('gold', 'silver')
            """)
        ).rowcount

        self.session.commit()
        tiers = {"gold": gold, "silver": silver, "bronze": bronze}
        logger.info("Phase 1g: confidence tiers — %s", tiers)
        return tiers
