"""show_sentence — aegyptus show --sentence <id>."""
from __future__ import annotations

import logging
from typing import Any

from inference.tools._aegyptus_cli import show_sentence as _show

log = logging.getLogger(__name__)

SHOW_SENTENCE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "show_sentence",
        "description": (
            "Fetch one sentence by integer sentence_id (the id returned by "
            "search_corpus or search_transliteration). Returns "
            "transliteration, English + German translation, and canonical_id "
            "of the parent text so you can follow up with show_text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sentence_id": {
                    "type": "integer",
                    "description": "Primary-key integer id of the sentence row.",
                },
            },
            "required": ["sentence_id"],
        },
    },
}


async def show_sentence(sentence_id: int) -> dict[str, Any]:
    try:
        sid = int(sentence_id)
    except (TypeError, ValueError):
        return {"error": f"invalid sentence_id: {sentence_id!r}"}
    try:
        raw = await _show(sid)
    except Exception as e:
        log.warning("show_sentence failed: %s", e)
        return {"sentence_id": sid, "error": str(e)[:200]}

    if not raw:
        return {"sentence_id": sid, "error": "not found"}

    trans = raw.get("translation") or {}
    if isinstance(trans, dict):
        en = trans.get("en") or ""
        de = trans.get("de") or ""
    else:
        en, de = str(trans), ""

    return {
        "sentence_id": raw.get("id", sid),
        "canonical_id": raw.get("canonical_id", ""),
        "sequence_num": raw.get("sequence_num"),
        "transliteration": (raw.get("transliteration") or "")[:480],
        "en": (en or "")[:600],
        "de": (de or "")[:600] if not en else "",
        "source": raw.get("source", ""),
    }
