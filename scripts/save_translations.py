#!/usr/bin/env python3
"""Save agent-produced translations to sentence rows.

Reads JSON from stdin: [{"id": 12345, "en": "translation text", "confidence": "HIGH"}, ...]

Usage:
    cat translations.json | python scripts/save_translations.py --model "claude-haiku-4-5"
"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="claude-haiku-4-5-20251001")
    p.add_argument("--input", type=str, help="JSON file (default: stdin)")
    args = p.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text())
    else:
        data = json.load(sys.stdin)

    from sqlalchemy.orm.attributes import flag_modified
    from core.models import Sentence, SessionLocal
    session = SessionLocal()

    now = datetime.now(timezone.utc).isoformat()
    saved = 0
    skipped = 0

    # Build lookup: id → (en, confidence)
    to_save = {}
    for item in data:
        sid = item["id"]
        en = (item.get("en") or "").strip()
        if not en or len(en) < 2:
            skipped += 1
            continue
        to_save[sid] = (en, item.get("confidence", "MEDIUM"))

    # Bulk fetch all sentences in one query
    sentences = session.query(Sentence).filter(Sentence.id.in_(to_save.keys())).all()
    by_id = {s.id: s for s in sentences}

    for sid, (en, conf) in to_save.items():
        s = by_id.get(sid)
        if not s:
            skipped += 1
            continue

        existing = dict(s.translation or {})
        if "en" in existing:
            skipped += 1
            continue

        existing["en"] = en
        s.translation = dict(existing)
        flag_modified(s, "translation")

        meta = dict(s.source_detail or {})
        meta["en_translation"] = {
            "source": "ml_draft",
            "model": args.model,
            "confidence": "low",
            "needs_review": True,
            "confidence_llm": conf,
            "translated_at": now,
            "method": "agent_transliteration_to_en",
        }
        s.source_detail = meta
        flag_modified(s, "source_detail")
        saved += 1

    session.commit()
    session.close()
    print(json.dumps({"saved": saved, "skipped": skipped, "total": len(data)}))

if __name__ == "__main__":
    main()
