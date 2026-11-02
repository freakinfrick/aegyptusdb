#!/usr/bin/env python3
"""Batch translate Egyptian transliterations via Gemini 3.1 Flash Lite (free tier).

Rate limits: 15 RPM, 250K TPM, 500 RPD (free tier).
Strategy: batch N sentences per request (transliteration→English).

For RAMSES and other sentences with no German translation — transliteration only.

Usage:
    GOOGLE_AI_API_KEY=... python scripts/gemini_translate_translit.py --limit 25000
    GOOGLE_AI_API_KEY=... python scripts/gemini_translate_translit.py --limit 25000 --dry-run
"""
import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = "gemini-3.1-flash-lite-preview"

# Rate limits (free tier): 15 RPM, 250K TPM, 500 RPD
RPM = 11  # 75% of 15 RPM cap
DELAY = 60.0 / RPM  # ~5.5s between requests
BATCH_SIZE = 50  # sentences per request


def find_translit_sentences(session, source=None, limit=25000, min_tokens=1, min_id=1, max_id=999999):
    """Find untranslated sentences with transliteration but no German."""
    from sqlalchemy import text as sa_text

    query = """
        SELECT s.id, s.transliteration, s.canonical_id,
               CASE WHEN s.tokens IS NOT NULL AND jsonb_typeof(s.tokens) = 'array'
                    THEN jsonb_array_length(s.tokens) ELSE 0 END AS tok_count
        FROM sentences s
        WHERE s.transliteration IS NOT NULL
        AND NOT (s.translation ? 'en')
        AND (s.translation IS NULL OR NOT (s.translation ? 'de'))
        AND s.id >= :min_id AND s.id <= :max_id
    """
    params = {"limit": limit, "min_tokens": min_tokens, "min_id": min_id, "max_id": max_id}
    if source:
        query += " AND s.source = :source"
        params["source"] = source

    query += """
        AND CASE WHEN s.tokens IS NOT NULL AND jsonb_typeof(s.tokens) = 'array'
                 THEN jsonb_array_length(s.tokens) ELSE 0 END >= :min_tokens
        ORDER BY length(s.transliteration) DESC
        LIMIT :limit
    """
    rows = session.execute(sa_text(query), params).fetchall()
    return [{"id": r[0], "transliteration": r[1], "canonical_id": r[2], "tok_count": r[3]} for r in rows]


