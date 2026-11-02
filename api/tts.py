"""TTS bridge — Edge TTS → MP3 cached to disk, URL served from web/.

v5.0 §Day-2 carry-over. The Oracle's ``tts`` tool hits this endpoint; the
reader overlay's ``[▶ HEAR IT]`` button hits it too. Both land as MP3
URLs the browser plays directly.

Edge TTS is free (Microsoft neural voices, no API key). A local hash
cache means the same (text, voice) pair never re-synthesises.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/hackathon", tags=["hackathon"])

# ── Cache directory ─────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent.parent / "web" / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Voice palette ───────────────────────────────────────────────────────────
# Maps the Oracle's symbolic voice ids → Edge TTS voice names. The agent
# picks a voice by role; the user never has to know Edge's schema.
VOICES = {
    "oracle":           "en-GB-RyanNeural",       # grave, measured — Oracle narration
    "priest":           "en-GB-ThomasNeural",     # ritual, authoritative
    "scribe":           "en-US-ChristopherNeural", # news/novel — reader narration
    "scholar":          "en-GB-SoniaNeural",      # commentary
    "young-priest":     "en-GB-MaisieNeural",     # lighter
    # Aliases
    "egyptian-priest":  "en-GB-ThomasNeural",
    "default":          "en-GB-RyanNeural",
}


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=6000, description="Text to synthesise.")
    voice: str = Field("oracle", description="Symbolic voice id; see VOICES.")
    rate:  str = Field("+0%", description="Speed override, e.g. '-10%' or '+15%'.")


def _resolve_voice(voice: str) -> str:
    v = (voice or "").strip().lower()
    if v in VOICES:
        return VOICES[v]
    # Pass-through if caller gave a raw Edge TTS name
    if v and "-" in v and v[:5].replace("-", "").isalpha():
        return voice
    return VOICES["default"]


def _cache_key(text: str, voice: str, rate: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    h.update(b"|")
    h.update(voice.encode("utf-8"))
    h.update(b"|")
    h.update(rate.encode("utf-8"))
    return h.hexdigest()[:24]


_RATE_RE = re.compile(r"^[+-]?\d{1,3}%$")


async def _synthesise(text: str, voice_edge: str, rate: str, out_path: Path) -> None:
    import edge_tts  # deferred — keeps import-time work out of the hot path
    kwargs: dict[str, Any] = {"voice": voice_edge}
    if rate and rate != "+0%" and _RATE_RE.match(rate):
        kwargs["rate"] = rate
    communicate = edge_tts.Communicate(text, **kwargs)
    await communicate.save(str(out_path))


async def synthesise_to_cache(text: str, voice: str = "oracle",
                              rate: str = "+0%") -> dict[str, Any]:
    """Synthesise (or hit cache) and return metadata dict.

    Returns::
        {
          "url":       "/web/audio_cache/<key>.mp3",
          "path":      absolute Path as str,
          "key":       hash,
          "cached":    True/False,
          "size":      int,
          "voice":     resolved Edge TTS voice,
          "duration_estimate_ms": heuristic based on char count,
        }
    """
    text = (text or "").strip()
    if not text:
        return {"error": "empty text", "url": None}
    if not _RATE_RE.match(rate or "+0%"):
        rate = "+0%"

    voice_edge = _resolve_voice(voice)
    key = _cache_key(text, voice_edge, rate)
    out_path = CACHE_DIR / f"{key}.mp3"

    if out_path.exists() and out_path.stat().st_size > 512:
        cached = True
    else:
        cached = False
        try:
            await _synthesise(text, voice_edge, rate, out_path)
        except Exception as e:
            log.exception("edge-tts synthesis failed")
            return {"error": f"{type(e).__name__}: {e}", "url": None}

    size = out_path.stat().st_size if out_path.exists() else 0
    # Rough heuristic: ~14 chars/sec at neutral rate, +6 for pauses.
    duration_ms = int(max(1000, (len(text) / 14.0) * 1000 + 400))

    return {
        "url":     f"/web/audio_cache/{out_path.name}",
        "path":    str(out_path),
        "key":     key,
        "cached":  cached,
        "size":    size,
        "voice":   voice_edge,
        "duration_estimate_ms": duration_ms,
    }


# ── /hackathon/tts ──────────────────────────────────────────────────────────
@router.post("/tts")
async def tts_endpoint(req: TTSRequest):
    """Synthesise text → MP3, cached. Returns {url, voice, cached, size}."""
    result = await synthesise_to_cache(req.text, req.voice, req.rate)
    if "error" in result:
        return JSONResponse(status_code=502, content=result)
    return result


@router.get("/tts/voices")
async def tts_voices():
    """List the symbolic voices the Oracle can pick."""
    return {
        "default": "oracle",
        "voices":  VOICES,
    }
