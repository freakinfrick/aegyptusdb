"""Nous Portal unified API client — Hermes-4-70B + Kimi K2.5."""

import json
import logging
import os
from typing import Generator

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from inference.models import (
    NOUS_BASE_URL,
    ORCHESTRATOR,
    ORCHESTRATOR_FALLBACK,
    SYNTHESISER,
    SYNTHESISER_FALLBACK,
)

log = logging.getLogger(__name__)


def _load_env():
    """Load .env if NOUS_API_KEY not already set."""
    if os.environ.get("NOUS_API_KEY"):
        return
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k] = v


_load_env()

_client = OpenAI(
    # Placeholder keeps the API importable without a key; model calls then fail with 401.
    api_key=os.environ.get("NOUS_API_KEY") or "unset",
    base_url=NOUS_BASE_URL,
)


def call_hermes(
    messages: list[ChatCompletionMessageParam],
    json_mode: bool = True,
    max_tokens: int = 800,
    temperature: float = 0.3,
    model: str | None = None,
) -> str:
    """Non-streaming Hermes-4-70B call. Oracle + ranking decisions."""
    model = model or ORCHESTRATOR
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return resp.choices[0].message.content
    except Exception as e:
        log.warning("Hermes %s failed: %s — trying fallback", model, e)
        resp = _client.chat.completions.create(
            model=ORCHESTRATOR_FALLBACK,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return resp.choices[0].message.content


def call_hermes_plain(
    messages: list[ChatCompletionMessageParam],
    max_tokens: int = 300,
    temperature: float = 0.4,
) -> str:
    """Non-streaming, plain text (no JSON mode). For navigation hints."""
    return call_hermes(messages, json_mode=False, max_tokens=max_tokens, temperature=temperature)


def stream_kimi(
    messages: list[ChatCompletionMessageParam],
    max_tokens: int = 4096,
    temperature: float = 0.7,
    model: str | None = None,
) -> Generator[str, None, None]:
    """Streaming Kimi K2.5 synthesis. Yields text chunks."""
    model = model or SYNTHESISER
    try:
        stream = _client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        log.warning("Kimi %s failed: %s — trying fallback", model, e)
        stream = _client.chat.completions.create(
            model=SYNTHESISER_FALLBACK,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
