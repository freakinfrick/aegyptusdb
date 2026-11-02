#!/usr/bin/env python3
"""Reconstruct the Aegyptus database from a JSONL corpus export.

Reads the files produced by export_corpus.py:
  texts.jsonl.gz, sentences.jsonl.gz, concordance.jsonl.gz,
  aliases.jsonl.gz, representation_layers.jsonl.gz, manifest.json

Import order matters due to foreign key constraints:
  1. texts (no FK dependencies)
  2. sentences, concordance, aliases, representation_layers (FK -> texts)

Usage:
  PYTHONPATH=. python3 scripts/import_corpus.py ./export/
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.models import SessionLocal

BATCH_SIZE = 2000

# Import order: texts first, then tables with FK -> texts
IMPORT_ORDER = [
    "texts",
    "sentences",
    "concordance",
    "aliases",
    "representation_layers",
]

# Column mappings (JSONL key -> DB column). The 'metadata' column uses
# 'metadata' as the DB column name even though the SQLAlchemy model maps
# it to extra_metadata.
TABLE_COLUMNS = {
    "texts": ["canonical_id", "conventional_name", "script_type", "date_earliest", "date_latest", "period_label", "findspot", "current_location", "text_type", "completeness", "shelfmarks", "metadata", "created_at", "updated_at"],
    "sentences": ["id", "canonical_id", "sequence_num", "transliteration", "translation", "tokens", "source", "source_id", "source_detail", "confidence", "created_at"],
    "concordance": ["id", "canonical_id", "external_system", "external_id", "relationship"],
    "aliases": ["id", "canonical_id", "alias_text", "alias_normalized", "alias_type", "confidence"],
    "representation_layers": ["id", "canonical_id", "layer_type", "content", "language", "source", "source_detail", "confidence", "created_at"],
}


def import_table(session, table_name: str, input_dir: Path) -> int:
    """Import one table from a gzipped JSONL file. Returns row count."""
    filepath = input_dir / f"{table_name}.jsonl.gz"
    if not filepath.exists():
        print(f"  WARNING: {filepath} not found, skipping")
        return 0

    columns = TABLE_COLUMNS[table_name]
    placeholders = ", ".join(f":{c}" for c in columns)
    col_list = ", ".join(columns)
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    count = 0
    batch = []

    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            # Map JSON keys to column params
            params = {}
            for col in columns:
                val = record.get(col)
                # JSONB columns need to stay as Python dicts (psycopg2 handles this)
                if val is not None and col in ("shelfmarks", "metadata", "translation", "tokens", "content", "source_detail"):
                    if isinstance(val, str):
                        val = json.loads(val)
                params[col] = val

            batch.append(params)

            if len(batch) >= BATCH_SIZE:
                session.execute(text(insert_sql), batch)
                session.commit()
                count += len(batch)
                batch = []

    if batch:
        session.execute(text(insert_sql), batch)
        session.commit()
        count += len(batch)

    print(f"  {table_name}: {count:,} rows imported")
    return count


def main():
    parser = argparse.ArgumentParser(description="Import Aegyptus corpus from JSONL export")
    parser.add_argument("input_dir", help="Directory containing the JSONL export files")
    parser.add_argument("--truncate", action="store_true", help="Truncate tables before import (DESTRUCTIVE)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: {input_dir} does not exist")
        sys.exit(1)

    manifest_path = input_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        print(f"Importing corpus: {manifest.get('version', 'unknown')} "
              f"({manifest.get('total_rows', '?'):,} total rows)")
    else:
        print("WARNING: No manifest.json found")

    session = SessionLocal()
    try:
        if args.truncate:
            print("Truncating tables (CASCADE)...")
            for table in reversed(IMPORT_ORDER):
                session.execute(text(f"TRUNCATE {table} CASCADE"))
            session.commit()
            print("Tables truncated.")

        total = 0
        for table_name in IMPORT_ORDER:
            total += import_table(session, table_name, input_dir)

        print(f"\nImport complete: {total:,} total rows")

    finally:
        session.close()


if __name__ == "__main__":
    main()
