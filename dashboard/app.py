"""FastAPI dashboard application for corpus health monitoring."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from core.models import SessionLocal

from . import queries

TEMPLATE_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="Aegyptus Dashboard", version="0.1.0")
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def _fmt_number(value: int) -> str:
    """Format number with comma separators."""
    return f"{value:,}"


jinja_env.filters["fmt_number"] = _fmt_number


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Main dashboard page with all corpus statistics."""
    session = SessionLocal()
    try:
        context = {
            "overview": queries.get_corpus_overview(session),
            "gaps": queries.get_gap_statistics(session),
            "sources": queries.get_source_breakdown(session),
            "confidence": queries.get_confidence_distribution(session),
            "recent": queries.get_recent_activity(session),
            "layer_coverage": queries.get_layer_coverage(session),
            "sentences_by_source": queries.get_sentences_by_source(session),
            "layers_by_source": queries.get_layers_by_source(session),
        }
        template = jinja_env.get_template("dashboard.html")
        return HTMLResponse(template.render(**context))
    finally:
        session.close()


@app.get("/api/overview")
async def api_overview():
    """JSON API for corpus overview stats."""
    session = SessionLocal()
    try:
        return queries.get_corpus_overview(session)
    finally:
        session.close()


@app.get("/api/gaps")
async def api_gaps():
    """JSON API for gap statistics."""
    session = SessionLocal()
    try:
        return queries.get_gap_statistics(session)
    finally:
        session.close()


@app.get("/api/sources")
async def api_sources():
    """JSON API for source breakdown."""
    session = SessionLocal()
    try:
        return queries.get_source_breakdown(session)
    finally:
        session.close()
