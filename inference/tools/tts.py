"""tts — Edge TTS bridge for the Oracle.

v5.0 Day-2 carry-over. Thin wrapper around api.tts.synthesise_to_cache().
Used both by the Oracle agent (to narrate a passage or direct the user's
attention) and by the reader overlay's ``[▶ HEAR IT]`` button.

Returns a URL the frontend can drop into <audio src="..."> for playback.
"""
from __future__ import annotations

from typing import Any

TTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tts",
        "description": (
            "Convert text to speech using Edge TTS. Returns an audio URL "
            "the frontend plays inline. Use sparingly — when the Oracle "
            "wants to RECITE a specific passage or invocation, not for "
            "every response. One paragraph max per call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesise. Keep under 500 chars.",
                },
                "voice": {
                    "type": "string",
                    "description": (
                        "Symbolic voice id: 'oracle' (default, grave UK), "
                        "'priest' (ritual), 'scribe' (narration), "
                        "'scholar' (commentary)."
                    ),
                    "enum": ["oracle", "priest", "scribe", "scholar", "young-priest"],
                },
            },
            "required": ["text"],
        },
    },
}


async def tts(text: str, voice: str = "oracle") -> dict[str, Any]:
    from api.tts import synthesise_to_cache
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    if len(text) > 1500:
        text = text[:1500]
    result = await synthesise_to_cache(text, voice=voice or "oracle")
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    return {
        "ok":     True,
        "url":    result["url"],
        "voice":  result["voice"],
        "cached": result["cached"],
        "duration_estimate_ms": result["duration_estimate_ms"],
        "action": "tts",
    }
