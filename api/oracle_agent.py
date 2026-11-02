"""
Oracle Agent — v4.0 §6.4.

A minimal Hermes-agent loop, one instance per WebSocket. Not the full
Hermes Agent harness. Streams tool_call / tool_result / final events to the
client so tool use is visible in the chat UI.

Streaming note: the Day-1 spike (scripts/spike_tool_calling.py) confirmed
Nous Portal buffers tool_call deltas — they arrive as one unit at finish.
So this loop uses non-streaming per-turn Hermes-4-70B calls and re-emits
events to the WS as tools execute. User-visible effect is identical.
"""

import asyncio
import json
import logging
import os
from typing import Awaitable, Callable

from openai import OpenAI

from inference.models import (
    NOUS_BASE_URL,
    ORCHESTRATOR,
    ORCHESTRATOR_FALLBACK,
)
from inference.tools import TOOL_REGISTRY, tool_schemas

log = logging.getLogger(__name__)

MAX_STEPS = 6  # hard cap on tool-call rounds per user turn

# Build a dedicated client here so the agent can use tool-calling without
# affecting the existing call_hermes() JSON-mode path.
_client = OpenAI(
    # Placeholder keeps the API importable without a key; model calls then fail with 401.
    api_key=os.environ.get("NOUS_API_KEY") or "unset",
    base_url=NOUS_BASE_URL,
)


EmitFn = Callable[[dict], Awaitable[None]]


def _parse_content_tool_calls(content: str) -> list:
    """Try to extract tool calls embedded in msg.content as JSON.

    Hermes-4-70B on Nous Portal sometimes returns structured tool calls as a
    JSON array/object in the content field rather than in msg.tool_calls.
    Accepted formats:
      - [{"id":"...","type":"function","function":{"name":"...","arguments":"..."}}]
      - {"name":"...","arguments":{...}}  (single object)
      - <tool_call>\n{...}\n</tool_call>  (some Hermes variants)
    Returns a list of mock tool-call objects with .id / .function.name /
    .function.arguments attributes.
    """
    if not content:
        return []

    class _Fn:
        def __init__(self, name, arguments): self.name = name; self.arguments = arguments

    class _TC:
        def __init__(self, id_, fn): self.id = id_; self.function = fn

    # Strip <tool_call> XML wrappers
    text = content.strip()
    if '<tool_call>' in text:
        import re
        blocks = re.findall(r'<tool_call>(.*?)</tool_call>', text, re.DOTALL)
        text = '[' + ','.join(b.strip() for b in blocks) + ']' if blocks else text

    # Try parsing JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    results = []
    items = parsed if isinstance(parsed, list) else [parsed]
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        # OpenAI-style: {"type":"function","function":{"name":...,"arguments":...}}
        if 'function' in item and isinstance(item['function'], dict):
            fn_data = item['function']
            name = fn_data.get('name', '')
            args = fn_data.get('arguments', '{}')
            if isinstance(args, dict):
                args = json.dumps(args)
            if name:
                results.append(_TC(item.get('id', f'cnt_{i}'), _Fn(name, args)))
        # Hermes flat style: {"name":...,"arguments":{...}}
        elif 'name' in item and item['name'] in {fn for fn in [
                'search_corpus','search_transliteration','show_text',
                'show_sentence','resolve_shelfmark','corpus_stats',
                'find_chamber','show_on_map','open_portal','speak',
                'read_article','tts']}:
            name = item['name']
            args = item.get('arguments', item.get('parameters', {}))
            if isinstance(args, dict):
                args = json.dumps(args)
            results.append(_TC(f'cnt_{i}', _Fn(name, args)))
    return results


