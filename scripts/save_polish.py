#!/usr/bin/env python3
"""Save polished translations — overwrites mechanical EN with fluent EN.

Reads JSON: [{"id": 12345, "en": "fluent translation"}, ...]

Usage:
    python scripts/save_polish.py --input /tmp/parsed.json
"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = p.parse_args()

    data = json.loads(Path(args.input).read_text())
    if not data:
        print(json.dumps({"saved": 0, "skipped": 0}))
        return

    from sqlalchemy import text as sa_text
    from core.models import SessionLocal
    session = SessionLocal()
    now = datetime.now(timezone.utc).isoformat()
    saved = 0
    skipped = 0

    for item in data:
        sid = item.get("id")
        en = (item.get("en") or "").strip()
        if not en or len(en) < 3 or not sid:
            skipped += 1
            continue

        row = session.execute(
            sa_text("SELECT translation FROM sentences WHERE id = :sid"),
            {"sid": sid},
        ).fetchone()
        if not row:
            skipped += 1
            continue

        translation = row[0] if isinstance(row[0], dict) else {}

        # Only overwrite if currently mechanical
        rosetta = translation.get("_rosetta", {})
        if rosetta.get("source") != "mechanical":
            skipped += 1
            continue

        translation["en"] = en
        rosetta["source"] = "haiku_polish"
        rosetta["model"] = args.model
        rosetta["method"] = "mechanical+haiku_lean"
        rosetta["tier"] = "T0.5"
        rosetta["polished_at"] = now
        rosetta["needs_review"] = False
        translation["_rosetta"] = rosetta

        session.execute(
            sa_text("UPDATE sentences SET translation = :trans WHERE id = :sid"),
            {"sid": sid, "trans": json.dumps(translation, ensure_ascii=False)},
        )
        saved += 1

    session.commit()
    session.close()
    print(json.dumps({"saved": saved, "skipped": skipped, "total": len(data)}))

if __name__ == "__main__":
    main()
