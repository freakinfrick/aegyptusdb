"""show_on_map — highlight chamber(s) on the minimap + full map.

v5.0. Pure frontend-event tool: validates chamber_ids against the live
topology cache and returns the highlight instruction for the client to
render. No DB work.
"""
from __future__ import annotations

import asyncio
from typing import Any

SHOW_ON_MAP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "show_on_map",
        "description": (
            "Highlight one or more chambers on the minimap and full map. "
            "Use AFTER find_chamber to visually confirm location to the user."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chamber_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of chamber ids to highlight.",
                },
            },
            "required": ["chamber_ids"],
        },
    },
}


async def show_on_map(chamber_ids: list[str]) -> dict[str, Any]:
    from graph.topology import chamber_by_id  # deferred: avoid circular import
    validated: list[dict[str, Any]] = []
    missing: list[str] = []
    for cid in chamber_ids or []:
        hall = await asyncio.to_thread(chamber_by_id, cid)
        if hall is not None:
            validated.append({
                "chamber_id": hall.chamber_id,
                "name_en": hall.name_en,
                "level_id": hall.level_id,
            })
        else:
            missing.append(cid)
    return {
        "highlighted": validated,
        "missing": missing,
        "count": len(validated),
    }
