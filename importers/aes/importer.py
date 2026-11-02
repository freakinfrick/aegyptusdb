"""AES (Ancient Egyptian Sentences) bulk importer.

Imports 16 subcorpus JSON files from simondschweitzer/aes into:
  - sentences: linked to existing ORAEC texts via shared TLA base32 IDs
  - texts: new canonical records for any AES sentences not matching ORAEC

Each AES file contains sentence records keyed by 26-char base32 sentence IDs.
Each sentence has a `text` field containing the parent text's TLA base32 ID.

Linking: AES text field -> concordance(external_system='tla') -> canonical_id

Idempotent: skips sentences already imported (source='aes', source_id=sentence_id).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import (
    Concordance,
    Sentence,
    SessionLocal,
    TextRecord,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aes_importer")

DATA_DIR = os.environ.get(
    "AES_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "aes" / "files" / "aes"),
)

BATCH_SIZE = 1000

# All known token fields from AES schema
AES_TOKEN_FIELDS = (
    "_id", "written_form", "mdc", "lineCount", "lemmaID", "lemma_form",
    "cotext_translation", "zaehler", "hiero", "hiero_unicode", "hiero_inventar",
    "pos", "name", "number", "voice", "genus", "pronoun", "numerus",
    "epitheton", "morphology", "inflection", "adjective", "particle",
    "adverb", "verbalClass", "status",
)


def build_tla_lookup(session) -> dict[str, str]:
    """Build a mapping from TLA base32 text ID -> canonical_id."""
    rows = session.execute(
        sql_text("SELECT external_id, canonical_id FROM concordance WHERE external_system = 'tla'")
    ).fetchall()
    lookup = {}
    for ext_id, canon_id in rows:
        lookup[ext_id] = canon_id
    log.info("Loaded %d TLA -> canonical_id mappings", len(lookup))
    return lookup


def build_sentence_tokens(token_list: list[dict]) -> list[dict]:
    """Extract token data into clean dicts for JSONB storage."""
    tokens = []
    for tok in token_list:
        token_obj = {}
        for key in AES_TOKEN_FIELDS:
            if key in tok:
                token_obj[key] = tok[key]
        tokens.append(token_obj)
    return tokens


def build_transliteration(token_list: list[dict]) -> str | None:
    """Concatenate written_form fields into a sentence-level transliteration."""
    forms = [t.get("written_form", "") for t in token_list if t.get("written_form")]
    return " ".join(forms) if forms else None


def create_orphan_text(session, tla_text_id: str, entry: dict, existing_texts: set) -> str:
    """Create a new canonical text record for an AES sentence with no ORAEC match."""
    canonical_id = f"aeg_aes_{tla_text_id}"

    if canonical_id in existing_texts:
        return canonical_id

    text_record = TextRecord(
        canonical_id=canonical_id,
        conventional_name=None,
        script_type=None,
        period_label=entry.get("date"),
        findspot=entry.get("findspot"),
        text_type=None,
        completeness=None,
        extra_metadata={
            "aes_corpus": entry.get("corpus"),
            "aes_owner": entry.get("owner"),
            "aes_text_id": tla_text_id,
            "source": "aes",
        },
    )
    session.add(text_record)
    session.flush()
    existing_texts.add(canonical_id)

    # Also add TLA concordance entry for the orphan
    stmt = pg_insert(Concordance).values(
        canonical_id=canonical_id,
        external_system="tla",
        external_id=tla_text_id,
        relationship="exact_match",
    ).on_conflict_do_nothing(constraint="uq_concordance_system_ext_canonical")
    session.execute(stmt)

    return canonical_id


def import_aes_file(
    session,
    filepath: str,
    tla_lookup: dict[str, str],
    existing_sentences: set[str],
    existing_texts: set[str],
    stats: dict,
):
    """Import a single AES subcorpus JSON file."""
    fname = os.path.basename(filepath)
    log.info("Processing %s", fname)

    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, dict):
        log.warning("Unexpected format in %s (expected dict, got %s)", fname, type(data).__name__)
        return

    file_linked = 0
    file_orphaned = 0
    file_inserted = 0
    file_skipped = 0

    for sentence_id, entry in data.items():
        # Skip if already imported
        if sentence_id in existing_sentences:
            file_skipped += 1
            stats["sentences_skipped"] += 1
            continue

        tla_text_id = entry.get("text", "")
        if not tla_text_id:
            log.warning("Sentence %s has no text field, skipping", sentence_id)
            stats["errors"] += 1
            continue

        # Look up canonical_id via TLA concordance
        canonical_id = tla_lookup.get(tla_text_id)
        if canonical_id:
            file_linked += 1
            stats["linked"] += 1
        else:
            # Create orphan text record
            canonical_id = create_orphan_text(session, tla_text_id, entry, existing_texts)
            file_orphaned += 1
            stats["orphaned"] += 1
            # Add to tla_lookup so subsequent sentences for same text reuse it
            tla_lookup[tla_text_id] = canonical_id

        # Build sentence record
        token_list = entry.get("token", [])
        tokens = build_sentence_tokens(token_list) if token_list else None
        transliteration = build_transliteration(token_list)

        translation_text = entry.get("sentence_translation")
        translation = {"de": translation_text} if translation_text else None

        sentence = Sentence(
            canonical_id=canonical_id,
            sequence_num=None,  # AES doesn't provide sequence within text
            transliteration=transliteration,
            translation=translation,
            tokens=tokens,
            source="aes",
            source_id=sentence_id,
            source_detail={
                "corpus": entry.get("corpus"),
                "owner": entry.get("owner"),
                "date": entry.get("date"),
                "findspot": entry.get("findspot"),
                "tla_text_id": tla_text_id,
            },
            confidence="verified",
        )
        session.add(sentence)
        existing_sentences.add(sentence_id)
        file_inserted += 1
        stats["sentences_inserted"] += 1

        # Batch commit
        if stats["sentences_inserted"] % BATCH_SIZE == 0:
            session.commit()

    session.commit()

    log.info(
        "  %s: %d inserted, %d skipped, %d linked, %d orphaned",
        fname, file_inserted, file_skipped, file_linked, file_orphaned,
    )


def import_all(session, data_dir: str) -> dict:
    """Import all AES subcorpus JSON files."""
    # Find all AES JSON files
    aes_files = sorted(
        [f for f in os.listdir(data_dir) if f.startswith("_aes_") and f.endswith(".json")]
    )
    if not aes_files:
        log.error("No AES files found in %s", data_dir)
        return {}

    log.info("Found %d AES subcorpus files", len(aes_files))

    stats = {
        "sentences_inserted": 0,
        "sentences_skipped": 0,
        "linked": 0,
        "orphaned": 0,
        "texts_created": 0,
        "errors": 0,
    }

    # Build TLA lookup from existing concordance
    tla_lookup = build_tla_lookup(session)

    # Pre-load existing AES sentence IDs for idempotency
    rows = session.execute(
        sql_text("SELECT source_id FROM sentences WHERE source = 'aes'")
    ).fetchall()
    existing_sentences = set(r[0] for r in rows if r[0])
    log.info("Found %d existing AES sentences", len(existing_sentences))

    # Pre-load existing text canonical IDs
    rows = session.execute(
        sql_text("SELECT canonical_id FROM texts")
    ).fetchall()
    existing_texts = set(r[0] for r in rows)
    initial_text_count = len(existing_texts)

    t_start = time.time()

    for aes_file in aes_files:
        filepath = os.path.join(data_dir, aes_file)
        try:
            import_aes_file(
                session, filepath, tla_lookup,
                existing_sentences, existing_texts, stats,
            )
        except Exception:
            log.exception("Error processing %s", aes_file)
            session.rollback()
            stats["errors"] += 1

    # Count new texts created
    stats["texts_created"] = len(existing_texts) - initial_text_count

    elapsed = time.time() - t_start
    log.info(
        "AES import complete in %.1fs: sentences=%d (skipped=%d) linked=%d orphaned=%d "
        "texts_created=%d errors=%d",
        elapsed,
        stats["sentences_inserted"], stats["sentences_skipped"],
        stats["linked"], stats["orphaned"],
        stats["texts_created"], stats["errors"],
    )

    return stats


def print_summary(session):
    """Print final table counts."""
    log.info("=" * 60)
    log.info("FINAL TABLE COUNTS")
    log.info("=" * 60)

    for table in ("texts", "sentences", "concordance"):
        count = session.execute(sql_text(f"SELECT count(*) FROM {table}")).scalar()
        log.info("  %-30s %d", table, count)

    # Sentence breakdown by source
    rows = session.execute(
        sql_text("SELECT source, count(*) FROM sentences GROUP BY source ORDER BY count(*) DESC")
    ).fetchall()
    log.info("  Sentence breakdown by source:")
    for source, cnt in rows:
        log.info("    %-26s %d", source, cnt)


def main():
    log.info("AES Bulk Importer starting")
    log.info("Data directory: %s", DATA_DIR)

    if not os.path.isdir(DATA_DIR):
        log.error("Data directory not found: %s", DATA_DIR)
        log.error(
            "Run: git clone https://github.com/simondschweitzer/aes.git "
            "data/upstream/aes"
        )
        sys.exit(1)

    session = SessionLocal()

    try:
        stats = import_all(session, DATA_DIR)
        print_summary(session)

        # Report link rate
        total = stats.get("linked", 0) + stats.get("orphaned", 0)
        if total > 0:
            rate = 100 * stats["linked"] / total
            log.info("Link rate: %.1f%% (%d/%d linked to ORAEC)", rate, stats["linked"], total)

        log.info("AES import complete.")

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