def translate_batch(sentences: list[dict], client: httpx.Client) -> list[dict]:
    """Send a batch of transliterations to Gemini for Egyptian→EN translation."""
    lines = []
    for i, s in enumerate(sentences):
        lines.append(f"{i+1}. {s['transliteration']}")
    numbered = "\n".join(lines)

    prompt = f"""You are an expert Egyptologist. Translate each numbered ancient Egyptian transliteration to English. Output ONLY a JSON array.

{numbered}

These are Manuel de Codage / RAMSES-style transliterations of hieroglyphic text.
Key patterns: iw=f (he is), r (to), m (in/from), n (for/of), Hr (upon), Dd (say), =f/=s/=sn (he/she/they).
Names: Wsir=Osiris, Hr=Horus, Ra=Re, Imn=Amun, DHwty=Thoth, Ast=Isis, Inpw=Anubis, PtH=Ptah.
LACUNA = damaged text, use [...] in translation.

Output format (no markdown, no explanation, ONLY the JSON array):
[{{"n":1,"en":"English translation","c":"HIGH"}},{{"n":2,"en":"...","c":"MEDIUM"}},...]

c = HIGH|MEDIUM|LOW based on certainty. Output ONLY valid JSON."""

    try:
        resp = client.post(
            BASE_URL,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 16384,
                "temperature": 0.3,
            },
        )

        if resp.status_code == 429:
            print("  RATE LIMITED — waiting 60s", file=sys.stderr)
            time.sleep(60)
            return []

        if resp.status_code != 200:
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return []

        raw = resp.json()["choices"][0]["message"]["content"]
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        raw = raw.strip()

        parsed = json.loads(raw)
        results = []
        for item in parsed:
            idx = item.get("n", 0) - 1
            if 0 <= idx < len(sentences):
                en = item.get("en", "").strip()
                if en and len(en) >= 2:
                    results.append({
                        "id": sentences[idx]["id"],
                        "canonical_id": sentences[idx]["canonical_id"],
                        "translation": en,
                        "confidence": item.get("c", "MEDIUM"),
                    })
        return results

    except json.JSONDecodeError:
        print(f"  JSON parse error on response", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []


def save_translations(results: list[dict], session) -> int:
    """Save translations to sentence rows."""
    from sqlalchemy.orm.attributes import flag_modified
    from core.models import Sentence

    saved = 0
    now = datetime.now(timezone.utc).isoformat()

    for r in results:
        sentence = session.get(Sentence, r["id"])
        if not sentence:
            continue

        existing = sentence.translation or {}
        if "en" in existing:
            continue

        existing["en"] = r["translation"]
        sentence.translation = dict(existing)
        flag_modified(sentence, "translation")

        meta = dict(sentence.source_detail or {})
        meta["en_translation"] = {
            "source": "ml_draft",
            "model": MODEL,
            "confidence": "low",
            "needs_review": True,
            "confidence_llm": r["confidence"],
            "translated_at": now,
            "method": "gemini_translit_to_en",
        }
        sentence.source_detail = meta
        flag_modified(sentence, "source_detail")
        saved += 1

    return saved


def main():
    parser = argparse.ArgumentParser(description="Translate transliterations via Gemini (translit→EN)")
    parser.add_argument("--limit", type=int, default=25000, help="Max sentences to translate")
    parser.add_argument("--source", type=str, help="Filter by source (ramses, oraec, etc.)")
    parser.add_argument("--min-tokens", type=int, default=1, help="Min token count (default: 1)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Sentences per API call")
    parser.add_argument("--commit-every", type=int, default=200, help="Commit every N saves")
    parser.add_argument("--min-id", type=int, default=1, help="Min sentence ID")
    parser.add_argument("--max-id", type=int, default=999999, help="Max sentence ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent")
    args = parser.parse_args()

    if not API_KEY and not args.dry_run:
        print("Set GOOGLE_AI_API_KEY (or use --dry-run)", file=sys.stderr)
        sys.exit(1)

    from core.models import SessionLocal

    session = SessionLocal()
    sentences = find_translit_sentences(
        session, source=args.source, limit=args.limit, min_tokens=args.min_tokens,
        min_id=args.min_id, max_id=args.max_id,
    )
    print(f"Loaded {len(sentences)} transliteration-only sentences (translit→EN)", file=sys.stderr)

    if not sentences:
        print("Nothing to translate.", file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        for s in sentences[:5]:
            print(f"  [{s['id']}] ({s['tok_count']} tok) {s['transliteration'][:100]}")
        batches = (len(sentences) + args.batch_size - 1) // args.batch_size
        print(f"  ... ({len(sentences)} total, {batches} batches)")
        print(f"  Estimated time: {batches * DELAY / 60:.1f} min at {RPM} RPM")
        print(f"  RPD usage: {batches} of 500 requests")
        session.close()
        sys.exit(0)

    client = httpx.Client(
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=httpx.Timeout(120.0, connect=10.0),
    )

    total_saved = 0
    pending = 0
    total_batches = (len(sentences) + args.batch_size - 1) // args.batch_size
    start = time.time()
    consecutive_errors = 0

    for i in range(0, len(sentences), args.batch_size):
        batch = sentences[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1

        results = translate_batch(batch, client)

        if not results:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print(f"  5 consecutive failures — aborting. Saved {total_saved}.", file=sys.stderr)
                break
        else:
            consecutive_errors = 0

        saved = save_translations(results, session)
        total_saved += saved
        pending += saved

        if pending >= args.commit_every:
            try:
                session.commit()
                print(f"  Checkpoint: committed ({total_saved} total saved)", file=sys.stderr)
            except Exception as e:
                print(f"  Commit failed ({e}), rolling back and retrying...", file=sys.stderr)
                session.rollback()
                total_saved -= pending
            pending = 0

        elapsed = time.time() - start
        rate = total_saved / elapsed * 60 if elapsed > 0 else 0
        print(
            f"  Batch {batch_num}/{total_batches}: +{len(results)} translated, "
            f"+{saved} saved (total: {total_saved}, {rate:.0f}/min)",
            file=sys.stderr,
        )

        time.sleep(DELAY)

    client.close()

    if pending > 0:
        try:
            session.commit()
            print(f"  Final commit: {total_saved} total saved", file=sys.stderr)
        except Exception as e:
            print(f"  Final commit failed ({e}), rolling back", file=sys.stderr)
            session.rollback()
            total_saved -= pending

    elapsed = (time.time() - start) / 60
    print(f"\nDone: {total_saved} saved in {elapsed:.1f} minutes", file=sys.stderr)
    session.close()


if __name__ == "__main__":
    main()
