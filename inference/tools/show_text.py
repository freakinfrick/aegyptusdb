"""show_text — aegyptus show --text <canonical_id>.

Returns a compact view of a full text: header, first several sentences with
transliteration + translation, shelfmarks, period, and cross-references.
The result is trimmed so it fits comfortably inside the agent's tool-result
history budget.
"""
from __future__ import annotations

import logging
from typing import Any

from inference.tools._aegyptus_cli import show_text as _show

log = logging.getLogger(__name__)

SHOW_TEXT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "show_text",
        "description": (
            "Fetch the full record of one text by canonical_id. Returns "
            "header metadata, the first N sentences (transliteration + "
            "translation), shelfmarks, period, and cross-references. "
            "Use after search_corpus to read a hit in context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "canonical_id": {
                    "type": "string",
                    "description": "e.g. 'aeg_oraec_320'",
                },
                "max_sentences": {
                    "type": "integer",
                    "default": 8,
                    "description": "How many sentences to include (cap 20).",
                },
            },
            "required": ["canonical_id"],
        },
    },
}


async def show_text(canonical_id: str, max_sentences: int = 8) -> dict[str, Any]:
    cid = (canonical_id or "").strip()
    if not cid:
        return {"error": "empty canonical_id"}
    max_sentences = max(1, min(int(max_sentences or 8), 20))

    try:
        raw = await _show(cid)
    except Exception as e:
        log.warning("show_text failed: %s", e)
        return {"canonical_id": cid, "error": str(e)[:200]}

    if not raw or "text" not in raw:
        return {"canonical_id": cid, "error": "not found"}

    t = raw.get("text") or {}
    sents_in = raw.get("sentences") or []
    sentences = []
    for s in sents_in[:max_sentences]:
        trans = s.get("translation") or {}
        if isinstance(trans, dict):
            en = trans.get("en") or ""
            de = trans.get("de") or ""
        else:
            en, de = str(trans), ""
        sentences.append({
            "sentence_id": s.get("id"),
            "seq": s.get("sequence_num"),
            "transliteration": (s.get("transliteration") or "")[:320],
            "en": (en or "")[:400],
            "de": (de or "")[:400] if not en else "",
        })

    concordance = [
        {"system": c.get("system"), "external_id": c.get("external_id")}
        for c in (raw.get("concordance") or [])[:10]
    ]

    return {
        "canonical_id": cid,
        "name": t.get("conventional_name", ""),
        "period": t.get("period_label", ""),
        "date_earliest": t.get("date_earliest"),
        "date_latest": t.get("date_latest"),
        "script_type": t.get("script_type", ""),
        "text_type": t.get("text_type", ""),
        "shelfmarks": (t.get("shelfmarks") or [])[:4],
        "source_corpus": t.get("source_corpus") or [],
        "sentence_count": len(sents_in),
        "sentences_shown": sentences,
        "concordance": concordance,
        "truncated": len(sents_in) > max_sentences,
    }
