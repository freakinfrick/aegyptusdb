"""Alias table seeder.

Auto-seeds the aliases table from:
  - ORAEC conventional_name fields (13,026 records)
  - ORAEC shelfmarks (from idno arrays)
  - AES text metadata (findspot, corpus labels -- via sentence source_detail)
  - Nederhof text titles

Each alias entry stores:
  - alias_text: the raw variant text
  - alias_normalized: the normalized form for matching
  - alias_type: 'conventional_name', 'shelfmark', 'abbreviation', 'foreign_title'
  - confidence: 'auto' for auto-generated, 'manual' for user-added

Run: PYTHONPATH=. python3 -m core.concordance.alias_seeder
"""

import logging
import sys
import time

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark
from core.models import Alias, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alias_seeder")

BATCH_SIZE = 1000


def add_alias(session, canonical_id: str, alias_text: str, alias_type: str,
              normalizer_fn=normalize_conventional_name, confidence: str = "auto") -> bool:
    """Insert an alias entry, returning True if new."""
    if not alias_text or not alias_text.strip():
        return False

    alias_text = alias_text.strip()
    normalized = normalizer_fn(alias_text)

    if not normalized:
        return False

    stmt = pg_insert(Alias).values(
        canonical_id=canonical_id,
        alias_text=alias_text,
        alias_normalized=normalized,
        alias_type=alias_type,
        confidence=confidence,
    ).on_conflict_do_nothing(
        constraint="uq_aliases_text_canonical"
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def seed_from_oraec_names(session) -> int:
    """Seed aliases from ORAEC conventional_name (title) fields."""
    log.info("Seeding from ORAEC conventional names...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id, conventional_name FROM texts "
            "WHERE canonical_id LIKE 'aeg_oraec_%' "
            "AND conventional_name IS NOT NULL "
            "AND conventional_name != ''"
        )
    ).fetchall()

    count = 0
    for canonical_id, name in rows:
        if add_alias(session, canonical_id, name, "conventional_name"):
            count += 1
        if count % BATCH_SIZE == 0 and count > 0:
            session.commit()

    session.commit()
    log.info("ORAEC conventional names: %d aliases added", count)
    return count


def seed_from_oraec_shelfmarks(session) -> int:
    """Seed aliases from ORAEC shelfmark arrays."""
    log.info("Seeding from ORAEC shelfmarks...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id, shelfmarks FROM texts "
            "WHERE canonical_id LIKE 'aeg_oraec_%' "
            "AND shelfmarks IS NOT NULL"
        )
    ).fetchall()

    count = 0
    for canonical_id, shelfmarks in rows:
        if not shelfmarks:
            continue
        for shelfmark in shelfmarks:
            if shelfmark and shelfmark.strip():
                if add_alias(session, canonical_id, shelfmark, "shelfmark",
                             normalizer_fn=normalize_shelfmark):
                    count += 1
        if count % BATCH_SIZE == 0 and count > 0:
            session.commit()

    session.commit()
    log.info("ORAEC shelfmarks: %d aliases added", count)
    return count


def seed_from_nederhof(session) -> int:
    """Seed aliases from Nederhof text titles."""
    log.info("Seeding from Nederhof titles...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id, conventional_name, shelfmarks FROM texts "
            "WHERE canonical_id LIKE 'aeg_nederhof_%'"
        )
    ).fetchall()

    count = 0
    for canonical_id, name, shelfmarks in rows:
        if name:
            if add_alias(session, canonical_id, name, "conventional_name"):
                count += 1
        if shelfmarks:
            for shelfmark in shelfmarks:
                if shelfmark and shelfmark.strip():
                    if add_alias(session, canonical_id, shelfmark, "shelfmark",
                                 normalizer_fn=normalize_shelfmark):
                        count += 1

    session.commit()
    log.info("Nederhof titles: %d aliases added", count)
    return count


def seed_from_tla_hf(session) -> int:
    """Seed aliases from TLA HF text names (conventional_name field)."""
    log.info("Seeding from TLA HF names...")

    rows = session.execute(
        sql_text(
            "SELECT canonical_id, conventional_name FROM texts "
            "WHERE canonical_id LIKE 'aeg_tla_hf_%' "
            "AND conventional_name IS NOT NULL "
            "AND conventional_name != ''"
        )
    ).fetchall()

    count = 0
    for canonical_id, name in rows:
        if add_alias(session, canonical_id, name, "conventional_name"):
            count += 1
        if count % BATCH_SIZE == 0 and count > 0:
            session.commit()

    session.commit()
    log.info("TLA HF names: %d aliases added", count)
    return count


def print_summary(session):
    """Print alias table statistics."""
    total = session.execute(sql_text("SELECT count(*) FROM aliases")).scalar()
    log.info("=" * 60)
    log.info("ALIAS TABLE SUMMARY")
    log.info("=" * 60)
    log.info("Total aliases: %d", total)

    rows = session.execute(
        sql_text(
            "SELECT alias_type, count(*) FROM aliases "
            "GROUP BY alias_type ORDER BY count(*) DESC"
        )
    ).fetchall()
    for alias_type, cnt in rows:
        log.info("  %-25s %d", alias_type, cnt)

    # Coverage
    total_texts = session.execute(sql_text("SELECT count(*) FROM texts")).scalar()
    aliased_texts = session.execute(
        sql_text("SELECT count(DISTINCT canonical_id) FROM aliases")
    ).scalar()
    log.info(
        "Coverage: %d/%d texts have at least one alias (%.1f%%)",
        aliased_texts, total_texts, 100 * aliased_texts / total_texts if total_texts else 0,
    )


def main():
    log.info("Alias table seeder starting")

    session = SessionLocal()

    try:
        t_start = time.time()

        oraec_names = seed_from_oraec_names(session)
        oraec_shelfmarks = seed_from_oraec_shelfmarks(session)
        nederhof_count = seed_from_nederhof(session)
        tla_hf_count = seed_from_tla_hf(session)

        elapsed = time.time() - t_start
        log.info(
            "Seeding complete in %.1fs: oraec_names=%d oraec_shelfmarks=%d "
            "nederhof=%d tla_hf=%d",
            elapsed, oraec_names, oraec_shelfmarks, nederhof_count, tla_hf_count,
        )

        print_summary(session)

    except Exception:
        log.exception("Fatal error during seeding")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