def _clean_final_text(text: str) -> str:
    """Remove raw tool-call JSON that leaked into a final assistant message."""
    t = text.strip()
    if not t:
        return t
    # If the whole message is a JSON array starting with {"id" or {"type", discard it.
    if t.startswith('[{"') or t.startswith('{"id"') or t.startswith('{"type"'):
        try:
            json.loads(t)  # valid JSON—definitely a tool call blob
            return ''      # drop it entirely; model will be re-prompted
        except json.JSONDecodeError:
            pass
    # Strip <tool_call>...</tool_call> blocks
    import re
    t = re.sub(r'<tool_call>.*?</tool_call>', '', t, flags=re.DOTALL).strip()
    return t


class OracleAgent:
    """One agent per WS connection. Stateful: keeps turn history.

    `emit` is an async callable (e.g. websocket.send_json) — the loop pushes
    events of types: tool_call, tool_result, final, error.
    """

    def __init__(self, system_prompt: str, emit: EmitFn):
        self.emit = emit
        self.history: list[dict] = [{"role": "system", "content": system_prompt}]
        self.tools_schema = tool_schemas()

    async def _call_model(self, model: str):
        """One call to Hermes with tools, wrapped for asyncio."""
        return await asyncio.to_thread(
            _client.chat.completions.create,
            model=model,
            messages=self.history,
            tools=self.tools_schema,
            tool_choice="auto",
            max_tokens=800,
            temperature=0.3,
        )

    async def turn(self, user_msg: str) -> None:
        """Run one user→final round. Emits events as tools execute."""
        self.history.append({"role": "user", "content": user_msg})

        for step in range(MAX_STEPS):
            try:
                resp = await self._call_model(ORCHESTRATOR)
            except Exception as e:
                log.warning("Hermes primary failed (%s), trying fallback", e)
                try:
                    resp = await self._call_model(ORCHESTRATOR_FALLBACK)
                except Exception as e2:
                    await self.emit({"type": "error", "message": f"model call failed: {e2}"})
                    return

            msg = resp.choices[0].message
            tool_calls = msg.tool_calls or []

            # Some Nous Portal / Hermes versions embed tool calls as JSON in
            # msg.content instead of the structured tool_calls field.  Detect
            # and parse that so tool-use always works regardless of build.
            if not tool_calls and msg.content:
                tool_calls = _parse_content_tool_calls(msg.content) or []

            if not tool_calls:
                # Final assistant turn — strip any residual tool-call JSON.
                text = _clean_final_text(msg.content or "")
                self.history.append({"role": "assistant", "content": text})
                await self.emit({"type": "final", "text": text})
                return

            # Record the assistant turn (carries tool_calls).
            # msg.content may contain raw JSON when tool_calls came from content
            # parsing — clean it so the history doesn't carry JSON blobs.
            assistant_content = _clean_final_text(msg.content or "")
            self.history.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool call in order. Emit events for each.
            for tc in tool_calls:
                name = tc.function.name
                raw = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {}
                    await self.emit({
                        "type": "tool_error",
                        "name": name,
                        "message": f"invalid args JSON: {raw[:120]}",
                    })

                await self.emit({"type": "tool_call", "name": name, "args": args})

                entry = TOOL_REGISTRY.get(name)
                if entry is None:
                    result = {"error": f"unknown tool: {name}"}
                    await self.emit({"type": "tool_result", "name": name, "result": result})
                else:
                    fn, _schema = entry
                    try:
                        result = await fn(**args)
                    except TypeError as e:
                        result = {"error": f"bad args for {name}: {e}"}
                    except Exception as e:
                        log.exception("Tool %s raised", name)
                        result = {"error": f"{type(e).__name__}: {e}"}
                    await self.emit({"type": "tool_result", "name": name, "result": result})

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)[:8000],  # cap token bloat
                })
        # MAX_STEPS hit
        await self.emit({
            "type": "final",
            "text": "The Oracle spiralled too deep. Try a tighter question.",
        })

    def compact_history(self, keep_last: int = 18) -> None:
        """Trim middle history, keeping system + last N messages."""
        if len(self.history) <= keep_last + 1:
            return
        self.history = [self.history[0]] + self.history[-keep_last:]
