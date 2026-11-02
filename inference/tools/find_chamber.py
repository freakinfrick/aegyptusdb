"""find_chamber — locate halls in the live topology whose defining lemmata
match a concept.

v5.0: the Labyrinth is the corpus. Chambers do NOT live in a JSON file —
they are derived from Louvain clustering on per-level lemma co-occurrence.
This tool delegates to graph.topology.find_chamber_by_concept.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

FIND_CHAMBER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "find_chamber",
        "description": (
            "Locate the chamber(s) in the Labyrinth whose defining lemma "
            "cluster matches a concept. Returns chamber_id, level, text "
            "count, and the top Egyptian lemmata that define the hall. "
            "Call this before show_on_map or before quoting from a chamber."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": (
                        "English concept or Egyptian lemma, e.g. 'tongue', "
                        "'offering', 'heart', 'Osiris', 'ns', 'jb'."
                    ),
                },
                "level_id": {
                    "type": "integer",
                    "description": (
                        "Optional: restrict to one level (1-7). Omit to "
                        "search across all levels that have been visited "
                        "(cached)."
                    ),
                },
            },
            "required": ["concept"],
        },
    },
}


def _ensure_all_levels_built() -> None:
    """Force-build every level's halls so find_chamber works cold."""
    # Deferred import to avoid circular dependency with inference.tools.__init__.
    from graph.topology import halls_for_level, level_index
    for L in level_index():
        if L.id == 0 or L.text_count < 80:
            continue
        halls_for_level(L.id)


async def find_chamber(concept: str, level_id: int | None = None) -> dict[str, Any]:
    from graph.topology import find_chamber_by_concept
    try:
        # Ensure at least one level is built; cheap if already cached.
        await asyncio.to_thread(_ensure_all_levels_built)
        matches = await asyncio.to_thread(find_chamber_by_concept, concept, level_id)
    except Exception as e:
        log.exception("find_chamber failed")
        return {"concept": concept, "matches": [], "total": 0, "error": str(e)[:200]}
    return {
        "concept": concept,
        "matches": matches,
        "total": len(matches),
    }
