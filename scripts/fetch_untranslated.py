#!/usr/bin/env python3
"""Fetch untranslated sentences as JSON for agent translation.

Usage:
    python scripts/fetch_untranslated.py --source aes --min-id 101800 --max-id 122000 --limit 50
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--min-id", type=int, default=1)
    p.add_argument("--max-id", type=int, default=999999)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-tokens", type=int, default=1)
    args = p.parse_args()

    from sqlalchemy import text as sa_text
    from core.models import SessionLocal
    session = SessionLocal()

    rows = session.execute(sa_text("""
        SELECT s.id, s.canonical_id, s.transliteration,
               s.translation->>'de' AS german,
               CASE WHEN s.tokens IS NOT NULL AND jsonb_typeof(s.tokens) = 'array'
                    THEN jsonb_array_length(s.tokens) ELSE 0 END AS tok_count
        FROM sentences s
        WHERE s.id >= :min_id AND s.id <= :max_id
        AND s.source = :source
        AND s.transliteration IS NOT NULL
        AND (s.translation IS NULL OR NOT (s.translation ? 'en'))
        AND CASE WHEN s.tokens IS NOT NULL AND jsonb_typeof(s.tokens) = 'array'
                 THEN jsonb_array_length(s.tokens) ELSE 0 END >= :min_tokens
        ORDER BY CASE WHEN s.tokens IS NOT NULL AND jsonb_typeof(s.tokens) = 'array'
                      THEN jsonb_array_length(s.tokens) ELSE 0 END DESC
        LIMIT :limit
    """), vars(args)).fetchall()
    session.close()

    out = [{"id": r[0], "canonical_id": r[1], "transliteration": r[2],
            "german": r[3], "tok_count": r[4]} for r in rows]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
