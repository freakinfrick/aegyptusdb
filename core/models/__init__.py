"""Aegyptus data models."""

from .base import Base, SessionLocal, engine
from .corpus import (
    Alias,
    Concordance,
    Lemma,
    RepresentationLayer,
    RosettaLemmaIndex,
    Sentence,
    TextRecord,
    ThothLexicon,
)
from .operations import CorpusVersion
from .pipeline import CrawlQueue, Gap

# Public alias matching the table name for ergonomic imports
Text = TextRecord

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "Text",
    "TextRecord",
    "Sentence",
    "Concordance",
    "Alias",
    "RepresentationLayer",
    "Lemma",
    "ThothLexicon",
    "RosettaLemmaIndex",
    "CrawlQueue",
    "Gap",
    "CorpusVersion",
]
