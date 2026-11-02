"""Pydantic schemas for API serialization and validation.

Canonical read-only schemas for corpus entities (Text, Sentence, Concordance,
Alias, RepresentationLayer).  API-layer response wrappers live in api/schemas.py.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TextBase(BaseModel):
    canonical_id: str
    conventional_name: str | None = None
    script_type: str | None = None
    date_earliest: int | None = None
    date_latest: int | None = None
    period_label: str | None = None
    findspot: str | None = None
    current_location: str | None = None
    text_type: str | None = None
    completeness: str | None = None
    shelfmarks: list[str] | None = None
    metadata: dict[str, Any] | None = Field(None, alias="extra_metadata")


class TextRead(TextBase):
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SentenceBase(BaseModel):
    canonical_id: str
    sequence_num: int | None = None
    transliteration: str | None = None
    translation: dict[str, Any] | None = None
    tokens: list[dict[str, Any]] | None = None
    source: str | None = None
    source_id: str | None = None
    source_detail: dict[str, Any] | None = None
    confidence: str = "verified"


class SentenceRead(SentenceBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConcordanceBase(BaseModel):
    canonical_id: str
    external_system: str
    external_id: str
    relationship: str = "exact_match"


class ConcordanceRead(ConcordanceBase):
    id: int

    model_config = {"from_attributes": True}


class AliasBase(BaseModel):
    canonical_id: str
    alias_text: str
    alias_normalized: str
    alias_type: str
    confidence: str = "auto"


class AliasRead(AliasBase):
    id: int

    model_config = {"from_attributes": True}


class RepresentationLayerBase(BaseModel):
    canonical_id: str
    layer_type: str
    content: dict[str, Any] | None = None
    language: str | None = None
    source: str | None = None
    source_detail: dict[str, Any] | None = None
    confidence: str = "verified"


class RepresentationLayerRead(RepresentationLayerBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


