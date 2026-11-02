"""Staging-to-Store Merge Pipeline.

On match: adds new representation layer(s) to the existing canonical record.
On no match: creates a new canonical record with source provenance.

All operations are idempotent -- re-running with the same input produces
no duplicates (uses ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark
from core.models import Alias, Concordance, RepresentationLayer, TextRecord
from core.resolution.engine import EntityResolver, MatchResult, NoMatch

logger = logging.getLogger(__name__)


@dataclass
class MergeStats:
    """Tracks merge operations for reporting."""

    merged: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.merged + self.created + self.skipped + self.errors

    def summary(self) -> dict:
        return {
            "merged": self.merged,
            "created": self.created,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
        }


@dataclass
class StagingRecord:
    """A record ready for merge into the central store.

    This is the intermediate format between parsers/importers and the DB.
    """

    # Identification hints (any or all may be None)
    tla_id: str | None = None
    tm_id: str | None = None
    oraec_id: str | None = None
    shelfmark: str | None = None
    title: str | None = None

    # Content
    text_content: str = ""
    transliteration: str | None = None
    language: str | None = None
    content_type: str = "mixed"  # translation, transliteration, commentary, etc.

    # Metadata
    source: str = ""
    source_url: str = ""
    source_attribution: str = ""
    script_type: str | None = None
    date_earliest: int | None = None
    date_latest: int | None = None
    period_label: str | None = None
    findspot: str | None = None
    current_location: str | None = None
    extra_metadata: dict | None = None

    def url_hash(self) -> str:
        """Generate a short hash from the source URL for canonical_id generation."""
        if self.source_url:
            return hashlib.sha256(self.source_url.encode()).hexdigest()[:12]
        # Fallback: hash of title + content prefix
        key = f"{self.title or ''}{self.text_content[:200]}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]


class StagingMerger:
    """Merges staging records into the central store.

    Usage:
        merger = StagingMerger(session)
        stats = merger.process_batch(records)
        session.commit()
    """

    def __init__(self, session: Session, resolver: EntityResolver | None = None):
        self.session = session
        self.resolver = resolver or EntityResolver(session)

    def process_record(self, record: StagingRecord) -> dict:
        """Process a single staging record.

        Returns dict with keys: action ('merged'|'created'|'skipped'|'error'),
        canonical_id, detail.
        """
        try:
            result = self.resolver.resolve(
                tla_id=record.tla_id,
                tm_id=record.tm_id,
                oraec_id=record.oraec_id,
                shelfmark=record.shelfmark,
                title=record.title,
                transliteration=record.transliteration,
            )

            if isinstance(result, MatchResult):
                return self._merge_into_existing(record, result)
            else:
                return self._create_new_record(record)

        except Exception as e:
            logger.error("Error processing record '%s': %s", record.title, e)
            return {"action": "error", "canonical_id": None, "detail": str(e)}

    def process_batch(self, records: list[StagingRecord]) -> MergeStats:
        """Process a batch of staging records.

        Commits after each successful record to avoid losing progress.
        """
        stats = MergeStats()

        for record in records:
            result = self.process_record(record)
            action = result["action"]

            if action == "merged":
                stats.merged += 1
            elif action == "created":
                stats.created += 1
            elif action == "skipped":
                stats.skipped += 1
            else:
                stats.errors += 1

            stats.details.append(result)

        # Commit the batch
        self.session.commit()

        logger.info(
            "Merge batch complete: %d merged, %d created, %d skipped, %d errors",
            stats.merged, stats.created, stats.skipped, stats.errors,
        )
        return stats

    def _merge_into_existing(self, record: StagingRecord, match: MatchResult) -> dict:
        """Add new layer(s) to an existing canonical record."""
        canonical_id = match.canonical_id

        # Check for duplicate layer (idempotency)
        existing_layer = self.session.execute(
            sql_text(
                "SELECT id FROM representation_layers "
                "WHERE canonical_id = :cid "
                "AND layer_type = :ltype "
                "AND source = :source "
                "LIMIT 1"
            ),
            {
                "cid": canonical_id,
                "ltype": record.content_type,
                "source": record.source,
            },
        ).fetchone()

        if existing_layer:
            logger.debug(
                "Skipping duplicate layer for %s (type=%s, source=%s)",
                canonical_id, record.content_type, record.source,
            )
            return {
                "action": "skipped",
                "canonical_id": canonical_id,
                "detail": f"Layer already exists (strategy={match.strategy})",
            }

        # Add representation layer
        layer = RepresentationLayer(
            canonical_id=canonical_id,
            layer_type=record.content_type,
            content={"text": record.text_content},
            language=record.language,
            source=record.source,
            source_detail={
                "url": record.source_url,
                "attribution": record.source_attribution,
                "match_strategy": match.strategy,
                "match_confidence": match.confidence,
                "match_detail": match.match_detail,
            },
            confidence="unreviewed",
        )
        self.session.add(layer)

        # Add alias if title is new
        if record.title:
            self._add_alias_if_new(canonical_id, record.title)

        logger.info(
            "Merged layer into %s (strategy=%s, confidence=%.2f)",
            canonical_id, match.strategy, match.confidence,
        )
        return {
            "action": "merged",
            "canonical_id": canonical_id,
            "detail": f"Added {record.content_type} layer via {match.strategy} (confidence={match.confidence:.2f})",
        }

    def _create_new_record(self, record: StagingRecord) -> dict:
        """Create a new canonical record for unmatched content."""
        url_hash = record.url_hash()
        canonical_id = f"aeg_crawl_{url_hash}"

        # Check if this crawl record already exists (idempotency)
        exists = self.session.execute(
            sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
            {"cid": canonical_id},
        ).fetchone()

        if exists:
            # Record exists but wasn't matched by resolver -- add layer if new
            return self._merge_into_existing(
                record,
                MatchResult(
                    canonical_id=canonical_id,
                    strategy="url_hash",
                    confidence=1.0,
                    match_detail="Re-import of existing crawl record",
                ),
            )

        # Create text record
        text_record = TextRecord(
            canonical_id=canonical_id,
            conventional_name=record.title,
            script_type=record.script_type,
            date_earliest=record.date_earliest,
            date_latest=record.date_latest,
            period_label=record.period_label,
            findspot=record.findspot,
            current_location=record.current_location,
            text_type=record.content_type,
            completeness="unknown",
            extra_metadata={
                "source": record.source,
                "source_url": record.source_url,
                "source_attribution": record.source_attribution,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                **(record.extra_metadata or {}),
            },
        )
        self.session.add(text_record)
        self.session.flush()  # Get the record into DB before adding layers

        # Add representation layer
        layer = RepresentationLayer(
            canonical_id=canonical_id,
            layer_type=record.content_type,
            content={"text": record.text_content},
            language=record.language,
            source=record.source,
            source_detail={
                "url": record.source_url,
                "attribution": record.source_attribution,
            },
            confidence="unreviewed",
        )
        self.session.add(layer)

        # Add alias
        if record.title:
            self._add_alias_if_new(canonical_id, record.title)

        # Add shelfmark alias if present
        if record.shelfmark:
            self._add_shelfmark_alias(canonical_id, record.shelfmark)

        # Add concordance entries for any known IDs
        self._add_concordance_entries(canonical_id, record)

        logger.info("Created new record: %s ('%s')", canonical_id, record.title)
        return {
            "action": "created",
            "canonical_id": canonical_id,
            "detail": f"New record from {record.source}",
        }

    def _add_alias_if_new(self, canonical_id: str, title: str) -> None:
        """Add a conventional_name alias if it doesn't already exist."""
        normalized = normalize_conventional_name(title)
        if not normalized:
            return

        stmt = pg_insert(Alias).values(
            canonical_id=canonical_id,
            alias_text=title.strip(),
            alias_normalized=normalized,
            alias_type="conventional_name",
            confidence="auto",
        ).on_conflict_do_nothing(constraint="uq_aliases_text_canonical")
        self.session.execute(stmt)

    def _add_shelfmark_alias(self, canonical_id: str, shelfmark: str) -> None:
        """Add a shelfmark alias."""
        normalized = normalize_shelfmark(shelfmark)
        if not normalized:
            return

        stmt = pg_insert(Alias).values(
            canonical_id=canonical_id,
            alias_text=shelfmark.strip(),
            alias_normalized=normalized,
            alias_type="shelfmark",
            confidence="auto",
        ).on_conflict_do_nothing(constraint="uq_aliases_text_canonical")
        self.session.execute(stmt)

    def _add_concordance_entries(self, canonical_id: str, record: StagingRecord) -> None:
        """Add concordance entries for any external IDs on the record."""
        entries = []
        if record.tla_id:
            entries.append(("TLA", record.tla_id))
        if record.tm_id:
            entries.append(("TM", str(record.tm_id)))
        if record.oraec_id:
            entries.append(("ORAEC", str(record.oraec_id)))

        for system, ext_id in entries:
            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system=system,
                external_id=ext_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(constraint="uq_concordance_system_ext_canonical")
            self.session.execute(stmt)
