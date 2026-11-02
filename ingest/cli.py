"""Ad-hoc ingestion CLI implementation.

Supports plain text, JSON, and CSV input.
Creates canonical records with aeg_adhoc_{content_hash} IDs.
All records tagged source='ad_hoc', confidence='unreviewed'.
"""

import argparse
import csv
import hashlib
import io
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import (
    Alias,
    Concordance,
    RepresentationLayer,
    Sentence,
    SessionLocal,
    TextRecord,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

VALID_SCRIPT_TYPES = {"hieroglyphic", "hieratic", "demotic", "coptic", "greek", "multiple"}


def content_hash(content: str) -> str:
    """Generate a stable hash from content for canonical_id."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def detect_format(filepath: str) -> str:
    """Detect file format from extension."""
    suffix = Path(filepath).suffix.lower()
    if suffix == ".json":
        return "json"
    elif suffix == ".csv":
        return "csv"
    else:
        return "text"


def parse_ids(ids_str: str) -> list[tuple[str, str]]:
    """Parse --ids flag: 'tla:ABC123,tm:12345' -> [('tla', 'ABC123'), ('tm', '12345')]"""
    if not ids_str:
        return []

    pairs = []
    for part in ids_str.split(","):
        part = part.strip()
        if ":" not in part:
            log.warning("Skipping malformed ID: %s (expected format: system:id)", part)
            continue
        system, ext_id = part.split(":", 1)
        pairs.append((system.strip(), ext_id.strip()))
    return pairs


def ingest_text_file(filepath: str, name: str | None, script_type: str | None,
                     source: str | None, ids: list[tuple[str, str]]) -> dict:
    """Ingest a plain text file as a single canonical record."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        log.error("File is empty: %s", filepath)
        sys.exit(1)

    chash = content_hash(content)
    canonical_id = f"aeg_adhoc_{chash}"

    session = SessionLocal()
    try:
        # Check if already exists
        existing = session.execute(
            sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
            {"cid": canonical_id},
        ).fetchone()

        if existing:
            log.info("Record already exists: %s (idempotent skip)", canonical_id)
            return {"canonical_id": canonical_id, "status": "exists"}

        # Create text record
        text_record = TextRecord(
            canonical_id=canonical_id,
            conventional_name=name,
            script_type=script_type,
            extra_metadata={
                "source": source or "ad_hoc",
                "original_filename": Path(filepath).name,
                "content_hash": chash,
                "ingestion_method": "cli",
            },
        )
        session.add(text_record)
        session.flush()

        # Create representation layer (the text content itself)
        layer = RepresentationLayer(
            canonical_id=canonical_id,
            layer_type="transliteration" if script_type else "text",
            content={"text": content},
            language=None,
            source="ad_hoc",
            source_detail={"filename": Path(filepath).name},
            confidence="unreviewed",
        )
        session.add(layer)

        # Create sentences (split on double newlines or single newlines)
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        for seq, line in enumerate(lines, start=1):
            sentence = Sentence(
                canonical_id=canonical_id,
                sequence_num=seq,
                transliteration=line,
                source="ad_hoc",
                source_id=f"adhoc_{chash}_{seq}",
                confidence="unreviewed",
            )
            session.add(sentence)

        # Add concordance links from --ids
        for system, ext_id in ids:
            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system=system,
                external_id=ext_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(
                constraint="uq_concordance_system_ext_canonical"
            )
            session.execute(stmt)

        # Add alias if name provided
        if name:
            from core.concordance.normalizer import normalize_conventional_name
            stmt = pg_insert(Alias).values(
                canonical_id=canonical_id,
                alias_text=name,
                alias_normalized=normalize_conventional_name(name),
                alias_type="conventional_name",
                confidence="manual",
            ).on_conflict_do_nothing(
                constraint="uq_aliases_text_canonical"
            )
            session.execute(stmt)

        session.commit()

        result = {
            "canonical_id": canonical_id,
            "status": "created",
            "sentences": len(lines),
            "ids_linked": len(ids),
        }
        log.info("Created: %s (%d sentences, %d external links)", canonical_id, len(lines), len(ids))
        return result

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ingest_json_file(filepath: str, name: str | None, script_type: str | None,
                     source: str | None, ids: list[tuple[str, str]]) -> dict:
    """Ingest a JSON file. Supports single record or array of records."""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # Normalize to list
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        log.error("JSON must be an object or array of objects")
        sys.exit(1)

    session = SessionLocal()
    results = []

    try:
        for record in records:
            # Use provided name or extract from record
            rec_name = name or record.get("name") or record.get("title") or record.get("conventional_name")
            rec_script = script_type or record.get("script_type")
            rec_text = record.get("text") or record.get("content") or record.get("transliteration") or json.dumps(record)

            chash = content_hash(rec_text)
            canonical_id = f"aeg_adhoc_{chash}"

            existing = session.execute(
                sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
                {"cid": canonical_id},
            ).fetchone()

            if existing:
                results.append({"canonical_id": canonical_id, "status": "exists"})
                continue

            text_record = TextRecord(
                canonical_id=canonical_id,
                conventional_name=rec_name,
                script_type=rec_script if rec_script in VALID_SCRIPT_TYPES else None,
                extra_metadata={
                    "source": source or "ad_hoc",
                    "original_filename": Path(filepath).name,
                    "content_hash": chash,
                    "ingestion_method": "cli",
                    "original_record": record,
                },
            )
            session.add(text_record)
            session.flush()

            layer = RepresentationLayer(
                canonical_id=canonical_id,
                layer_type="transliteration" if rec_script else "text",
                content=record,
                language=record.get("language"),
                source="ad_hoc",
                source_detail={"filename": Path(filepath).name},
                confidence="unreviewed",
            )
            session.add(layer)

            # IDs from record itself
            rec_ids = list(ids)
            for sys_key in ("tla_id", "tm_id", "trismegistos_id", "oraec_id"):
                val = record.get(sys_key)
                if val:
                    system = sys_key.replace("_id", "")
                    rec_ids.append((system, str(val)))

            for system, ext_id in rec_ids:
                stmt = pg_insert(Concordance).values(
                    canonical_id=canonical_id,
                    external_system=system,
                    external_id=ext_id,
                    relationship="exact_match",
                ).on_conflict_do_nothing(
                    constraint="uq_concordance_system_ext_canonical"
                )
                session.execute(stmt)

            if rec_name:
                from core.concordance.normalizer import normalize_conventional_name
                stmt = pg_insert(Alias).values(
                    canonical_id=canonical_id,
                    alias_text=rec_name,
                    alias_normalized=normalize_conventional_name(rec_name),
                    alias_type="conventional_name",
                    confidence="manual",
                ).on_conflict_do_nothing(
                    constraint="uq_aliases_text_canonical"
                )
                session.execute(stmt)

            results.append({"canonical_id": canonical_id, "status": "created"})

        session.commit()

        created = sum(1 for r in results if r["status"] == "created")
        existed = sum(1 for r in results if r["status"] == "exists")
        log.info("JSON import: %d created, %d already existed", created, existed)
        return {"records": results, "created": created, "existed": existed}

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ingest_csv_file(filepath: str, name: str | None, script_type: str | None,
                    source: str | None, ids: list[tuple[str, str]]) -> dict:
    """Ingest a CSV file. Each row becomes a separate canonical record."""
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.error("CSV file is empty: %s", filepath)
        sys.exit(1)

    session = SessionLocal()
    results = []

    try:
        for row in rows:
            rec_name = name or row.get("name") or row.get("title") or row.get("conventional_name")
            rec_script = script_type or row.get("script_type")
            rec_text = row.get("text") or row.get("content") or row.get("transliteration") or str(row)

            chash = content_hash(rec_text)
            canonical_id = f"aeg_adhoc_{chash}"

            existing = session.execute(
                sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
                {"cid": canonical_id},
            ).fetchone()

            if existing:
                results.append({"canonical_id": canonical_id, "status": "exists"})
                continue

            text_record = TextRecord(
                canonical_id=canonical_id,
                conventional_name=rec_name,
                script_type=rec_script if rec_script in VALID_SCRIPT_TYPES else None,
                extra_metadata={
                    "source": source or "ad_hoc",
                    "original_filename": Path(filepath).name,
                    "content_hash": chash,
                    "ingestion_method": "cli",
                },
            )
            session.add(text_record)
            session.flush()

            layer = RepresentationLayer(
                canonical_id=canonical_id,
                layer_type="transliteration" if rec_script else "text",
                content=dict(row),
                language=row.get("language"),
                source="ad_hoc",
                source_detail={"filename": Path(filepath).name},
                confidence="unreviewed",
            )
            session.add(layer)

            rec_ids = list(ids)
            for sys_key in ("tla_id", "tm_id", "trismegistos_id", "oraec_id"):
                val = row.get(sys_key)
                if val:
                    system = sys_key.replace("_id", "")
                    rec_ids.append((system, str(val)))

            for system, ext_id in rec_ids:
                stmt = pg_insert(Concordance).values(
                    canonical_id=canonical_id,
                    external_system=system,
                    external_id=ext_id,
                    relationship="exact_match",
                ).on_conflict_do_nothing(
                    constraint="uq_concordance_system_ext_canonical"
                )
                session.execute(stmt)

            results.append({"canonical_id": canonical_id, "status": "created"})

        session.commit()

        created = sum(1 for r in results if r["status"] == "created")
        existed = sum(1 for r in results if r["status"] == "exists")
        log.info("CSV import: %d created, %d already existed", created, existed)
        return {"records": results, "created": created, "existed": existed}

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ad-hoc text ingestion for Aegyptus",
        prog="python -m ingest",
    )
    parser.add_argument("file", help="Input file (text, JSON, or CSV)")
    parser.add_argument("--name", help="Conventional name for the text")
    parser.add_argument(
        "--script-type",
        choices=sorted(VALID_SCRIPT_TYPES),
        help="Script type classification",
    )
    parser.add_argument("--source", help="Source attribution (default: ad_hoc)")
    parser.add_argument(
        "--ids",
        help="External IDs to link: 'tla:XXXXX,tm:YYYYY'",
    )

    args = parser.parse_args()

    filepath = args.file
    if not Path(filepath).exists():
        log.error("File not found: %s", filepath)
        sys.exit(1)

    ids = parse_ids(args.ids) if args.ids else []
    fmt = detect_format(filepath)

    log.info("Ingesting %s (format=%s, name=%s, script=%s, source=%s, ids=%s)",
             filepath, fmt, args.name, args.script_type, args.source, ids)

    if fmt == "json":
        result = ingest_json_file(filepath, args.name, args.script_type, args.source, ids)
    elif fmt == "csv":
        result = ingest_csv_file(filepath, args.name, args.script_type, args.source, ids)
    else:
        result = ingest_text_file(filepath, args.name, args.script_type, args.source, ids)

    print(json.dumps(result, indent=2))
