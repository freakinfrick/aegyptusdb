"""search_transliteration — find texts by Egyptian word form.

When the player or Oracle knows a lemma or transliteration (nswt, ḥtp-ḏj,
rdi̯, etc.) this returns the sentences that contain it. Complements
search_corpus (which searches English translations).
"""
from __future__ import annotations

import logging
from typing import Any

from inference.tools._aegyptus_cli import grep

log = logging.getLogger(__name__)

SEARCH_TRANSLITERATION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_transliteration",
        "description": (
            "Regex search across Egyptian transliterations "
            "(aegyptus grep --field transliteration). Use when the user "
            "names an Egyptian word or lemma (e.g. 'nswt', 'ḥtp-ḏj', 'ns')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Egyptian transliteration fragment. Case-insensitive. "
                        "PostgreSQL regex is honored."
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


async def search_transliteration(query: str, limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 30))
    q = (query or "").strip()
    if not q:
        return {"query": query, "hits": [], "total": 0, "note": "empty query"}
    try:
        rows = await grep(q, field="transliteration", limit=limit)
    except Exception as e:
        log.warning("search_transliteration failed: %s", e)
        return {"query": q, "hits": [], "total": 0, "error": str(e)[:200]}

    hits = []
    for row in rows:
        trans = row.get("translation") or {}
        if isinstance(trans, dict):
            en = trans.get("en") or trans.get("de") or ""
        else:
            en = str(trans)
        hits.append({
            "canonical_id": row.get("canonical_id", ""),
            "sentence_id": row.get("sentence_id"),
            "transliteration": (row.get("transliteration") or "")[:240],
            "translation": (en or "")[:240],
            "source": row.get("source", ""),
        })

    return {"query": q, "hits": hits, "total": len(hits)}
