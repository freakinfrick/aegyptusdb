"""corpus_stats — counts for a scope, v5.0.

Scopes:
  'corpus'          whole-corpus totals via aegyptus status
  'level:<n>'       level_index() from live topology
  'chamber:<id>'    hall metadata from graph.topology
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from inference.tools._aegyptus_cli import status as _status

log = logging.getLogger(__name__)

CORPUS_STATS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "corpus_stats",
        "description": (
            "Return counts for a scope. Use when the user asks 'how big', "
            "'how many', or wants a sense of scale. Scopes: 'corpus', "
            "'level:<n>' (0-7), or 'chamber:<id>'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "'corpus' | 'level:<n>' | 'chamber:<id>'",
                },
            },
            "required": ["scope"],
        },
    },
}


_corpus_cache: dict[str, Any] | None = None


async def _corpus_totals() -> dict[str, Any]:
    global _corpus_cache
    if _corpus_cache is not None:
        return _corpus_cache
    try:
        raw = await _status()
    except Exception as e:
        log.warning("corpus_stats status failed: %s", e)
        return {"texts": 0, "sentences": 0, "by_script": {}}
    # aegyptus status returns nested dict with breakdowns
    out = {
        "texts": raw.get("texts", 0),
        "sentences": raw.get("sentences", 0),
        "representation_layers": raw.get("representation_layers", 0),
        "concordance": raw.get("concordance", 0),
        "by_script": raw.get("by_script") or raw.get("script_types") or {},
        "by_source": raw.get("by_source") or raw.get("sources") or {},
    }
    _corpus_cache = out
    return out


async def corpus_stats(scope: str) -> dict[str, Any]:
    scope = (scope or "").strip().lower()
    if scope in ("corpus", ""):
        t = await _corpus_totals()
        return {"scope": "corpus", **t}

    if scope.startswith("level:"):
        from graph.topology import level_index, halls_for_level
        try:
            lvl_id = int(scope.split(":", 1)[1])
        except ValueError:
            return {"scope": scope, "error": "invalid level"}
        levels = await asyncio.to_thread(level_index)
        level = next((L for L in levels if L.id == lvl_id), None)
        if level is None:
            return {"scope": scope, "error": "level not found"}
        halls = await asyncio.to_thread(halls_for_level, lvl_id)
        return {
            "scope": scope,
            "level_id": lvl_id,
            "name_en": level.name_en,
            "date_range": level.date_range,
            "text_count": level.text_count,
            "period_label_count": len(level.period_labels),
            "chamber_count": len(halls),
            "chambers": [
                {"chamber_id": h.chamber_id, "name_en": h.name_en,
                 "text_count": h.text_count}
                for h in halls[:12]
            ],
        }

    if scope.startswith("chamber:"):
        from graph.topology import chamber_by_id
        cid = scope.split(":", 1)[1]
        hall = await asyncio.to_thread(chamber_by_id, cid)
        if hall is None:
            return {"scope": scope, "error": "chamber not found"}
        return {
            "scope": scope,
            "chamber_id": hall.chamber_id,
            "name_en": hall.name_en,
            "level_id": hall.level_id,
            "text_count": hall.text_count,
            "defining_lemmata": [
                {"form": lr.form, "gloss_en": lr.gloss_en}
                for lr in hall.defining_lemmata
            ],
        }

    return {"scope": scope, "error": "unknown scope"}
