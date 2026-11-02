#!/usr/bin/env python3
"""Batch translate Egyptian sentences via Gemini 3.1 Flash Lite (free tier).

Rate limits: 30 RPM, 250K TPM, 1500 RPD (free tier as of 2026-04).
Strategy: batch N sentences per request (German→English) to maximize throughput.

Targets the most intact, richest sentences — those with high token counts and
low damage markers — leaving fragments for the local GPU.

Saves directly to sentences.translation->'en' with model provenance metadata.

Usage:
    GOOGLE_AI_API_KEY=... python scripts/gemini_translate.py --limit 500
    GOOGLE_AI_API_KEY=... python scripts/gemini_translate.py --limit 500 --dry-run
    GOOGLE_AI_API_KEY=... python scripts/gemini_translate.py --limit 500 --source oraec
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
BATCH_SIZE = 50  # sentences per request (~200 tok/sent, ~10K tok/batch, well under 250K TPM)


def find_intact_sentences(session, source=None, limit=500, min_tokens=5):
    """Find the most intact untranslated sentences — high token count, low damage."""
    from sqlalchemy import text as sa_text

    query = """
        SELECT s.id, s.translation->>'de' AS german, s.canonical_id,
               jsonb_array_length(s.tokens) AS tok_count
        FROM sentences s
        WHERE s.transliteration IS NOT NULL
        AND s.tokens IS NOT NULL
        AND s.translation ? 'de'
        AND NOT (s.translation ? 'en')
        AND jsonb_array_length(s.tokens) >= :min_tokens
    """
    params = {"limit": limit, "min_tokens": min_tokens}
    if source:
        query += " AND s.source = :source"
        params["source"] = source

    # Score: token_count * (1 - damage_ratio) — intact sentences first
    query += """
        ORDER BY jsonb_array_length(s.tokens) * (
            1.0 - (
                length(s.transliteration)
                - length(replace(replace(replace(s.transliteration, '[', ''), '⸮', ''), '...', ''))
            )::float / NULLIF(length(s.transliteration), 0)
        ) DESC
        LIMIT :limit
    """
    rows = session.execute(sa_text(query), params).fetchall()
    return [{"id": r[0], "german": r[1], "canonical_id": r[2], "tok_count": r[3]} for r in rows]


def translate_batch(sentences: list[dict], client: httpx.Client) -> list[dict]:
    """Send a batch of sentences to Gemini for DE→EN translation."""
    lines = []
    for i, s in enumerate(sentences):
        lines.append(f"{i+1}. {s['german']}")
    numbered = "\n".join(lines)

    prompt = f"""Translate each numbered German Egyptological sentence to English. Output ONLY a JSON array.

{numbered}

Output format (no markdown, no explanation, ONLY the JSON array):
[{{"n":1,"en":"English translation","c":"HIGH"}},{{"n":2,"en":"...","c":"MEDIUM"}},...]

Rules: 100% English. Zero German words. Preserve Egyptian names (Osiris, Horus, Re, Amun, Thoth, Isis, Anubis, Ptah). Keep [...] brackets for lacunae. c = HIGH|MEDIUM|LOW."""

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
                if en and len(en) >= 5:
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
    """Save translations to sentence rows. Returns count saved."""
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
            "method": "gemini_de_to_en",
        }
        sentence.source_detail = meta
        flag_modified(sentence, "source_detail")
        saved += 1

    return saved


def main():
    parser = argparse.ArgumentParser(description="Translate via Gemini (DE→EN, intact sentences)")
    parser.add_argument("--limit", type=int, default=500, help="Max sentences to translate")
    parser.add_argument("--source", type=str, help="Filter by source (oraec, aes, etc.)")
    parser.add_argument("--min-tokens", type=int, default=5, help="Min token count (default: 5)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Sentences per API call")
    parser.add_argument("--commit-every", type=int, default=200, help="Commit every N saves")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent")
    args = parser.parse_args()

    if not API_KEY and not args.dry_run:
        print("Set GOOGLE_AI_API_KEY (or use --dry-run)", file=sys.stderr)
        sys.exit(1)

    from core.models import SessionLocal

    session = SessionLocal()
    sentences = find_intact_sentences(
        session, source=args.source, limit=args.limit, min_tokens=args.min_tokens,
    )
    print(f"Loaded {len(sentences)} intact untranslated sentences (DE→EN)", file=sys.stderr)

    if not sentences:
        print("Nothing to translate.", file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        for s in sentences[:5]:
            print(f"  [{s['id']}] ({s['tok_count']} tok) {s['german'][:100]}")
        batches = (len(sentences) + args.batch_size - 1) // args.batch_size
        print(f"  ... ({len(sentences)} total, {batches} batches)")
        print(f"  Estimated time: {batches * DELAY / 60:.1f} min at {RPM} RPM")
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
