"""read_article — open a golden tablet in the reader overlay.

v5.0 Day-2 carry-over. Clients render an EB-Garamond reader overlay
(web/reader.js) over the canvas with the article body + ``[▶ HEAR IT]``
and ``[✦ SPEAK ABOUT THIS]`` actions.

The nine Oracle articles live in graph/chambers.json on the v3.1 L0
Sanctum chambers, one per hand-authored physical_text entry. Each
article has an article_id (1..9), a theme, and a body. The Oracle can
offer to "read one" to the user — this tool fires the overlay.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

READ_ARTICLE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_article",
        "description": (
            "Open one of the nine Oracle articles in the reader overlay. "
            "The nine articles live in the L0 Sanctum horseshoe and are "
            "hand-authored essays by the Oracle on core themes. Use when "
            "the user asks to READ an article, or when their question "
            "matches an article theme more closely than a live chamber."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": ["integer", "string"],
                    "description": (
                        "Article index 1..9 (the nine tablets in the "
                        "Sanctum horseshoe), or the canonical_id of a "
                        "specific tablet for more precise targeting."
                    ),
                },
            },
            "required": ["article_id"],
        },
    },
}


_CHAMBERS_PATH = Path(__file__).parent.parent.parent / "graph" / "chambers.json"
_cache: list[dict] | None = None


def _load_articles() -> list[dict]:
    """Load the 9 hand-authored Sanctum articles from chambers.json.

    Each L0 chamber carries physical_texts[]; we extract all of them and
    assign a stable article_id 1..9 in document order.
    """
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_CHAMBERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _cache = []
        return _cache

    articles: list[dict] = []
    idx = 1
    for ch in data:
        if ch.get("level") != 0:
            continue
        for pt in ch.get("physical_texts", []) or []:
            articles.append({
                "article_id":   idx,
                "canonical_id": pt.get("canonical_id", ""),
                "name":         pt.get("name", f"Tablet {idx}"),
                "period":       pt.get("period", ""),
                "theme":        pt.get("theme", pt.get("name", "")),
                "body":         pt.get("body", pt.get("description", "")),
                "chamber_id":   ch.get("id", ""),
            })
            idx += 1
            if idx > 9:
                break
        if idx > 9:
            break
    _cache = articles
    return _cache


async def read_article(article_id: int | str) -> dict[str, Any]:
    articles = await asyncio.to_thread(_load_articles)
    if not articles:
        return {"ok": False, "error": "no articles available (chambers.json missing?)"}

    # Accept either the integer index or a canonical_id string.
    match: dict | None = None
    if isinstance(article_id, int) or (isinstance(article_id, str) and article_id.isdigit()):
        wanted = int(article_id)
        match = next((a for a in articles if a["article_id"] == wanted), None)
    if match is None and isinstance(article_id, str):
        match = next(
            (a for a in articles if a["canonical_id"] == article_id),
            None,
        )
    if match is None:
        return {
            "ok": False,
            "error": f"article '{article_id}' not found",
            "available": [a["article_id"] for a in articles],
        }
    # Truncate body in the tool result — the frontend fetches the full
    # body from its own chamber cache. We just need enough for the
    # Oracle's final message to quote a line.
    body = match["body"] or ""
    if not body:
        # Graceful placeholder when the chambers.json entry has only
        # metadata (name/period/canonical_id). The reader overlay will
        # still open with the title card + [HEAR IT] action pointing at
        # this placeholder, and [SPEAK ABOUT THIS] will invoke the Oracle
        # on the theme. Better than a blank page.
        body = (
            f"# {match['name']}\n\n"
            f"*{match['period']}*\n\n"
            "This tablet has been catalogued but its full body "
            "has not yet been transcribed into the Oracle's library. "
            "The Oracle can still speak about it \u2014 press "
            "[\u2726 SPEAK ABOUT THIS] and the chamber will open."
        )
    preview = body[:400] + ("\u2026" if len(body) > 400 else "")
    return {
        "ok":          True,
        "article_id":  match["article_id"],
        "canonical_id": match["canonical_id"],
        "name":        match["name"],
        "theme":       match["theme"],
        "period":      match["period"],
        "preview":     preview,
        "body":        body,
        "chamber_id":  match["chamber_id"],
        "action":      "read_article",
    }
