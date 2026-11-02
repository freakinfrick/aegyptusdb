#!/usr/bin/env python3
"""Export the full Aegyptus corpus to compressed JSONL files.

Produces one file per table:
  texts.jsonl.gz
  sentences.jsonl.gz
  concordance.jsonl.gz
  aliases.jsonl.gz
  representation_layers.jsonl.gz

Plus a manifest.json with row counts, export date, and corpus version.

Usage:
  PYTHONPATH=. python3 scripts/export_corpus.py [--output-dir ./export]
"""

import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.models import SessionLocal

BATCH_SIZE = 5000

TABLES = {
    "texts": {
        "query": "SELECT canonical_id, conventional_name, script_type, date_earliest, date_latest, period_label, findspot, current_location, text_type, completeness, shelfmarks, metadata, created_at, updated_at FROM texts ORDER BY canonical_id",
        "columns": ["canonical_id", "conventional_name", "script_type", "date_earliest", "date_latest", "period_label", "findspot", "current_location", "text_type", "completeness", "shelfmarks", "metadata", "created_at", "updated_at"],
    },
    "sentences": {
        "query": "SELECT id, canonical_id, sequence_num, transliteration, translation, tokens, source, source_id, source_detail, confidence, created_at FROM sentences ORDER BY canonical_id, id",
        "columns": ["id", "canonical_id", "sequence_num", "transliteration", "translation", "tokens", "source", "source_id", "source_detail", "confidence", "created_at"],
    },
    "concordance": {
        "query": "SELECT id, canonical_id, external_system, external_id, relationship FROM concordance ORDER BY canonical_id, id",
        "columns": ["id", "canonical_id", "external_system", "external_id", "relationship"],
    },
    "aliases": {
        "query": "SELECT id, canonical_id, alias_text, alias_normalized, alias_type, confidence FROM aliases ORDER BY canonical_id, id",
        "columns": ["id", "canonical_id", "alias_text", "alias_normalized", "alias_type", "confidence"],
    },
    "representation_layers": {
        "query": "SELECT id, canonical_id, layer_type, content, language, source, source_detail, confidence, created_at FROM representation_layers ORDER BY canonical_id, id",
        "columns": ["id", "canonical_id", "layer_type", "content", "language", "source", "source_detail", "confidence", "created_at"],
    },
}


def serialize_value(val):
    """Convert non-JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, (list, dict)):
        return val
    return val


def export_table(session, table_name: str, spec: dict, output_dir: Path) -> int:
    """Export one table to a gzipped JSONL file. Returns row count."""
    outpath = output_dir / f"{table_name}.jsonl.gz"
    columns = spec["columns"]
    query = spec["query"]

    count = 0
    with gzip.open(outpath, "wt", encoding="utf-8") as f:
        offset = 0
        while True:
            rows = session.execute(
                text(f"{query} LIMIT :limit OFFSET :offset"),
                {"limit": BATCH_SIZE, "offset": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                record = {}
                for i, col in enumerate(columns):
                    record[col] = serialize_value(row[i])
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                count += 1

            offset += BATCH_SIZE
            if len(rows) < BATCH_SIZE:
                break

    print(f"  {table_name}: {count:,} rows -> {outpath.name}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Export Aegyptus corpus to JSONL")
    parser.add_argument(
        "--output-dir", "-o",
        default=str(Path(__file__).resolve().parents[1] / "export"),
        help="Output directory (default: ./export)",
    )
    parser.add_argument(
        "--version", "-v",
        default=None,
        help="Corpus version tag (default: auto-detect from DB)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = SessionLocal()
    try:
        print(f"Exporting corpus to {output_dir}/")

        counts = {}
        for table_name, spec in TABLES.items():
            counts[table_name] = export_table(session, table_name, spec, output_dir)

        # Get version tag
        version = args.version
        if not version:
            row = session.execute(
                text("SELECT version_tag FROM corpus_versions ORDER BY id DESC LIMIT 1")
            ).fetchone()
            version = row[0] if row else "unknown"

        # Write manifest
        manifest = {
            "corpus": "aegyptus",
            "version": version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "jsonl.gz",
            "tables": counts,
            "total_rows": sum(counts.values()),
            "schema_version": "0.1.0",
        }
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\n  manifest.json written ({sum(counts.values()):,} total rows)")
        print(f"\nExport complete: {output_dir}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
