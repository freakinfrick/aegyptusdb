"""search_corpus — aegyptus CLI wrapper (v5.0).

The Oracle's search layer IS the aegyptus CLI's search layer. No parallel
implementation. The hits are real sentences from the corpus.

Per ETHOS Law II: the Oracle is the harness.

Query expansion (v5.1): if the caller passes a natural-language phrase
like 'honey bees', 'weighing of the heart', or 'mouth opening', a literal
regex search often returns zero hits because the corpus splits those
concepts across sentences. We expand queries by:

  1. Trying the literal regex the caller provided (authoritative).
  2. If zero hits and the query has >=2 content words, retry with
     `term1|term2|term3` (PostgreSQL regex alternation) so at least one
     of the concept words matches.
  3. Fall back to the single most distinctive word (longest content word).

Stopwords are stripped so 'texts about honey' doesn't alternate with
'texts' or 'about'. The `expansions` field in the returned dict records
which query actually produced the hits so the Oracle can be honest.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from inference.tools._aegyptus_cli import grep

# Common English stopwords + corpus-meta words that never select useful hits.
_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or",
    "with", "from", "by", "at", "as", "is", "are", "was", "were", "be",
    "it", "this", "that", "these", "those", "about", "any", "all",
    "some", "text", "texts", "corpus", "sentence", "sentences",
    "find", "search", "show", "discuss", "discusses", "discussing",
    "mention", "mentions", "mentioning", "reference", "references",
    "referencing", "egyptian", "ancient",
})


def _tokenize(q: str) -> list[str]:
    """Lowercase + alpha-tokenize a query into content words."""
    return [w for w in re.findall(r"[a-zA-Z]+", q.lower())
            if w not in _STOPWORDS and len(w) > 1]

log = logging.getLogger(__name__)

SEARCH_CORPUS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_corpus",
        "description": (
            "Regex search across the English translations of all 460,333 "
            "sentences in the corpus (aegyptus grep --field translation). "
            "Returns up to `limit` matching sentences with canonical_id, "
            "transliteration, translation snippet, and shelfmark."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Term or short phrase in English. e.g. 'tongue', "
                        "'mouth opening', 'weighing of the heart'. "
                        "Case-insensitive. PostgreSQL regex is honored."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Max hits to return. Default 10, hard cap 30.",
                },
            },
            "required": ["query"],
        },
    },
}


def _rows_to_hits(rows: list[dict], q: str, limit: int) -> list[dict]:
    hits: list[dict] = []
    for row in rows[:limit]:
        trans = row.get("translation") or {}
        if isinstance(trans, dict):
            en = trans.get("en") or trans.get("de") or ""
        else:
            en = str(trans)
        snippet = (en or "").strip()
        if len(snippet) > 240:
            low = snippet.lower()
            pos = low.find(q.lower())
            snippet = (
                "…" + snippet[max(0, pos - 40): pos - 40 + 240] + "…"
                if pos > 60 else snippet[:240] + "…"
            )
        hits.append({
            "canonical_id": row.get("canonical_id", ""),
            "sentence_id": row.get("sentence_id"),
            "transliteration": (row.get("transliteration") or "")[:240],
            "snippet": snippet,
            "source": row.get("source", ""),
        })
    return hits


async def search_corpus(query: str, limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 30))
    q = (query or "").strip()
    if not q:
        return {"query": query, "hits": [], "total": 0, "note": "empty query"}

    expansions: list[str] = []
    hits: list[dict] = []
    used = q

    # Pass 1: literal.
    try:
        rows = await grep(q, field="translation", limit=limit)
        expansions.append(q)
        hits = _rows_to_hits(rows, q, limit)
    except Exception as e:
        log.warning("search_corpus literal failed: %s", e)
        return {"query": q, "hits": [], "total": 0, "error": str(e)[:200],
                "expansions": expansions}

    # Pass 2: OR-alternation across content words (if literal found nothing).
    if not hits:
        tokens = _tokenize(q)
        if len(tokens) >= 2:
            alt = "|".join(tokens)
            expansions.append(alt)
            try:
                rows2 = await grep(alt, field="translation", limit=limit)
                hits = _rows_to_hits(rows2, tokens[0], limit)
                if hits:
                    used = alt
            except Exception as e:
                log.warning("search_corpus OR-expand failed: %s", e)

        # Pass 3: longest single content word (most distinctive).
        if not hits and tokens:
            longest = max(tokens, key=len)
            if longest != q.lower():
                expansions.append(longest)
                try:
                    rows3 = await grep(longest, field="translation", limit=limit)
                    hits = _rows_to_hits(rows3, longest, limit)
                    if hits:
                        used = longest
                except Exception as e:
                    log.warning("search_corpus longest-word failed: %s", e)

    return {
        "query": q,
        "query_used": used,
        "expansions": expansions,
        "hits": hits,
        "total": len(hits),
    }
