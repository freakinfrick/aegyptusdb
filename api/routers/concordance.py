"""Concordance, alias, and layer lookup endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from core.models import Alias, Concordance, RepresentationLayer, TextRecord
from core.schemas import AliasRead, ConcordanceRead, RepresentationLayerRead

router = APIRouter(prefix="/api/v1", tags=["concordance"])


@router.get("/concordance/{canonical_id}", response_model=list[ConcordanceRead])
def get_concordance(canonical_id: str, db: Session = Depends(get_db)):
    _require_text(canonical_id, db)
    rows = db.execute(
        select(Concordance)
        .where(Concordance.canonical_id == canonical_id)
        .order_by(Concordance.external_system)
    ).scalars().all()
    return [ConcordanceRead.model_validate(r) for r in rows]


@router.get("/aliases/{canonical_id}", response_model=list[AliasRead])
def get_aliases(canonical_id: str, db: Session = Depends(get_db)):
    _require_text(canonical_id, db)
    rows = db.execute(
        select(Alias)
        .where(Alias.canonical_id == canonical_id)
        .order_by(Alias.alias_type)
    ).scalars().all()
    return [AliasRead.model_validate(r) for r in rows]


@router.get("/layers/{canonical_id}", response_model=list[RepresentationLayerRead])
def get_layers(canonical_id: str, db: Session = Depends(get_db)):
    _require_text(canonical_id, db)
    rows = db.execute(
        select(RepresentationLayer)
        .where(RepresentationLayer.canonical_id == canonical_id)
        .order_by(RepresentationLayer.layer_type)
    ).scalars().all()
    return [RepresentationLayerRead.model_validate(r) for r in rows]


def _require_text(canonical_id: str, db: Session) -> None:
    exists = db.execute(
        select(TextRecord.canonical_id).where(TextRecord.canonical_id == canonical_id)
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, f"Text {canonical_id!r} not found")
