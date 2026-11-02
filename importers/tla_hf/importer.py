"""TLA Hugging Face dataset loader.

Imports 3 TLA datasets from the thesaurus-linguae-aegyptiae HF organization:
  - Earlier Egyptian (12,773 premium sentences)
  - Late Egyptian (3,606 premium sentences)
  - Demotic (13,383 premium sentences)

All rows are premium (verified). The HF datasets only contain the premium subset
of the full TLA corpus. Non-premium rows are not published on HF.

Each sentence gets a new canonical text record (grouped by date range).
Token-level data (lemmatization, UPOS, glossing) stored in JSONB tokens column.

Idempotent: skips sentences already imported (source='tla_hf', source_id=dataset:index).
"""

import logging
import os
import sys
import time

from sqlalchemy import text as sql_text

from core.models import (
    Sentence,
    SessionLocal,
    TextRecord,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tla_hf_importer")

BATCH_SIZE = 500

# Dataset configs: (HF dataset ID, short name, script type, has hieroglyphs)
DATASETS = [
    (
        "thesaurus-linguae-aegyptiae/tla-Earlier_Egyptian_original-v18-premium",
        "earlier_egyptian",
        "hieroglyphic",
        True,
    ),
    (
        "thesaurus-linguae-aegyptiae/tla-late_egyptian-v19-premium",
        "late_egyptian",
        "hieratic",
        True,
    ),
    (
        "thesaurus-linguae-aegyptiae/tla-demotic-v18-premium",
        "demotic",
        "demotic",
        False,
    ),
]


def parse_lemmatization(lemma_str: str) -> list[dict]:
    """Parse TLA lemmatization string into token dicts.

    Format: "90880|nd 51510|wdi 91901|r 10090|=s"
    Each entry is lemma_id|lemma_form, space-separated.
    """
    if not lemma_str:
        return []
    tokens = []
    for entry in lemma_str.split():
        parts = entry.split("|", 1)
        if len(parts) == 2:
            tokens.append({"lemma_id": parts[0], "lemma_form": parts[1]})
        else:
            tokens.append({"lemma_form": parts[0]})
    return tokens


def build_tokens(row: dict, has_hieroglyphs: bool) -> list[dict] | None:
    """Build token-level JSONB from HF row fields.

    Aligns lemmatization, UPOS, glossing, and hieroglyphs by token position.
    """
    lemma_str = row.get("lemmatization", "")
    upos_str = row.get("UPOS", "")
    glossing_str = row.get("glossing", "")
    hiero_str = row.get("hieroglyphs", "") if has_hieroglyphs else ""
    translit_str = row.get("transliteration", "")

    # Parse each field into lists
    lemma_tokens = parse_lemmatization(lemma_str)
    upos_list = upos_str.split() if upos_str else []
    glossing_list = glossing_str.split() if glossing_str else []
    hiero_list = hiero_str.split() if hiero_str else []
    translit_list = translit_str.split() if translit_str else []

    if not lemma_tokens and not upos_list and not translit_list:
        return None

    # Determine max token count (fields may differ in length)
    max_len = max(len(lemma_tokens), len(upos_list), len(translit_list), 1)

    tokens = []
    for i in range(max_len):
        tok = {}

        # Transliteration
        if i < len(translit_list):
            tok["written_form"] = translit_list[i]

        # Lemmatization
        if i < len(lemma_tokens):
            tok.update(lemma_tokens[i])

        # UPOS
        if i < len(upos_list):
            tok["upos"] = upos_list[i]

        # Glossing
        if i < len(glossing_list):
            tok["glossing"] = glossing_list[i]

        # Hieroglyphs
        if i < len(hiero_list):
            tok["hiero"] = hiero_list[i]

        if tok:
            tokens.append(tok)

    return tokens if tokens else None


def parse_date(val: str) -> int | None:
    """Parse a date string (may be BCE negative integer) to int."""
    if not val:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def import_dataset(session, hf_id: str, short_name: str, script_type: str, has_hieroglyphs: bool) -> dict:
    """Import a single TLA HF dataset."""
    from datasets import load_dataset

    log.info("Loading HF dataset: %s", hf_id)
    ds = load_dataset(hf_id)
    train = ds["train"]
    total_rows = len(train)
    log.info("  Rows: %d, Columns: %s", total_rows, train.column_names)

    # Extract version from dataset ID (e.g., "v18" or "v19")
    version = None
    for part in hf_id.split("-"):
        if part.startswith("v") and part[1:].isdigit():
            version = part
            break

    stats = {
        "inserted": 0,
        "skipped": 0,
        "texts_created": 0,
        "errors": 0,
    }

    # Pre-load existing sentence source_ids for this dataset
    rows = session.execute(
        sql_text(
            "SELECT source_id FROM sentences WHERE source = 'tla_hf' "
            "AND source_id LIKE :prefix"
        ),
        {"prefix": f"{short_name}:%"},
    ).fetchall()
    existing_ids = set(r[0] for r in rows)
    log.info("  Found %d existing TLA HF sentences for %s", len(existing_ids), short_name)

    # Pre-load existing text canonical IDs
    existing_texts = set(
        r[0] for r in session.execute(
            sql_text("SELECT canonical_id FROM texts")
        ).fetchall()
    )

    # Group by date range: no text-level IDs exist in the HF dataset,
    # so (dateNotBefore, dateNotAfter) is the best available grouping key.
    text_cache = {}  # (dateNotBefore, dateNotAfter) -> canonical_id

    t_start = time.time()

    for idx in range(total_rows):
        row = train[idx]
        source_id = f"{short_name}:{idx}"

        if source_id in existing_ids:
            stats["skipped"] += 1
            continue

        # Create or reuse text record
        date_before = row.get("dateNotBefore", "")
        date_after = row.get("dateNotAfter", "")
        canonical_id = f"aeg_tla_hf_{short_name}_{idx}"

        if canonical_id not in existing_texts:
            text_record = TextRecord(
                canonical_id=canonical_id,
                script_type=script_type,
                date_earliest=parse_date(date_before),
                date_latest=parse_date(date_after),
                extra_metadata={
                    "source": "tla_hf",
                    "dataset": hf_id,
                    "version": version,
                    "row_index": idx,
                    "authors": row.get("authors"),
                },
            )
            session.add(text_record)
            session.flush()
            existing_texts.add(canonical_id)
            stats["texts_created"] += 1

        # Build tokens JSONB
        tokens = build_tokens(row, has_hieroglyphs)

        # Translation
        translation_text = row.get("translation", "")
        translation = {"de": translation_text} if translation_text else None

        # Build sentence
        sentence = Sentence(
            canonical_id=canonical_id,
            sequence_num=1,  # One sentence per text record
            transliteration=row.get("transliteration") or None,
            translation=translation,
            tokens=tokens,
            source="tla_hf",
            source_id=source_id,
            source_detail={
                "dataset": hf_id,
                "version": version,
                "short_name": short_name,
                "row_index": idx,
                "dateNotBefore": date_before,
                "dateNotAfter": date_after,
                "authors": row.get("authors"),
            },
            confidence="verified",  # All HF rows are premium
        )
        session.add(sentence)
        existing_ids.add(source_id)
        stats["inserted"] += 1

        if stats["inserted"] % BATCH_SIZE == 0:
            session.commit()
            if stats["inserted"] % 5000 == 0:
                elapsed = time.time() - t_start
                rate = stats["inserted"] / elapsed if elapsed > 0 else 0
                log.info(
                    "  Progress: %d/%d (%.0f/s) inserted=%d skipped=%d",
                    idx + 1, total_rows, rate,
                    stats["inserted"], stats["skipped"],
                )

    session.commit()

    elapsed = time.time() - t_start
    log.info(
        "  %s complete in %.1fs: inserted=%d skipped=%d texts=%d errors=%d",
        short_name, elapsed,
        stats["inserted"], stats["skipped"],
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

    # TLA HF breakdown by dataset
    rows = session.execute(
        sql_text(
            "SELECT "
            "  CASE "
            "    WHEN source_id LIKE 'earlier_egyptian:%' THEN 'Earlier Egyptian' "
            "    WHEN source_id LIKE 'late_egyptian:%' THEN 'Late Egyptian' "
            "    WHEN source_id LIKE 'demotic:%' THEN 'Demotic' "
            "    ELSE 'unknown' "
            "  END as dataset, "
            "  count(*) "
            "FROM sentences WHERE source = 'tla_hf' "
            "GROUP BY 1 ORDER BY 2 DESC"
        )
    ).fetchall()
    if rows:
        log.info("  TLA HF breakdown:")
        for ds_name, cnt in rows:
            log.info("    %-26s %d", ds_name, cnt)


def main():
    log.info("TLA HF Dataset Loader starting")

    session = SessionLocal()

    try:
        all_stats = {}
        for hf_id, short_name, script_type, has_hiero in DATASETS:
            log.info("=" * 60)
            log.info("Importing %s", short_name)
            log.info("=" * 60)
            stats = import_dataset(session, hf_id, short_name, script_type, has_hiero)
            all_stats[short_name] = stats

        print_summary(session)

        # Summary
        total_inserted = sum(s["inserted"] for s in all_stats.values())
        total_texts = sum(s["texts_created"] for s in all_stats.values())
        log.info(
            "TLA HF import complete: %d sentences, %d text records across %d datasets",
            total_inserted, total_texts, len(all_stats),
        )

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
