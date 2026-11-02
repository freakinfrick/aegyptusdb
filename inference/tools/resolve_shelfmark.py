"""resolve_shelfmark — look up a museum/collection shelfmark via aegyptus."""
from __future__ import annotations

import logging
from typing import Any

from inference.tools._aegyptus_cli import resolve as _resolve

log = logging.getLogger(__name__)

RESOLVE_SHELFMARK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "resolve_shelfmark",
        "description": (
            "Resolve a museum shelfmark (e.g. 'P. Berlin 3022', "
            "'EA 10477', 'CG 51189') to canonical corpus texts. "
            "Use when the user names a papyrus, ostracon, stele, or "
            "tomb reference."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "shelfmark": {
                    "type": "string",
                    "description": "Shelfmark string as found in the literature.",
                },
            },
            "required": ["shelfmark"],
        },
    },
}


async def resolve_shelfmark(shelfmark: str) -> dict[str, Any]:
    s = (shelfmark or "").strip()
    if not s:
        return {"shelfmark": shelfmark, "matches": [], "total": 0,
                "note": "empty shelfmark"}
    try:
        raw = await _resolve(shelfmark=s)
    except Exception as e:
        log.warning("resolve_shelfmark failed: %s", e)
        return {"shelfmark": s, "matches": [], "total": 0, "error": str(e)[:200]}

    matches = raw.get("matches") or []
    out_matches = []
    for m in matches[:10]:
        out_matches.append({
            "canonical_id": m.get("canonical_id", ""),
            "alias_type": m.get("alias_type", ""),
            "value": m.get("value", "") or m.get("normalized", ""),
        })
    return {
        "shelfmark": s,
        "normalized": raw.get("normalized", s),
        "matches": out_matches,
        "total": len(out_matches),
    }
