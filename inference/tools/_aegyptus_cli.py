"""Thin asyncio wrapper around the aegyptus CLI.

Every Oracle tool that reads the corpus goes through this module. One code
path, one place to add caching / rate-limits / instrumentation.

The aegyptus CLI entry-point is cli.py at the repo root (click group);
we call it via `python3 cli.py <cmd> ...` in the repo root because the
console script entry-point (.venv/bin/aegyptus) fails to resolve the
sibling `rosetta` module in this checkout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AEGYPTUS_ROOT = Path(os.environ.get("AEGYPTUS_ROOT", Path(__file__).resolve().parents[2]))
AEGYPTUS_PY = AEGYPTUS_ROOT / ".venv" / "bin" / "python3"
AEGYPTUS_CLI = AEGYPTUS_ROOT / "cli.py"

# Prefer .venv python, fall back to system python3.
_PY = str(AEGYPTUS_PY) if AEGYPTUS_PY.exists() else (shutil.which("python3") or "python3")

# Default timeout. Most commands return in <2s; we cap long queries.
DEFAULT_TIMEOUT = 20.0


class AegyptusCliError(RuntimeError):
    """Raised when the CLI exits with an unexpected status or yields no JSON."""


async def run(
    *args: str,
    timeout: float = DEFAULT_TIMEOUT,
    expect_json: bool = True,
) -> Any:
    """Invoke `aegyptus <args...>`, return parsed JSON (or raw text).

    Exit codes per the CLI contract:
        0 → success
        1 → error (raises AegyptusCliError)
        2 → no results (returns empty structure without raising)
    """
    cmd = [_PY, str(AEGYPTUS_CLI), *args]
    env = {**os.environ, "PYTHONPATH": str(AEGYPTUS_ROOT)}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(AEGYPTUS_ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise AegyptusCliError(f"aegyptus python not found: {_PY}") from e

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AegyptusCliError(f"aegyptus {' '.join(args[:2])}… timed out after {timeout}s")

    code = proc.returncode or 0
    # Exit 2 = no results; CLI still prints valid JSON (usually empty array).
    if code not in (0, 2):
        msg = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise AegyptusCliError(
            f"aegyptus exited {code}: {msg[:400] or '(no stderr)'}"
        )

    if not expect_json:
        return (stdout or b"").decode("utf-8", errors="replace")

    text = (stdout or b"").decode("utf-8", errors="replace").strip()
    if not text:
        return [] if code == 2 else {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("aegyptus output not JSON: %s", text[:200])
        raise AegyptusCliError(f"non-JSON output from aegyptus: {e}") from e


# ── Common wrappers ─────────────────────────────────────────────────────
async def grep(
    pattern: str,
    *,
    field: str = "translation",
    source: str | None = None,
    limit: int = 10,
) -> list[dict]:
    args = ["grep", pattern, "--field", field, "--limit", str(limit)]
    if source:
        args += ["--source", source]
    data = await run(*args)
    if isinstance(data, list):
        return data
    return []


async def show_text(canonical_id: str) -> dict:
    data = await run("show", "--text", canonical_id)
    if isinstance(data, dict):
        return data
    return {}


async def show_sentence(sentence_id: int) -> dict:
    data = await run("show", "--sentence", str(sentence_id))
    if isinstance(data, dict):
        return data
    return {}


async def resolve(
    *,
    shelfmark: str | None = None,
    system: str | None = None,
    ext_id: str | None = None,
) -> dict:
    if shelfmark:
        data = await run("resolve", "--shelfmark", shelfmark)
    elif system and ext_id:
        data = await run("resolve", "--system", system, "--id", ext_id)
    else:
        raise AegyptusCliError("resolve needs --shelfmark or --system+--id")
    return data if isinstance(data, dict) else {}


async def status() -> dict:
    data = await run("status")
    return data if isinstance(data, dict) else {}
