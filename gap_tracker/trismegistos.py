"""Conservative Trismegistos API checker.

Uses the TM TexRelations Matcher API for ID lookups to find texts
present in TM but not in our corpus. Rate-limited and conservative
to avoid hammering their API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from core.models import Concordance, Gap, SessionLocal

logger = logging.getLogger(__name__)

# TM API base URL for text lookups
TM_API_BASE = "https://www.trismegistos.org/dataservices"
# Be very conservative with API calls
REQUEST_DELAY_SECONDS = 2.0
MAX_REQUESTS_PER_RUN = 50


@dataclass
class TMCheckResult:
    """Result of checking a TM ID against our corpus."""

    tm_id: str
    in_corpus: bool
    canonical_id: Optional[str] = None
    tm_data: Optional[dict] = None
    error: Optional[str] = None


class TrismegistosChecker:
    """Check Trismegistos IDs against our concordance table.

    Two modes:
    1. Local-only: Check which TM IDs in our concordance table lack full records
    2. API lookup: For a given TM ID, check if it exists in TM and in our corpus
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        max_api_calls: int = MAX_REQUESTS_PER_RUN,
        delay: float = REQUEST_DELAY_SECONDS,
    ) -> None:
        self._own_session = session is None
        self._session = session or SessionLocal()
        self._max_api_calls = max_api_calls
        self._delay = delay
        self._api_calls_made = 0

    def close(self) -> None:
        if self._own_session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def check_local_coverage(self) -> dict:
        """Analyze TM IDs already in our concordance table.

        Returns stats on how many TM-linked texts we have vs. total TM references.
        """
        session = self._session

        # Count concordance entries with TM IDs
        tm_entries = session.execute(sa_text("""
            SELECT count(*) FROM concordance
            WHERE external_system = 'trismegistos'
        """)).scalar() or 0

        # Count unique TM IDs
        tm_unique = session.execute(sa_text("""
            SELECT count(DISTINCT external_id) FROM concordance
            WHERE external_system = 'trismegistos'
        """)).scalar() or 0

        # Count TM-linked texts that also have layers
        tm_with_layers = session.execute(sa_text("""
            SELECT count(DISTINCT c.canonical_id)
            FROM concordance c
            JOIN representation_layers rl ON rl.canonical_id = c.canonical_id
            WHERE c.external_system = 'trismegistos'
        """)).scalar() or 0

        # Count TM-linked texts with no layers
        tm_no_layers = session.execute(sa_text("""
            SELECT count(DISTINCT c.canonical_id)
            FROM concordance c
            LEFT JOIN representation_layers rl ON rl.canonical_id = c.canonical_id
            WHERE c.external_system = 'trismegistos'
            AND rl.id IS NULL
        """)).scalar() or 0

        return {
            "tm_concordance_entries": tm_entries,
            "tm_unique_ids": tm_unique,
            "tm_texts_with_layers": tm_with_layers,
            "tm_texts_no_layers": tm_no_layers,
        }

    def lookup_tm_id(self, tm_id: str) -> TMCheckResult:
        """Check if a TM text ID exists in our corpus, and optionally fetch TM data.

        This is conservative: it checks our concordance first, and only
        calls the TM API if we need external data.
        """
        session = self._session

        # Check local concordance first
        row = session.execute(sa_text("""
            SELECT canonical_id FROM concordance
            WHERE external_system = 'trismegistos' AND external_id = :tm_id
            LIMIT 1
        """), {"tm_id": str(tm_id)}).fetchone()

        if row:
            return TMCheckResult(tm_id=str(tm_id), in_corpus=True, canonical_id=row[0])

        return TMCheckResult(tm_id=str(tm_id), in_corpus=False)

    def fetch_tm_text_info(self, tm_id: str) -> Optional[dict]:
        """Fetch basic text info from TM API (rate-limited).

        Returns None if rate limit exceeded or API unavailable.
        """
        if self._api_calls_made >= self._max_api_calls:
            logger.warning("TM API rate limit reached (%d calls)", self._max_api_calls)
            return None

        url = f"{TM_API_BASE}/texrelations/text/{tm_id}"
        try:
            if self._api_calls_made > 0:
                time.sleep(self._delay)

            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
                self._api_calls_made += 1

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    return None
                else:
                    logger.warning("TM API returned %d for TM %s", resp.status_code, tm_id)
                    return None
        except httpx.HTTPError as e:
            logger.error("TM API error for TM %s: %s", tm_id, e)
            return None

    def find_tm_gaps(self, tm_ids: list[str], write_gaps: bool = False) -> list[TMCheckResult]:
        """Check a list of TM IDs against our corpus.

        Does NOT call the TM API -- just checks our concordance table.
        Use this for batch checking known TM IDs (e.g., from ORAEC mappings).
        """
        results = []
        for tm_id in tm_ids:
            result = self.lookup_tm_id(tm_id)
            results.append(result)

        missing = [r for r in results if not r.in_corpus]
        logger.info("Checked %d TM IDs: %d in corpus, %d missing", len(results), len(results) - len(missing), len(missing))

        if write_gaps and missing:
            self._write_tm_gaps(missing)

        return results

    def _write_tm_gaps(self, missing: list[TMCheckResult]) -> int:
        """Write gap records for TM IDs not in our corpus."""
        session = self._session
        written = 0

        # Check existing gaps to avoid duplicates
        existing = set()
        rows = session.execute(sa_text("""
            SELECT external_id FROM gaps
            WHERE external_system = 'trismegistos' AND gap_type = 'not_imported' AND status = 'open'
        """)).fetchall()
        existing = {r[0] for r in rows}

        for result in missing:
            if result.tm_id in existing:
                continue
            gap = Gap(
                canonical_id=None,
                external_system="trismegistos",
                external_id=result.tm_id,
                gap_type="not_imported",
                priority="P0",
                recommended_action="Import from Trismegistos or linked source",
                status="open",
            )
            session.add(gap)
            written += 1

        if written:
            session.flush()
            session.commit()
            logger.info("Wrote %d TM gap records", written)

        return written
