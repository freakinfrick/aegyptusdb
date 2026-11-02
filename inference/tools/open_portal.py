"""open_portal — spawn a portal at the Oracle Sanctum to a target chamber.

v5.0 Day-2 carry-over. Pure frontend-event tool: validates chamber_id
against the live topology cache and returns the payload for the client
to render (spawn the 3×3 gateway tiles and start portal effects).

Game-side, walking onto the portal centre calls enterPortal() which
flips G.currentLevel to the target and teleports the player to the
chamber room.
"""
from __future__ import annotations

import asyncio
from typing import Any

OPEN_PORTAL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "open_portal",
        "description": (
            "Spawn a portal in the Oracle Sanctum (L0) that leads to the "
            "target chamber. Use AFTER find_chamber when the user wants "
            "to TRAVEL to a chamber — not just see it on the map. The "
            "player walks through the portal to arrive. Only works when "
            "the player is on L0 (the Oracle Sanctum). On other levels, "
            "instruct the user to ascend to the stairs first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chamber_id": {
                    "type": "string",
                    "description": (
                        "The chamber_id to portal to (e.g. 'L1-n-r-p-t'). "
                        "Must be a real chamber resolved via find_chamber."
                    ),
                },
            },
            "required": ["chamber_id"],
        },
    },
}


async def open_portal(chamber_id: str) -> dict[str, Any]:
    from graph.topology import chamber_by_id
    hall = await asyncio.to_thread(chamber_by_id, chamber_id)
    if hall is None:
        return {
            "ok": False,
            "error": f"chamber '{chamber_id}' not found in live topology",
            "chamber_id": chamber_id,
        }
    return {
        "ok": True,
        "chamber_id": hall.chamber_id,
        "name_en":    hall.name_en,
        "level_id":   hall.level_id,
        "text_count": hall.text_count,
        "action":     "open_portal",
    }
