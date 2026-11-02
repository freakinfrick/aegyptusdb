#!/usr/bin/env python3
"""Tag a corpus version snapshot.

Inserts a row into the corpus_versions table with current counts
and optional description.

Usage:
  PYTHONPATH=. python3 scripts/tag_version.py v0.2.0-phase4 --description "Phase 4 complete"
  PYTHONPATH=. python3 scripts/tag_version.py v0.1.1-patch --description "Fixed papyri import"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.models import CorpusVersion, SessionLocal


def get_counts(session) -> dict[str, int]:
    """Get current row counts for all corpus tables."""
    tables = {
        "text_count": "texts",
        "sentence_count": "sentences",
        "layer_count": "representation_layers",
        "concordance_count": "concordance",
        "alias_count": "aliases",
    }
    counts = {}
    for key, table in tables.items():
        val = session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        counts[key] = val or 0
    return counts


def get_source_breakdown(session) -> dict:
    """Get breakdown of texts by source prefix."""
    rows = session.execute(text(
        "SELECT split_part(canonical_id, '_', 2) AS src, count(*) "
        "FROM texts GROUP BY src ORDER BY count(*) DESC"
    )).fetchall()
    return {r[0]: r[1] for r in rows}


def main():
    parser = argparse.ArgumentParser(description="Tag a corpus version")
    parser.add_argument("version_tag", help="Version tag (e.g., v0.2.0-phase4)")
    parser.add_argument("--description", "-d", default=None, help="Version description")
    parser.add_argument("--export-key", default=None, help="MinIO export key if applicable")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        # Check for duplicate
        existing = session.execute(
            text("SELECT id FROM corpus_versions WHERE version_tag = :tag"),
            {"tag": args.version_tag},
        ).fetchone()

        if existing:
            print(f"Error: Version '{args.version_tag}' already exists (id={existing[0]})")
            sys.exit(1)

        counts = get_counts(session)
        sources = get_source_breakdown(session)

        version = CorpusVersion(
            version_tag=args.version_tag,
            description=args.description,
            text_count=counts["text_count"],
            sentence_count=counts["sentence_count"],
            layer_count=counts["layer_count"],
            concordance_count=counts["concordance_count"],
            alias_count=counts["alias_count"],
            export_key=args.export_key,
            extra_metadata={
                "tagged_at": datetime.now(timezone.utc).isoformat(),
                "texts_by_source": sources,
                "gap_count": session.execute(text("SELECT count(*) FROM gaps")).scalar() or 0,
            },
        )
        session.add(version)
        session.commit()

        print(f"Tagged corpus version: {args.version_tag}")
        print(f"  texts:        {counts['text_count']:,}")
        print(f"  sentences:    {counts['sentence_count']:,}")
        print(f"  layers:       {counts['layer_count']:,}")
        print(f"  concordance:  {counts['concordance_count']:,}")
        print(f"  aliases:      {counts['alias_count']:,}")
        print(f"  sources:      {json.dumps(sources)}")
        if args.description:
            print(f"  description:  {args.description}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
