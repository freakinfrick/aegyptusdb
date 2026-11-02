"""Hackathon API router — AEGYPTUS: THE LABYRINTH.

Endpoints:
  GET  /hackathon/health         → status check
  GET  /hackathon/graph          → full chamber graph JSON
  GET  /hackathon/levels         → level metadata
  GET  /hackathon/chamber/{id}   → single chamber with passages
  GET  /hackathon/synthesis/{id} → cached Kimi synthesis
  POST /hackathon/speak          → SSE: passages → Kimi synthesis stream
  POST /hackathon/hint           → short navigation hint (Hermes)
  WS   /hackathon/ws_agent       → Oracle WebSocket (Hermes-agent, tool-call streaming)
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from inference.client import call_hermes_plain, stream_kimi
from inference.prompts import (
    EXPLORE_NAVIGATION_HINT,
    ORACLE_AGENT_SYSTEM_PROMPT,
    SPEAK_SYNTHESIS_SYSTEM_PROMPT,
)
from api.oracle_agent import OracleAgent
from inference.tools._db import get_conn as _get_db, put_conn as _put_db
from graph.topology import (
    level_index,
    halls_for_level,
    chamber_by_id,
    texts_for_chamber,
    composition_for_chamber,
)
from graph.kit import size_room_for as kit_size_room_for, density_for as kit_density_for
from dataclasses import asdict

log = logging.getLogger(__name__)

router = APIRouter(prefix="/hackathon", tags=["hackathon"])

# ── Config ──────────────────────────────────────────────────────────────────
GRAPH_PATH = Path(__file__).parent.parent / "graph" / "chambers.json"
LEVELS_PATH = Path(__file__).parent.parent / "graph" / "levels.json"

# ── Cached data ─────────────────────────────────────────────────────────────
_chambers_cache: list[dict] | None = None
_chambers_by_id: dict[str, dict] = {}


def _load_chambers() -> list[dict]:
    global _chambers_cache, _chambers_by_id
    if _chambers_cache is None:
        with open(GRAPH_PATH) as f:
            _chambers_cache = json.load(f)
        _chambers_by_id = {c["id"]: c for c in _chambers_cache}
    return _chambers_cache


def _get_chamber(chamber_id: str) -> dict | None:
    _load_chambers()
    return _chambers_by_id.get(chamber_id)


# ── Request/Response models ────────────────────────────────────────────────
class SpeakRequest(BaseModel):
    chamber_id: str
    oracle_context: str | None = None


class HintRequest(BaseModel):
    chamber_id: str


# ── /health ─────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "corpus_texts": 77683,
        "hermes": "Hermes-4-70B",
        "kimi": "moonshotai/kimi-k2.5",
        "topology": "live (v5.0)",
    }


# ── /graph ──────────────────────────────────────────────────────────────────
@router.get("/graph")
async def get_graph():
    """v3.1 hand-curated chamber graph. Superseded by /level/<id>/halls."""
    chambers = _load_chambers()
    return chambers


# ── /levels ────────────────────────────────────────────────────────────────
@router.get("/levels")
async def get_levels():
    """Live level index — one entry per L0..L7 with text counts and the
    period_labels bucketing into each level (derived from texts.period_label).
    """
    levels = await asyncio.to_thread(level_index)
    return [asdict(L) for L in levels]


@router.get("/level/{level_id}/halls")
async def get_level_halls(level_id: int, with_composition: bool = True):
    """Run (or look up cached) Louvain clustering for this level; return the
    halls with their defining Egyptian lemmata and text counts.

    When ``with_composition=true`` (default), each hall also carries its
    ``text_type_composition``, full ``assigned_ids`` list, and the
    kit-suggested ``size`` (w, h) — so the client can assemble chambers
    without follow-up round-trips.
    """
    try:
        halls = await asyncio.to_thread(halls_for_level, level_id)
    except Exception as e:
        log.exception("halls_for_level(%s) failed", level_id)
        return JSONResponse(status_code=500, content={"error": str(e)})
    out_halls: list[dict] = []
    for h in halls:
        d = asdict(h)
        if with_composition:
            try:
                comp = await asyncio.to_thread(composition_for_chamber, h.chamber_id)
            except Exception as e:
                log.warning("composition_for_chamber(%s) failed: %s", h.chamber_id, e)
                comp = {}
            if "error" not in comp:
                composition = comp.get("text_type_composition", {})
                assigned_ids = comp.get("assigned_ids", [])
                d["text_type_composition"] = composition
                d["assigned_ids"] = assigned_ids
                if composition:
                    try:
                        w, h_ = kit_size_room_for(composition)
                        d["suggested_size"] = {
                            "w": w, "h": h_,
                            "density": round(kit_density_for(composition, w, h_), 4),
                        }
                    except Exception as e:
                        log.warning("size_room_for failed for %s: %s", h.chamber_id, e)
        out_halls.append(d)
    return {
        "level_id": level_id,
        "halls": out_halls,
        "count": len(out_halls),
    }


@router.get("/chamber/{chamber_id}/texts")
async def get_chamber_texts(chamber_id: str, limit: int = 60):
    """Return the passages that belong to a chamber, live-queried.
    A text is in the chamber iff it carries ≥2 of the chamber's defining
    lemmata AND its period_label maps to the chamber's level.
    """
    data = await asyncio.to_thread(texts_for_chamber, chamber_id, limit)
    if "error" in data:
        return JSONResponse(status_code=404, content=data)
    # Attach composition so the client can feed kit.size_room_for without
    # a second round-trip.
    comp = await asyncio.to_thread(composition_for_chamber, chamber_id)
    if "error" not in comp:
        data["text_type_composition"] = comp["text_type_composition"]
        data["assigned_ids"] = comp["assigned_ids"]
    return data


@router.get("/chamber/{chamber_id}/composition")
async def get_chamber_composition(chamber_id: str):
    """Return text_type composition + full assigned canonical_ids for a
    chamber. Drives the kit-of-parts assembler: room sizing,
    part-placement budget, density verification.
    """
    data = await asyncio.to_thread(composition_for_chamber, chamber_id)
    if "error" in data:
        return JSONResponse(status_code=404, content=data)
    # Add suggested room dimensions from the kit.
    try:
        w, h = kit_size_room_for(data["text_type_composition"])
        d = kit_density_for(data["text_type_composition"], w, h)
        data["suggested_size"] = {"w": w, "h": h, "density": round(d, 4)}
    except Exception as e:
        log.warning("size_room_for failed for %s: %s", chamber_id, e)
    return data


# ── /chamber/{id} ───────────────────────────────────────────────────────────
async def _chamber_live(chamber_id: str) -> dict | None:
    hall = await asyncio.to_thread(chamber_by_id, chamber_id)
    if hall is None:
        return None
    payload = await asyncio.to_thread(texts_for_chamber, chamber_id, 12)
    passages = payload.get("passages", [])
    comp = await asyncio.to_thread(composition_for_chamber, chamber_id)
    composition = comp.get("text_type_composition", {}) if "error" not in comp else {}
    assigned_ids = comp.get("assigned_ids", []) if "error" not in comp else []
    suggested_size = None
    if composition:
        try:
            w, h = kit_size_room_for(composition)
            suggested_size = {
                "w": w, "h": h,
                "density": round(kit_density_for(composition, w, h), 4),
            }
        except Exception as e:
            log.warning("size_room_for failed for %s: %s", chamber_id, e)
    return {
        "id": hall.chamber_id,
        "name_en": hall.name_en,
        "level": hall.level_id,
        "term_eg": " · ".join(lr.form for lr in hall.defining_lemmata[:3]),
        "term_en": " · ".join(
            (lr.gloss_en or lr.form).split(";")[0].split(",")[0].strip()
            for lr in hall.defining_lemmata[:3]
        ),
        "defining_lemmata": [asdict(lr) for lr in hall.defining_lemmata],
        "text_count": hall.text_count,
        "canonical_ids": assigned_ids or [p["canonical_id"] for p in passages],
        "passages": passages,
        "text_type_composition": composition,
        "assigned_ids": assigned_ids,
        "suggested_size": suggested_size,
    }


@router.get("/chamber/{chamber_id}")
async def get_chamber(chamber_id: str):
    """Return full chamber data. Tries the live topology first; falls back
    to v3.1 chambers.json only if the id is unknown."""
    live = await _chamber_live(chamber_id)
    if live is not None:
        return live

    chamber = _get_chamber(chamber_id)
    if not chamber:
        return JSONResponse(status_code=404, content={"error": f"Chamber '{chamber_id}' not found"})

    passages = await asyncio.to_thread(_fetch_passages, chamber["canonical_ids"][:12])
    return {**chamber, "passages": passages}


def _fetch_passages(canonical_ids: list[str], limit: int = 12) -> list[dict]:
    """Fetch full passage data for a list of canonical IDs."""
    if not canonical_ids:
        return []

    conn = _get_db()
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(canonical_ids))

    # Use window function to pick longest English translation per text
    cur.execute(f"""
        WITH ranked AS (
            SELECT s.canonical_id, s.transliteration, s.translation,
                   t.conventional_name, t.period_label, t.current_location,
                   t.shelfmarks,
                   ROW_NUMBER() OVER (
                       PARTITION BY s.canonical_id
                       ORDER BY length(s.translation::text) DESC
                   ) AS rn
            FROM sentences s
            JOIN texts t ON t.canonical_id = s.canonical_id
            WHERE s.canonical_id IN ({placeholders})
              AND s.translation IS NOT NULL
              AND s.translation::text != 'null'
              AND length(s.translation::text) > 20
        )
        SELECT canonical_id, transliteration, translation,
               conventional_name, period_label, current_location, shelfmarks
        FROM ranked
        WHERE rn = 1
        ORDER BY canonical_id
    """, canonical_ids)

    by_id: dict[str, dict] = {}
    for row in cur.fetchall():
        cid = row[0]
        trans = row[2]
        en = ""
        if isinstance(trans, dict):
            en = trans.get("en", trans.get("de", ""))
        elif isinstance(trans, str):
            en = trans
        by_id[cid] = {
            "canonical_id": cid,
            "transliteration": row[1] or "",
            "translation": en,
            "text_name": row[3] or "",
            "period": row[4] or "",
            "location": row[5] or "",
            "shelfmark": (row[6] or [""])[0] if row[6] else "",
        }

    # Get hieroglyphic layers
    cur.execute(f"""
        SELECT canonical_id, content
        FROM representation_layers
        WHERE canonical_id IN ({placeholders})
          AND layer_type = 'hieroglyphic'
    """, canonical_ids)
    hiero_map = {}
    for row in cur.fetchall():
        content = row[1]
        if isinstance(content, dict):
            hiero_map[row[0]] = content.get("text", content.get("content", ""))[:300]
        elif content:
            hiero_map[row[0]] = str(content)[:300]

    _put_db(conn)

    # Assemble: one best passage per text
    passages = []
    for cid in canonical_ids:
        if cid not in by_id:
            continue
        passage = by_id[cid]
        passage["hieroglyphic"] = hiero_map.get(cid, "")
        passages.append(passage)
        if len(passages) >= limit:
            break

    return passages


# ── /synthesis/{chamber_id} — cached Kimi synthesis ──────────────────────
@router.get("/synthesis/{chamber_id}")
async def get_synthesis(chamber_id: str):
    """Return cached Kimi synthesis for a chamber, or 404."""
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT content, word_count, citation_count, model, created_at "
        "FROM hackathon_syntheses WHERE chamber_id = %s",
        (chamber_id,),
    )
    row = cur.fetchone()
    _put_db(conn)
    if not row:
        return JSONResponse(status_code=404, content={"cached": False})
    return {
        "cached": True,
        "chamber_id": chamber_id,
        "content": row[0],
        "word_count": row[1],
        "citation_count": row[2],
        "model": row[3],
        "created_at": str(row[4]),
    }


def _save_synthesis(chamber_id: str, content: str, word_count: int, citation_count: int):
    """Cache a completed Kimi synthesis in the database."""
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO hackathon_syntheses (chamber_id, content, word_count, citation_count) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (chamber_id) DO UPDATE SET "
            "content = EXCLUDED.content, word_count = EXCLUDED.word_count, "
            "citation_count = EXCLUDED.citation_count, created_at = NOW()",
            (chamber_id, content, word_count, citation_count),
        )
        _put_db(conn)
        log.info("Cached synthesis for chamber %s (%d words)", chamber_id, word_count)
    except Exception as e:
        log.error("Failed to cache synthesis for %s: %s", chamber_id, e)


# ── /speak ──────────────────────────────────────────────────────────────────
@router.post("/speak")
async def speak(req: SpeakRequest):
    """SSE stream: emit passages, then Kimi synthesis.

    Tries the live topology first so v5.0 halls (L1-L7) SPEAK work; falls
    back to the v3.1 chambers.json for the L0 Sanctum.
    """
    chamber: dict | None = None
    live = await _chamber_live(req.chamber_id)
    if live is not None:
        chamber = {
            "id":            live["id"],
            "name_en":       live["name_en"],
            "term_eg":       live["term_eg"],
            "text_count":    live["text_count"],
            "period_range":  "",
            "canonical_ids": live["canonical_ids"],
        }
    else:
        chamber = _get_chamber(req.chamber_id)
    if not chamber:
        return JSONResponse(status_code=404, content={"error": f"Chamber '{req.chamber_id}' not found"})

    return EventSourceResponse(
        _speak_generator(chamber, req.oracle_context),
        media_type="text/event-stream",
    )


async def _speak_generator(chamber: dict, oracle_context: str | None) -> AsyncGenerator:
    """Generator that yields SSE events for SPEAK.

    Uses an asyncio.Queue to bridge the synchronous stream_kimi generator
    (running in a thread) with the async SSE response. Each chunk is yielded
    as it arrives — true streaming, not buffered.
    """

    # 1. Fetch passages
    passages = await asyncio.to_thread(_fetch_passages, chamber["canonical_ids"][:10], 8)

    # Emit passages
    yield {
        "event": "message",
        "data": json.dumps({"type": "passages", "data": passages}),
    }

    if not passages:
        yield {
            "event": "message",
            "data": json.dumps({"type": "error", "data": "No passages found for this chamber."}),
        }
        return

    # 2. Build Kimi synthesis prompt
    passage_block = "\n\n".join([
        f"--- {p['canonical_id']} · {p['shelfmark']} · {p['period']} ---\n"
        f"Transliteration: {p['transliteration'][:200]}\n"
        f"Translation: {p['translation']}"
        for p in passages
    ])

    chamber_context = (
        f"Chamber: {chamber['name_en']} ({chamber['term_eg']})\n"
        f"Texts: {chamber['text_count']} spanning {chamber['period_range']}\n"
    )
    if oracle_context:
        chamber_context += f"Oracle context: {oracle_context}\n"

    messages = [
        {"role": "system", "content": SPEAK_SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"{chamber_context}\n\n"
            f"Write about this chamber's concept using these corpus passages:\n\n"
            f"{passage_block}"
        )},
    ]

    # 3. Stream Kimi synthesis via async queue
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def _run_kimi():
        """Synchronous producer: feeds chunks into the queue thread-safely."""
        word_count = 0
        full_text = []
        try:
            for chunk in stream_kimi(messages):
                word_count += len(chunk.split())
                full_text.append(chunk)
                loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
            # Cache the completed synthesis
            _save_synthesis(chamber["id"], "".join(full_text), word_count, len(passages))
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("done", {"word_count": word_count, "citation_count": len(passages)}),
            )
        except Exception as e:
            log.error("Kimi synthesis error: %s", e)
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    # Start producer in thread
    loop = asyncio.get_running_loop()
    task = loop.run_in_executor(None, _run_kimi)

    # 4. Consume from queue, yield SSE events
    try:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=120.0)
            if item is _SENTINEL:
                break
            event_type, event_data = item
            yield {
                "event": "message",
                "data": json.dumps({"type": event_type, "data": event_data}),
            }
    except asyncio.TimeoutError:
        log.error("Kimi synthesis timed out after 120s for chamber %s", chamber["id"])
        yield {
            "event": "message",
            "data": json.dumps({"type": "error", "data": "Synthesis timed out after 120 seconds."}),
        }
    except asyncio.CancelledError:
        log.info("SPEAK stream cancelled for chamber %s", chamber["id"])
        return
    finally:
        # Ensure the thread finishes (it will, since stream_kimi is finite)
        try:
            await asyncio.shield(task)
        except Exception:
            pass


# ── /hint ───────────────────────────────────────────────────────────────────
@router.post("/hint")
async def navigation_hint(req: HintRequest):
    """Short Hermes navigation hint when entering a chamber."""
    chamber: dict | None = None
    live = await _chamber_live(req.chamber_id)
    if live is not None:
        chamber = {
            "name_en":    live["name_en"],
            "text_count": live["text_count"],
            "term_eg":    live["term_eg"],
        }
    else:
        chamber = _get_chamber(req.chamber_id)
    if not chamber:
        return JSONResponse(status_code=404, content={"error": f"Chamber '{req.chamber_id}' not found"})

    prompt = EXPLORE_NAVIGATION_HINT.format(
        chamber_name=chamber["name_en"],
        text_count=chamber["text_count"],
        chamber_concept=chamber["term_eg"],
    )

    hint = await asyncio.to_thread(
        call_hermes_plain,
        [{"role": "system", "content": prompt}],
    )
    return {"hint": hint, "chamber_id": req.chamber_id}


# ── /ws_agent (Oracle WebSocket — Hermes-agent with tool streaming) ──────────
@router.websocket("/ws_agent")
async def oracle_agent_websocket(websocket: WebSocket):
    await websocket.accept()

    async def emit(evt: dict) -> None:
        await websocket.send_json(evt)

    agent = OracleAgent(ORACLE_AGENT_SYSTEM_PROMPT, emit)
    await emit({"type": "ready", "model": "Hermes-4-70B", "version": "v4.0"})

    try:
        while True:
            data = await websocket.receive_json()
            user_msg = (data.get("message") or "").strip()
            current_chamber = data.get("chamber_id") or ""
            if not user_msg:
                continue
            if current_chamber:
                hall = await asyncio.to_thread(chamber_by_id, current_chamber)
                if hall is not None:
                    term_eg = " · ".join(
                        lr.form for lr in hall.defining_lemmata[:3]
                    )
                    user_msg = (
                        f"[User is in chamber {hall.chamber_id}: "
                        f"{hall.name_en} ({term_eg}); "
                        f"level L{hall.level_id}; {hall.text_count} texts]\n\n"
                        + user_msg
                    )
                else:
                    ch = _get_chamber(current_chamber)
                    if ch:
                        user_msg = (
                            f"[User is in chamber {ch['id']}: "
                            f"{ch.get('name_en','')} ({ch.get('term_eg','')})]\n\n"
                            + user_msg
                        )
            try:
                await asyncio.wait_for(agent.turn(user_msg), timeout=60.0)
            except asyncio.TimeoutError:
                await emit({
                    "type": "final",
                    "text": "The Oracle needs a moment — the Labyrinth is vast. Try a tighter question.",
                })
            except Exception as e:
                log.exception("agent turn failed")
                await emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
            agent.compact_history()
    except WebSocketDisconnect:
        log.info("Oracle agent WebSocket disconnected")
    except Exception as e:
        log.error("Oracle agent WebSocket error: %s", e)
