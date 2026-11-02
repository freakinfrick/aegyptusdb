"""Batch Orchestrator — orchestrate translation across tiers and backends."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.models import Sentence

from .classifier import TierClassifier
from .translator import RosettaTranslator
from .validator import RosettaValidator

logger = logging.getLogger(__name__)

# Default per-tier batch limits
DEFAULT_TIER_LIMITS = {
    "T1": 100,
    "T2": 50,
    "T3": 50,
    "T4": 25,
    "T5": 0,  # skip fragments
}


class BatchOrchestrator:
    """Orchestrate batch translation across tiers and backends."""

    def __init__(
        self,
        session: Session,
        translator: Optional[RosettaTranslator] = None,
        validator: Optional[RosettaValidator] = None,
    ):
        self.session = session
        self.translator = translator or RosettaTranslator()
        self.validator = validator or RosettaValidator()
        self._classifier = TierClassifier()

    def run_batch(
        self,
        tier: str = "all",
        limit: int = 100,
        backend: str = "local",
    ) -> dict[str, Any]:
        """Translate a batch of untranslated sentences.

        Returns stats: {translated, failed, skipped, total, errors}.
        """
        from rosetta.witness.dossier import assemble_dossier

        stats = {"translated": 0, "failed": 0, "skipped": 0, "total": 0, "errors": []}

        if tier == "all":
            sentences = self._find_untranslated_all(limit)
        else:
            sentences = self._find_untranslated_by_tier(tier, limit)

        stats["total"] = len(sentences)
        logger.info("Batch: %d sentences to translate (tier=%s)", len(sentences), tier)

        for i, sent in enumerate(sentences):
            try:
                dossier = assemble_dossier(sent.id, self.session)
                result = self.translator.translate_with_witnesses(dossier)

                if not result.success:
                    stats["failed"] += 1
                    if result.error:
                        stats["errors"].append(
                            f"sentence {sent.id}: {result.error}"
                        )
                    continue

                is_valid, reason, adjusted_conf = self.validator.validate(
                    result, dossier
                )

                if not is_valid:
                    stats["failed"] += 1
                    stats["errors"].append(
                        f"sentence {sent.id} validation: {reason}"
                    )
                    logger.warning(
                        "Rejected sentence %d: %s", sent.id, reason
                    )
                    continue

                if result.metadata.get("_rosetta"):
                    result.metadata["_rosetta"]["confidence"] = adjusted_conf.lower()

                saved = self.save_result(result, self.session)
                if saved:
                    stats["translated"] += 1
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"sentence {sent.id}: {e}")
                logger.error("Error translating sentence %d: %s", sent.id, e)

            if (i + 1) % 10 == 0:
                self.session.commit()
                logger.info(
                    "Progress: %d/%d (translated=%d, failed=%d)",
                    i + 1, stats["total"], stats["translated"], stats["failed"],
                )

        self.session.commit()
        logger.info(
            "Batch complete: translated=%d, failed=%d, skipped=%d, total=%d",
            stats["translated"], stats["failed"], stats["skipped"], stats["total"],
        )
        return stats

    def run_all_tiers(self, limits: Optional[dict[str, int]] = None) -> dict[str, dict[str, Any]]:
        """Run batches across all tiers in priority order (T1 first).

        Returns {tier: batch_stats, ...}.
        """
        tier_limits = limits or dict(DEFAULT_TIER_LIMITS)
        results: dict[str, dict[str, Any]] = {}

        for tier in ["T1", "T2", "T3", "T4", "T5"]:
            lim = tier_limits.get(tier, 0)
            if lim <= 0:
                logger.info("Skipping tier %s (limit=0)", tier)
                results[tier] = {"translated": 0, "failed": 0, "skipped": 0, "total": 0}
                continue

            logger.info("Starting tier %s (limit=%d)", tier, lim)
            results[tier] = self.run_batch(tier=tier, limit=lim)

        return results

    def save_result(self, result, session: Session) -> bool:
        """Save translation to sentence.translation JSONB.

        Returns True if saved, False if skipped.
        """
        if not result.success or not result.translation_en:
            return False

        sentence = session.get(Sentence, result.sentence_id)
        if not sentence:
            logger.warning("Sentence %d not found", result.sentence_id)
            return False

        existing_trans = sentence.translation or {}
        if "en" in existing_trans:
            logger.debug(
                "Skipping sentence %d: already has English translation",
                result.sentence_id,
            )
            return False

        existing_trans["en"] = result.translation_en
        sentence.translation = dict(existing_trans)
        flag_modified(sentence, "translation")

        rosetta_meta = result.metadata.get("_rosetta", {})
        if rosetta_meta:
            existing_trans["_rosetta"] = rosetta_meta
            sentence.translation = dict(existing_trans)
            flag_modified(sentence, "translation")

        sentence_meta = dict(sentence.source_detail or {})
        sentence_meta["en_translation"] = {
            "source": "ml_draft",
            "model": result.model,
            "confidence": rosetta_meta.get("confidence", "low"),
            "needs_review": True,
            "confidence_llm": result.confidence_llm,
            "notes": result.notes,
            "translated_at": rosetta_meta.get("translated_at"),
        }
        sentence.source_detail = sentence_meta
        flag_modified(sentence, "source_detail")

        logger.info(
            "Saved Rosetta translation for sentence %d (%s)",
            result.sentence_id, result.canonical_id,
        )
        return True

    def _find_untranslated_by_tier(self, tier: str, limit: int) -> list[Sentence]:
        """Find untranslated sentences matching a given tier."""
        # Over-fetch since classification will filter some out
        fetch_limit = limit * 3

        ids = [
            row[0]
            for row in self.session.execute(
                sa_text("""
                    SELECT id FROM sentences
                    WHERE transliteration IS NOT NULL
                    AND (translation IS NULL OR NOT (translation ? 'en'))
                    ORDER BY id
                    LIMIT :lim
                """),
                {"lim": fetch_limit},
            ).fetchall()
        ]

        if not ids:
            return []

        tiers = self._classifier.classify_batch(ids, self.session)
        matching_ids = [sid for sid, t in tiers.items() if t == tier][:limit]

        if not matching_ids:
            return []

        return (
            self.session.query(Sentence)
            .filter(Sentence.id.in_(matching_ids))
            .all()
        )

    def _find_untranslated_all(self, limit: int) -> list[Sentence]:
        """Find untranslated sentences across all tiers."""
        ids = [
            row[0]
            for row in self.session.execute(
                sa_text("""
                    SELECT id FROM sentences
                    WHERE transliteration IS NOT NULL
                    AND (translation IS NULL OR NOT (translation ? 'en'))
                    ORDER BY id
                    LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()
        ]

        if not ids:
            return []

        return (
            self.session.query(Sentence)
            .filter(Sentence.id.in_(ids))
            .all()
        )
