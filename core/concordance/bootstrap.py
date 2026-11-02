"""Concordance bootstrap script.

Extracts ALL remaining ID mappings from ORAEC mapping files, AES metadata,
and TLA HF metadata. Cross-links systems:
  ORAEC <-> AES <-> TLA <-> Trismegistos <-> Wikidata <-> Karnak

The ORAEC importer (W2) already imported:
  - oraec: 13,026 entries (self-references)
  - tla: 13,026 entries (TLA base32 text IDs from credits.source)
  - trismegistos: 1,244 entries (from mapping_oraec_trismegistos.csv)
  - wikidata: 289 entries (from mapping_oraec_wikidata.tsv)
  - karnak: 31 entries (from mapping_oraec_karnak.tsv -- text-level only)
  - tla_entity_*: ~45,000+ entries (date, origplace, objecttype, location entities)

This bootstrap adds:
  - VEGA lemmata references (informational, stored with special prefix)
  - AES sentence-level IDs (linking AES sentences back to concordance)
  - Cross-system validation and coverage reporting

Run: PYTHONPATH=. python3 -m core.concordance.bootstrap
"""

import logging
import os
import sys
import time
from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import Concordance, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("concordance_bootstrap")

ORAEC_DATA_DIR = os.environ.get(
    "ORAEC_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "oraec_corpus_raw_data"),
)


def add_concordance_entry(session, canonical_id: str, external_system: str,
                          external_id: str, relationship: str = "exact_match") -> bool:
    """Insert a concordance entry, returning True if new."""
    stmt = pg_insert(Concordance).values(
        canonical_id=canonical_id,
        external_system=external_system,
        external_id=external_id,
        relationship=relationship,
    ).on_conflict_do_nothing(
        constraint="uq_concordance_system_ext_canonical"
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def bootstrap_aes_sentence_links(session) -> int:
    """Link AES sentence source_ids into concordance for cross-referencing.

    AES sentences have source_id values that are 27-char base32 AES IDs.
    We link these to their parent canonical texts for traceability.
    """
    log.info("Bootstrapping AES sentence concordance links...")

    # Get distinct (canonical_id, source_id) pairs from AES sentences
    rows = session.execute(
        sql_text(
            "SELECT DISTINCT canonical_id, source_id FROM sentences "
            "WHERE source = 'aes' AND source_id IS NOT NULL"
        )
    ).fetchall()

    count = 0
    for canonical_id, source_id in rows:
        if add_concordance_entry(session, canonical_id, "aes_sentence", source_id):
            count += 1
        if count % 5000 == 0 and count > 0:
            session.commit()

    session.commit()
    log.info("AES sentence links: %d new entries", count)
    return count


def bootstrap_tla_hf_links(session) -> int:
    """Add TLA HF dataset references to concordance.

    TLA HF texts have canonical_ids like aeg_tla_hf_* but no concordance
    entries yet. We add self-references for queryability.
    """
    log.info("Bootstrapping TLA HF concordance links...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id FROM texts "
            "WHERE canonical_id LIKE 'aeg_tla_hf_%'"
        )
    ).fetchall()

    count = 0
    for (canonical_id,) in rows:
        # Extract the numeric suffix as the TLA HF row ID
        hf_id = canonical_id.replace("aeg_tla_hf_", "")
        if add_concordance_entry(session, canonical_id, "tla_hf", hf_id):
            count += 1
        if count % 5000 == 0 and count > 0:
            session.commit()

    session.commit()
    log.info("TLA HF self-links: %d new entries", count)
    return count


def bootstrap_nederhof_links(session) -> int:
    """Add Nederhof text references to concordance."""
    log.info("Bootstrapping Nederhof concordance links...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id FROM texts "
            "WHERE canonical_id LIKE 'aeg_nederhof_%'"
        )
    ).fetchall()

    count = 0
    for (canonical_id,) in rows:
        nederhof_id = canonical_id.replace("aeg_nederhof_", "")
        if add_concordance_entry(session, canonical_id, "nederhof", nederhof_id):
            count += 1

    session.commit()
    log.info("Nederhof self-links: %d new entries", count)
    return count


def bootstrap_ramses_links(session) -> int:
    """Add RAMSES text references to concordance."""
    log.info("Bootstrapping RAMSES concordance links...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id FROM texts "
            "WHERE canonical_id LIKE 'aeg_ramses_%'"
        )
    ).fetchall()

    count = 0
    for (canonical_id,) in rows:
        ramses_id = canonical_id.replace("aeg_ramses_", "")
        if add_concordance_entry(session, canonical_id, "ramses", ramses_id):
            count += 1

    session.commit()
    log.info("RAMSES self-links: %d new entries", count)
    return count


def verify_coverage(session):
    """Print concordance coverage statistics."""
    log.info("=" * 60)
    log.info("CONCORDANCE COVERAGE REPORT")
    log.info("=" * 60)

    # Total entries
    total = session.execute(sql_text("SELECT count(*) FROM concordance")).scalar()
    log.info("Total concordance entries: %d", total)

    # Breakdown by system
    rows = session.execute(
        sql_text(
            "SELECT external_system, count(*) FROM concordance "
            "GROUP BY external_system ORDER BY count(*) DESC"
        )
    ).fetchall()
    for system, cnt in rows:
        log.info("  %-30s %d", system, cnt)

    # Texts with concordance coverage
    total_texts = session.execute(sql_text("SELECT count(*) FROM texts")).scalar()
    linked_texts = session.execute(
        sql_text("SELECT count(DISTINCT canonical_id) FROM concordance")
    ).scalar()
    log.info(
        "Text coverage: %d/%d texts have at least one concordance entry (%.1f%%)",
        linked_texts, total_texts, 100 * linked_texts / total_texts if total_texts else 0,
    )

    # Texts with cross-system links (more than just self-reference)
    multi_system = session.execute(
        sql_text(
            "SELECT count(*) FROM ("
            "  SELECT canonical_id FROM concordance "
            "  GROUP BY canonical_id "
            "  HAVING count(DISTINCT external_system) > 1"
            ") sub"
        )
    ).scalar()
    log.info(
        "Cross-linked texts: %d texts have links in 2+ systems (%.1f%%)",
        multi_system, 100 * multi_system / total_texts if total_texts else 0,
    )


def main():
    log.info("Concordance bootstrap starting")

    session = SessionLocal()

    try:
        t_start = time.time()

        # Bootstrap each source
        aes_count = bootstrap_aes_sentence_links(session)
        hf_count = bootstrap_tla_hf_links(session)
        nederhof_count = bootstrap_nederhof_links(session)
        ramses_count = bootstrap_ramses_links(session)

        elapsed = time.time() - t_start
        log.info(
            "Bootstrap complete in %.1fs: aes_sentences=%d tla_hf=%d nederhof=%d ramses=%d",
            elapsed, aes_count, hf_count, nederhof_count, ramses_count,
        )

        verify_coverage(session)

    except Exception:
        log.exception("Fatal error during bootstrap")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
