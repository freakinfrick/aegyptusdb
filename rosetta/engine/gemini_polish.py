"""Gemini polish — batch fluency polish for mechanical translations.

Takes mechanical interlinear translations and produces fluent English
using Gemini 3.1 Flash Lite API with the full witness dossier:
  - Mechanical English (interlinear)
  - German scholarly translation
  - Token-level glosses

Rate limits (free tier): 15 RPM, 250K TPM, 500 RPD.
We run at 11 RPM with ~100K tokens per request (10% of 1M context).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from typing import TypedDict


class _Candidate(TypedDict):
    id: int
    canonical_id: str
    mechanical: str
    german: str
    glosses: str


class _PolishResult(TypedDict):
    id: int
    canonical_id: str
    en: str


logger = logging.getLogger(__name__)

API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = "gemini-3.1-flash-lite-preview"

# Rate control
# 250K TPM / ~30K tokens per request = ~8 req/min theoretical max.
# Run at 5 RPM to stay well under TPM and give the preview model breathing room.
RPM_TARGET = 5
DELAY = 60.0 / RPM_TARGET   # 12s between requests
MAX_TOKENS_PER_REQUEST = 8_000     # ~50 sentences — output fits in 4K tokens
MAX_OUTPUT_TOKENS = 4096           # ~50 sent × ~80 chars output each
MAX_CONSECUTIVE_ERRORS = 10
MAX_RETRIES = 3
RETRY_BACKOFF = [60, 120, 240]  # longer backoff — give overloaded model time

SYSTEM_PROMPT = """You are an expert Egyptologist producing fluent English translations. For each numbered entry you receive:
- A mechanical (word-by-word) English gloss
- The German scholarly translation
- Token-level glosses

Produce fluent, natural English that:
1. Follows English word order (SVO), not Egyptian
2. Preserves ALL meaning from the German translation
3. Uses the mechanical gloss and token glosses to verify individual word meanings
4. Keeps Egyptian proper names unchanged (Osiris, Horus, Re, Amun, Thoth, Isis, Anubis, Ptah, etc.)
5. Preserves [...] for lacunae/destroyed sections
6. Uses «...» only if a word could not be translated

Output ONLY a JSON array. No markdown, no explanation:
[{"n":1,"en":"Fluent English translation"},{"n":2,"en":"..."},...]"""


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 chars."""
    return len(text) // 4 + 1


def _build_dossier_entry(idx: int, row: _Candidate) -> str:
    """Build a single numbered dossier entry for the prompt."""
    parts = [f"{idx}. "]
    if row.get("german"):
        parts.append(f"German: {row['german']}\n")
    if row.get("mechanical"):
        parts.append(f"Mechanical: {row['mechanical']}\n")
    if row.get("glosses"):
        parts.append(f"Glosses: {row['glosses']}\n")
    return "".join(parts)


