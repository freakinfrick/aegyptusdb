"""speak — trigger the SPEAK synthesis overlay on a chamber.

v5.0 Day-2 carry-over. Client-side tool: validates chamber_id against
live topology and emits an action the frontend subscribes to. The
frontend then opens the three-column SPEAK overlay and streams the
/hackathon/speak SSE (Kimi K2.5 synthesis) for that chamber.

The Oracle uses this tool when the user asks for *interpretation*
(vs. raw lookup). Pairs naturally with find_chamber.
"""
from __future__ import annotations

import asyncio
from typing import Any

SPEAK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "speak",
        "description": (
            "Open the SPEAK overlay on a chamber — streams a Kimi K2.5 "
            "synthesis drawing on the chamber's live corpus passages. "
            "Use when the user wants INTERPRETATION, SYNTHESIS, or "
            "ASKS THE ORACLE TO SPEAK ABOUT a concept/theme. For plain "
            "navigation or lookup, use find_chamber + show_on_map instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chamber_id": {
                    "type": "string",
                    "description": "Chamber to synthesise over.",
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional: the oracle-context hint the user gave, "
                        "passed into the synthesis prompt."
                    ),
                },
            },
            "required": ["chamber_id"],
        },
    },
}


async def speak(chamber_id: str, topic: str = "") -> dict[str, Any]:
    from graph.topology import chamber_by_id
    hall = await asyncio.to_thread(chamber_by_id, chamber_id)
    if hall is None:
        return {
            "ok": False,
            "error": f"chamber '{chamber_id}' not found",
            "chamber_id": chamber_id,
        }
    return {
        "ok": True,
        "chamber_id": hall.chamber_id,
        "name_en":    hall.name_en,
        "level_id":   hall.level_id,
        "topic":      (topic or "").strip(),
        "action":     "speak",
    }
