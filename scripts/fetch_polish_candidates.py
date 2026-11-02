#!/usr/bin/env python3
"""Fetch mechanical translations needing polish as JSON.

Usage:
    python scripts/fetch_polish_candidates.py --limit 500 --min-id 1 --max-id 999999
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-id", type=int, default=1)
    p.add_argument("--max-id", type=int, default=999999)
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--min-tokens", type=int, default=6)
    args = p.parse_args()

    from sqlalchemy import text as sa_text
    from core.models import SessionLocal
    session = SessionLocal()

    rows = session.execute(sa_text("""
        SELECT s.id, s.translation->>'de' AS german,
               s.translation->>'en' AS mechanical_en
        FROM sentences s
        WHERE s.id >= :min_id AND s.id <= :max_id
          AND s.translation->'_rosetta'->>'source' = 'mechanical'
          AND s.tokens IS NOT NULL
          AND jsonb_typeof(s.tokens) = 'array'
        ORDER BY s.id
        LIMIT :limit
    """), {"min_id": args.min_id, "max_id": args.max_id, "limit": args.limit}).fetchall()
    session.close()

    out = [{"id": r[0], "german": r[1] or "", "mechanical": r[2] or ""} for r in rows]
    json.dump(out, sys.stdout, ensure_ascii=False)

if __name__ == "__main__":
    main()