class GeminiPolisher:
    """Batch fluency polish via Gemini API."""

    def __init__(self, session: Session, api_key: str | None = None):
        self.session = session
        self._api_key = api_key or API_KEY
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    def load_candidates(self, limit: int = 0, min_tokens: int = 6) -> list[_Candidate]:
        """Load mechanical translations that need polishing.

        Returns list of dicts with id, mechanical_en, german, glosses.
        """
        rows = self.session.execute(
            sa_text("""
                SELECT s.id, s.translation->>'en' AS en,
                       s.translation->>'de' AS de,
                       s.tokens, s.canonical_id
                FROM sentences s
                WHERE s.translation->'_rosetta'->>'source' = 'mechanical'
                  AND s.tokens IS NOT NULL
                  AND jsonb_typeof(s.tokens) = 'array'
                ORDER BY s.id
            """)
        ).fetchall()

        candidates: list[_Candidate] = []
        for sid, en, de, tokens, cid in rows:
            if not isinstance(tokens, list):
                continue
            if len(tokens) < min_tokens:
                continue

            # Build concise gloss string from tokens
            gloss_parts = []
            for tok in tokens:
                if not isinstance(tok, dict):
                    continue
                tde = tok.get("translation_de") or tok.get("cotext_translation") or ""
                form = tok.get("written_form") or tok.get("form") or ""
                if tde:
                    gloss_parts.append(f"{form}={tde}" if form else tde)

            candidates.append(_Candidate(
                id=sid,
                canonical_id=cid,
                mechanical=en or "",
                german=de or "",
                glosses=" | ".join(gloss_parts) if gloss_parts else "",
            ))

            if limit > 0 and len(candidates) >= limit:
                break

        logger.info("Loaded %d candidates for polish", len(candidates))
        return candidates

    def _batch_by_token_budget(
        self, candidates: list[_Candidate], max_tokens: int = MAX_TOKENS_PER_REQUEST
    ) -> list[list[_Candidate]]:
        """Split candidates into batches that fit within token budget."""
        batches: list[list[_Candidate]] = []
        current_batch: list[_Candidate] = []
        current_tokens = _estimate_tokens(SYSTEM_PROMPT) + 200  # overhead

        for cand in candidates:
            entry = _build_dossier_entry(len(current_batch) + 1, cand)
            entry_tokens = _estimate_tokens(entry)
            # Output estimate: ~1.5x the mechanical EN length
            output_tokens = _estimate_tokens(cand["mechanical"]) + 10

            total_add = entry_tokens + output_tokens

            if current_tokens + total_add > max_tokens and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = _estimate_tokens(SYSTEM_PROMPT) + 200

            current_batch.append(cand)
            current_tokens += total_add

        if current_batch:
            batches.append(current_batch)

        return batches

    def _call_gemini(self, batch: list[_Candidate]) -> list[_PolishResult]:
        """Send a batch to Gemini, parse JSON response.

        Returns list of {"id": sentence_id, "en": fluent_english}.
        """
        # Build numbered entries
        entries = []
        for i, cand in enumerate(batch, 1):
            entries.append(_build_dossier_entry(i, cand))
        user_msg = "\n".join(entries)

        client = self._get_client()
        try:
            resp = client.post(
                BASE_URL,
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "max_tokens": MAX_OUTPUT_TOKENS,
                    "temperature": 0.3,
                },
            )

            if resp.status_code == 429:
                body = resp.text
                # RPD exhausted: wait until midnight UTC
                if "quota" in body.lower() or "daily" in body.lower():
                    now = __import__('datetime').datetime.utcnow()
                    import datetime
                    tomorrow = (now + datetime.timedelta(days=1)).replace(
                        hour=0, minute=5, second=0, microsecond=0
                    )
                    wait_secs = (tomorrow - now).total_seconds()
                    logger.warning(
                        "RPD quota exhausted — sleeping until %s UTC (%.1f hrs)",
                        tomorrow.isoformat(), wait_secs / 3600,
                    )
                    time.sleep(wait_secs)
                else:
                    logger.warning("Rate limited (RPM) — waiting 60s")
                    time.sleep(60)
                return []

            if resp.status_code == 503:
                logger.warning("Gemini 503 (overloaded) — will retry")
                return []

            if resp.status_code != 200:
                logger.error("Gemini %d: %s", resp.status_code, resp.text[:200])
                return []

            raw = resp.json()["choices"][0]["message"]["content"]
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            raw = raw.strip()
            # Collapse literal newlines inside JSON string values
            # (model sometimes inserts \n inside "en":"..." values)
            raw = re.sub(r'(?<=: ")([^"]*?)(?=")', lambda m: m.group(0).replace('\n', ' '), raw)

            parsed = json.loads(raw)
            results: list[_PolishResult] = []
            for item in parsed:
                idx = item.get("n", 0) - 1
                en = item.get("en", "").strip()
                if 0 <= idx < len(batch) and en and len(en) >= 3:
                    results.append(_PolishResult(
                        id=batch[idx]["id"],
                        canonical_id=batch[idx]["canonical_id"],
                        en=en,
                    ))
            return results

        except json.JSONDecodeError as e:
            logger.error(
                "JSON parse error: %s | first 300 chars: %s",
                e, raw[:300] if raw else "(empty)",
            )
            # Try to salvage partial JSON — find the last complete entry
            try:
                # Find last valid closing bracket
                last_bracket = raw.rfind("}]")
                if last_bracket > 0:
                    partial = raw[: last_bracket + 2]
                    parsed = json.loads(partial)
                    salvaged: list[_PolishResult] = []
                    for item in parsed:
                        idx = item.get("n", 0) - 1
                        en = item.get("en", "").strip()
                        if 0 <= idx < len(batch) and en and len(en) >= 3:
                            salvaged.append(_PolishResult(
                                id=batch[idx]["id"],
                                canonical_id=batch[idx]["canonical_id"],
                                en=en,
                            ))
                    if salvaged:
                        logger.info("Salvaged %d/%d from partial JSON", len(salvaged), len(batch))
                        return salvaged
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error("Gemini call failed: %s", e)
            return []

    def _save_batch(self, results: list[_PolishResult]):
        """Update sentence translations with polished English."""
        now = datetime.now(timezone.utc).isoformat()

        for r in results:
            # Load current translation
            row = self.session.execute(
                sa_text("SELECT translation FROM sentences WHERE id = :sid"),
                {"sid": r["id"]},
            ).fetchone()

            if not row:
                continue

            translation = row[0] if isinstance(row[0], dict) else {}
            translation["en"] = r["en"]

            rosetta = translation.get("_rosetta", {})
            rosetta["source"] = "gemini_polish"
            rosetta["model"] = MODEL
            rosetta["method"] = "mechanical+gemini_dossier"
            rosetta["tier"] = "T0.5"
            rosetta["polished_at"] = now
            rosetta["needs_review"] = False
            translation["_rosetta"] = rosetta

            self.session.execute(
                sa_text("UPDATE sentences SET translation = :trans WHERE id = :sid"),
                {"sid": r["id"], "trans": json.dumps(translation, ensure_ascii=False)},
            )

    def polish_all(
        self,
        limit: int = 0,
        min_tokens: int = 6,
        dry_run: bool = False,
        commit_every: int = 5,
    ) -> dict[str, object]:
        """Run the full Gemini polish pipeline over all mechanical-translated sentences."""
        if not self._api_key and not dry_run:
            return {"error": "Set GOOGLE_AI_API_KEY"}

        candidates = self.load_candidates(limit=limit, min_tokens=min_tokens)
        if not candidates:
            return {"candidates": 0, "message": "Nothing to polish"}

        batches = self._batch_by_token_budget(candidates)

        total_input_tokens = sum(
            _estimate_tokens(SYSTEM_PROMPT)
            + sum(_estimate_tokens(_build_dossier_entry(i + 1, c)) for i, c in enumerate(b))
            for b in batches
        )
        total_output_tokens = sum(
            sum(_estimate_tokens(c["mechanical"]) + 10 for c in b)
            for b in batches
        )

        stats = {
            "candidates": len(candidates),
            "batches": len(batches),
            "batch_sizes": [len(b) for b in batches[:5]] + (["..."] if len(batches) > 5 else []),
            "est_input_tokens": total_input_tokens,
            "est_output_tokens": total_output_tokens,
            "est_total_tokens": total_input_tokens + total_output_tokens,
            "est_time_minutes": round(len(batches) * DELAY / 60, 1),
            "est_rpd_used": len(batches),
        }

        if dry_run:
            stats["dry_run"] = True
            return stats

        # Execute
        total_polished = 0
        total_failed = 0
        consecutive_errors = 0
        batches_since_commit = 0
        start = time.time()

        for batch_num, batch in enumerate(batches, 1):
            results = self._call_gemini(batch)

            if not results:
                # Retry with backoff
                retried = False
                for attempt, wait in enumerate(RETRY_BACKOFF):
                    logger.warning(
                        "Batch %d/%d failed, retry %d after %ds",
                        batch_num, len(batches), attempt + 1, wait,
                    )
                    time.sleep(wait)
                    results = self._call_gemini(batch)
                    if results:
                        retried = True
                        break

                if not results:
                    consecutive_errors += 1
                    total_failed += len(batch)
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            "%d consecutive errors — aborting at batch %d/%d",
                            MAX_CONSECUTIVE_ERRORS, batch_num, len(batches),
                        )
                        break
                    continue

            if results:
                consecutive_errors = 0
                self._save_batch(results)
                total_polished += len(results)
                total_failed += len(batch) - len(results)
                batches_since_commit += 1

            # Periodic commit
            if batches_since_commit >= commit_every:
                self.session.commit()
                batches_since_commit = 0
                logger.info(
                    "Checkpoint: batch %d/%d, polished %d",
                    batch_num, len(batches), total_polished,
                )

            # Rate limit delay
            if batch_num < len(batches):
                time.sleep(DELAY)

        # Final commit
        if batches_since_commit > 0:
            self.session.commit()

        elapsed = time.time() - start
        stats.update({
            "polished": total_polished,
            "failed": total_failed,
            "elapsed_seconds": round(elapsed, 1),
            "rate_per_minute": round(total_polished / (elapsed / 60), 1) if elapsed > 0 else 0,
        })

        logger.info("Gemini polish complete: %s", stats)
        return stats

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
