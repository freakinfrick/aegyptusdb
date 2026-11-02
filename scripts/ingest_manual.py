"""Ingest manually prepared JSON text files into the corpus.

Usage: python scripts/ingest_manual.py data/manual/shabaka_stone.json
       python scripts/ingest_manual.py data/manual/  (all JSON files in dir)

JSON format: see data/manual/shabaka_stone.json for example.
"""

import json
import logging
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import (
    Alias,
    Concordance,
    RepresentationLayer,
    Sentence,
    SessionLocal,
    TextRecord,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)


def ingest_file(session, filepath: Path) -> dict:
    """Ingest a single JSON file. Returns stats dict."""
    log.info("Ingesting: %s", filepath)

    with open(filepath) as fh:
        data = json.load(fh)

    canonical_id = data["canonical_id"]
    stats = {"file": filepath.name, "texts": 0, "sentences": 0, "concordance": 0, "aliases": 0}

    # TextRecord
    text_rec = {
        "canonical_id": canonical_id,
        "conventional_name": data.get("conventional_name"),
        "script_type": data.get("script_type"),
        "date_earliest": data.get("date_earliest"),
        "date_latest": data.get("date_latest"),
        "period_label": data.get("period_label"),
        "findspot": data.get("findspot"),
        "current_location": data.get("current_location"),
        "text_type": data.get("text_type"),
        "completeness": data.get("completeness", "unknown"),
        "shelfmarks": data.get("shelfmarks"),
        "metadata": data.get("extra_metadata"),
        "source_corpus": data.get("source_corpus", ["manual"]),
    }
    stmt = pg_insert(TextRecord.__table__).values(text_rec)
    stmt = stmt.on_conflict_do_nothing(index_elements=["canonical_id"])
    result = session.execute(stmt)
    stats["texts"] = result.rowcount
    session.commit()

    # Sentences — skip ones already present (no unique constraint on source_id),
    # confidence from the sentence, else the file, else "verified"
    existing = {
        r[0] for r in session.execute(
            select(Sentence.source_id).where(Sentence.canonical_id == canonical_id)
        )
    }
    default_conf = data.get("default_confidence", "verified")
    for sent in data.get("sentences", []):
        if f"{canonical_id}-{sent.get('sequence_num', 0)}" in existing:
            continue
        sent_rec = {
            "canonical_id": canonical_id,
            "sequence_num": sent.get("sequence_num"),
            "transliteration": sent.get("transliteration"),
            "translation": sent.get("translation"),
            "tokens": sent.get("tokens"),
            "source": "manual",
            "source_id": f"{canonical_id}-{sent.get('sequence_num', 0)}",
            "source_detail": sent.get("source_detail"),
            "confidence": sent.get("confidence", default_conf),
        }
        session.execute(pg_insert(Sentence.__table__).values(sent_rec))
        stats["sentences"] += 1
    session.commit()

    # Concordance
    for conc in data.get("concordance", []):
        conc_rec = {
            "canonical_id": canonical_id,
            "external_system": conc["external_system"],
            "external_id": conc["external_id"],
            "relationship": "exact_match",
        }
        stmt = pg_insert(Concordance.__table__).values(conc_rec)
        stmt = stmt.on_conflict_do_nothing()
        result = session.execute(stmt)
        stats["concordance"] += result.rowcount
    session.commit()

    # Aliases
    for alias_text in data.get("aliases", []):
        normalized = re.sub(r"\s+", " ", alias_text.strip().lower())
        alias_rec = {
            "canonical_id": canonical_id,
            "alias_text": alias_text,
            "alias_normalized": normalized,
            "alias_type": "conventional_name",
            "confidence": "verified",
        }
        stmt = pg_insert(Alias.__table__).values(alias_rec)
        stmt = stmt.on_conflict_do_nothing()
        result = session.execute(stmt)
        stats["aliases"] += result.rowcount
    session.commit()

    log.info("  Text: %d, Sentences: %d, Concordance: %d, Aliases: %d",
             stats["texts"], stats["sentences"], stats["concordance"], stats["aliases"])
    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_manual.py <file_or_dir>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_dir():
        files = sorted(target.glob("*.json"))
    else:
        files = [target]

    if not files:
        log.error("No JSON files found at %s", target)
        sys.exit(1)

    session = SessionLocal()
    try:
        total = {"texts": 0, "sentences": 0, "concordance": 0, "aliases": 0}
        for f in files:
            stats = ingest_file(session, f)
            for k in total:
                total[k] += stats[k]

        log.info("=" * 60)
        log.info("Manual ingest complete.")
        log.info("  Files:       %d", len(files))
        log.info("  Texts:       %d", total["texts"])
        log.info("  Sentences:   %d", total["sentences"])
        log.info("  Concordance: %d", total["concordance"])
        log.info("  Aliases:     %d", total["aliases"])
        log.info("=" * 60)
    except Exception:
        log.exception("Fatal error")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
