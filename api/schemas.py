"""API-specific Pydantic response schemas."""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from core.schemas import (
    AliasRead,
    ConcordanceRead,
    RepresentationLayerRead,
    SentenceRead,
    TextRead,
)


# ---- Pagination wrapper ----

_T = TypeVar("_T", bound=BaseModel)


class PaginatedResponse(BaseModel, Generic[_T]):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[_T]


class TextListResponse(PaginatedResponse[TextRead]):
    items: list[TextRead]


class SentenceListResponse(PaginatedResponse[SentenceRead]):
    items: list[SentenceRead]


# ---- Detail views ----

class TextDetail(TextRead):
    """Single text with all related data."""
    layers: list[RepresentationLayerRead] = []
    sentences: list[SentenceRead] = []
    concordance: list[ConcordanceRead] = []
    aliases: list[AliasRead] = []


class SentenceDetail(SentenceRead):
    """Single sentence with parent text info."""
    text_canonical_id: str | None = None
    text_conventional_name: str | None = None


# ---- Stats ----

class SourceCount(BaseModel):
    source: str
    count: int


class LayerCoverage(BaseModel):
    layer_type: str
    texts_covered: int
    total_layers: int


class CorpusStats(BaseModel):
    texts: int
    sentences: int
    layers: int
    concordance: int
    aliases: int
    gaps: int
    texts_by_source: list[SourceCount]
    sentences_by_source: list[SourceCount]
    layer_coverage: list[LayerCoverage]


# ---- Cross-reference resolution ----

class LayerSummary(BaseModel):
    layer_type: str
    count: int


class ResolvedRecord(BaseModel):
    canonical_id: str
    conventional_name: str | None = None
    script_type: str | None = None
    period_label: str | None = None
    concordance: list[ConcordanceRead] = []
    layers_summary: list[LayerSummary] = []


class ResolveResponse(BaseModel):
    query_system: str
    query_id: str
    matches: list[ResolvedRecord]
