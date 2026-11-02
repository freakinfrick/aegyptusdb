"""Aegyptus unified query API."""

import mimetypes
import os
from pathlib import Path

from fastapi import FastAPI

# Register font mimetypes BEFORE StaticFiles is instantiated — it caches them.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import concordance, export, resolve, sentences, stats, texts
from api.hackathon import router as hackathon_router
from api.tts import router as tts_router

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app = FastAPI(
    title="Aegyptus API — The Labyrinth",
    description="Unified query API for the Aegyptus open corpus of ancient Egyptian texts",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(texts.router)
app.include_router(sentences.router)
app.include_router(concordance.router)
app.include_router(stats.router)
app.include_router(export.router)
app.include_router(resolve.router)
app.include_router(hackathon_router)
app.include_router(tts_router)

# Serve web frontend as static files
WEB_DIR = Path(__file__).parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/", tags=["health"])
def root():
    return {"service": "aegyptus-api", "version": "0.2.0", "docs": "/docs", "labyrinth": "/web/"}
