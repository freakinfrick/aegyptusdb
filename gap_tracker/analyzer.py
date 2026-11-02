"""Core gap analysis engine.

Compares corpus holdings against what should exist and identifies gaps:
- Texts with no translation layer
- Texts with no transliteration layer
- Orphan records (zero concordance links)
- Coverage analysis by source
- Texts with sentences but no representation layers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, text as sa_text
from sqlalchemy.orm import Session

from core.models import (
    Alias,
    Concordance,
    Gap,
    RepresentationLayer,
    Sentence,
    SessionLocal,
    TextRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class GapSummary:
    """Summary counts for a single gap type."""

    gap_type: str
    count: int
    priority: str
    sample_ids: list[str] = field(default_factory=list)


@dataclass
class GapReport:
    """Full gap analysis report."""

    timestamp: str
    total_texts: int
    total_sentences: int
    total_layers: int
    total_concordance: int
    summaries: list[GapSummary] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    gaps_written: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "corpus": {
                "texts": self.total_texts,
                "sentences": self.total_sentences,
                "layers": self.total_layers,
                "concordance": self.total_concordance,
            },
            "gaps": [
                {
                    "type": s.gap_type,
                    "count": s.count,
                    "priority": s.priority,
                    "samples": s.sample_ids[:5],
                }
                for s in self.summaries
            ],
            "coverage": self.coverage,
            "gaps_written": self.gaps_written,
        }


class GapAnalyzer:
    """Analyzes the corpus for gaps and writes results to the gaps table."""

    def __init__(self, session: Optional[Session] = None) -> None:
        self._own_session = session is None
        self._session = session or SessionLocal()

    def close(self) -> None:
        if self._own_session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def run_full_analysis(self, write_gaps: bool = True, limit_per_type: int = 500) -> GapReport:
        """Run all gap analyses and return a report."""
        session = self._session

        report = GapReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_texts=session.query(func.count(TextRecord.canonical_id)).scalar() or 0,
            total_sentences=session.query(func.count(Sentence.id)).scalar() or 0,
            total_layers=session.query(func.count(RepresentationLayer.id)).scalar() or 0,
            total_concordance=session.query(func.count(Concordance.id)).scalar() or 0,
        )

        # Run each analysis
        analyses = [
            ("no_translation", "P3", self._find_no_translation),
            ("no_transliteration", "P3", self._find_no_transliteration),
            ("orphan", "P3", self._find_orphans),
            ("no_layers", "P1", self._find_no_layers),
            ("sentences_no_layers", "P2", self._find_sentences_no_layers),
        ]

        total_written = 0
        for gap_type, priority, finder in analyses:
            canonical_ids = finder(limit=limit_per_type)
            summary = GapSummary(
                gap_type=gap_type,
                count=len(canonical_ids),
                priority=priority,
                sample_ids=canonical_ids[:10],
            )
            report.summaries.append(summary)
            logger.info("Gap type '%s' (P=%s): %d texts", gap_type, priority, len(canonical_ids))

            if write_gaps and canonical_ids:
                written = self._write_gaps(canonical_ids, gap_type, priority, limit_per_type)
                total_written += written

        # Coverage analysis
        report.coverage = self._compute_coverage()
        report.gaps_written = total_written

        if write_gaps:
            self._session.commit()
            logger.info("Wrote %d gap records total", total_written)

        return report

    def _find_no_translation(self, limit: int = 500) -> list[str]:
        """Texts that have transliteration layers but no translation layers."""
        session = self._session
        rows = session.execute(sa_text("""
            SELECT t.canonical_id
            FROM texts t
            WHERE EXISTS (
                SELECT 1 FROM representation_layers rl
                WHERE rl.canonical_id = t.canonical_id
                AND rl.layer_type = 'transliteration'
            )
            AND NOT EXISTS (
                SELECT 1 FROM representation_layers rl2
                WHERE rl2.canonical_id = t.canonical_id
                AND rl2.layer_type = 'translation'
            )
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [r[0] for r in rows]

    def _find_no_transliteration(self, limit: int = 500) -> list[str]:
        """Texts that have some layers but no transliteration."""
        session = self._session
        rows = session.execute(sa_text("""
            SELECT t.canonical_id
            FROM texts t
            WHERE EXISTS (
                SELECT 1 FROM representation_layers rl
                WHERE rl.canonical_id = t.canonical_id
            )
            AND NOT EXISTS (
                SELECT 1 FROM representation_layers rl2
                WHERE rl2.canonical_id = t.canonical_id
                AND rl2.layer_type = 'transliteration'
            )
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [r[0] for r in rows]

    def _find_orphans(self, limit: int = 500) -> list[str]:
        """Texts with zero concordance links to external systems."""
        session = self._session
        rows = session.execute(sa_text("""
            SELECT t.canonical_id
            FROM texts t
            LEFT JOIN concordance c ON c.canonical_id = t.canonical_id
            WHERE c.id IS NULL
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [r[0] for r in rows]

    def _find_no_layers(self, limit: int = 500) -> list[str]:
        """Texts with zero representation layers at all."""
        session = self._session
        rows = session.execute(sa_text("""
            SELECT t.canonical_id
            FROM texts t
            LEFT JOIN representation_layers rl ON rl.canonical_id = t.canonical_id
            WHERE rl.id IS NULL
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [r[0] for r in rows]

    def _find_sentences_no_layers(self, limit: int = 500) -> list[str]:
        """Texts that have sentences but no representation layers.

        These are texts where we have sentence-level data (from AES/TLA)
        but the document-level layers haven't been created.
        """
        session = self._session
        rows = session.execute(sa_text("""
            SELECT DISTINCT s.canonical_id
            FROM sentences s
            LEFT JOIN representation_layers rl ON rl.canonical_id = s.canonical_id
            WHERE rl.id IS NULL
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [r[0] for r in rows]

    def _compute_coverage(self) -> dict:
        """Compute coverage statistics by source and layer type."""
        session = self._session

        coverage = {}

        # Texts by source prefix
        rows = session.execute(sa_text("""
            SELECT split_part(canonical_id, '_', 2) AS src, count(*)
            FROM texts
            GROUP BY src ORDER BY count(*) DESC
        """)).fetchall()
        coverage["texts_by_source"] = {r[0]: r[1] for r in rows}

        # Layer coverage per layer type
        rows = session.execute(sa_text("""
            SELECT rl.layer_type, count(DISTINCT rl.canonical_id)
            FROM representation_layers rl
            GROUP BY rl.layer_type
        """)).fetchall()
        coverage["texts_with_layer_type"] = {r[0]: r[1] for r in rows}

        # Sentences by source
        rows = session.execute(sa_text("""
            SELECT source, count(*) FROM sentences GROUP BY source ORDER BY count(*) DESC
        """)).fetchall()
        coverage["sentences_by_source"] = {r[0]: r[1] for r in rows}

        # Confidence distribution across layers
        rows = session.execute(sa_text("""
            SELECT confidence, count(*) FROM representation_layers GROUP BY confidence
        """)).fetchall()
        coverage["layer_confidence"] = {r[0]: r[1] for r in rows}

        # Sentences by confidence
        rows = session.execute(sa_text("""
            SELECT confidence, count(*) FROM sentences GROUP BY confidence
        """)).fetchall()
        coverage["sentence_confidence"] = {r[0]: r[1] for r in rows}

        return coverage

    def _write_gaps(
        self,
        canonical_ids: list[str],
        gap_type: str,
        priority: str,
        limit: int,
    ) -> int:
        """Write gap records, skipping duplicates."""
        session = self._session

        # Get existing gaps for this type to avoid duplicates
        existing = set()
        rows = session.execute(sa_text("""
            SELECT canonical_id FROM gaps WHERE gap_type = :gt AND status = 'open'
        """), {"gt": gap_type}).fetchall()
        existing = {r[0] for r in rows}

        action_map = {
            "no_translation": "Queue for draft translation (ML or manual)",
            "no_transliteration": "Queue for transliteration (OCR or manual)",
            "orphan": "Queue for concordance enrichment (TM/TLA lookup)",
            "no_layers": "Needs investigation - text record with no content",
            "sentences_no_layers": "Promote sentence data to representation layers",
        }

        written = 0
        for cid in canonical_ids:
            if cid in existing:
                continue
            gap = Gap(
                canonical_id=cid,
                external_system="corpus_internal",
                external_id=cid,
                gap_type=gap_type,
                priority=priority,
                recommended_action=action_map.get(gap_type, "Review"),
                status="open",
            )
            session.add(gap)
            written += 1
            if written >= limit:
                break

        session.flush()
        return written

    def run_single_analysis(
        self,
        gap_type: str,
        write_gaps: bool = True,
        limit: int = 500,
    ) -> GapSummary:
        """Run a single type of gap analysis."""
        finders = {
            "no_translation": ("P3", self._find_no_translation),
            "no_transliteration": ("P3", self._find_no_transliteration),
            "orphan": ("P3", self._find_orphans),
            "no_layers": ("P1", self._find_no_layers),
            "sentences_no_layers": ("P2", self._find_sentences_no_layers),
        }

        if gap_type not in finders:
            raise ValueError(f"Unknown gap type: {gap_type}. Valid: {list(finders.keys())}")

        priority, finder = finders[gap_type]
        canonical_ids = finder(limit=limit)

        summary = GapSummary(
            gap_type=gap_type,
            count=len(canonical_ids),
            priority=priority,
            sample_ids=canonical_ids[:10],
        )

        if write_gaps and canonical_ids:
            written = self._write_gaps(canonical_ids, gap_type, priority, limit)
            if write_gaps:
                self._session.commit()
            logger.info("Wrote %d gap records for type '%s'", written, gap_type)

        return summary
