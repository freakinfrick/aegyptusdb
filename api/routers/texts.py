"""Text query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import TextDetail, TextListResponse
from core.models import Alias, Concordance, RepresentationLayer, Sentence, TextRecord
from core.schemas import (
    AliasRead,
    ConcordanceRead,
    RepresentationLayerRead,
    SentenceRead,
    TextRead,
)

router = APIRouter(prefix="/api/v1/texts", tags=["texts"])

SORT_COLUMNS = {
    "canonical_id": TextRecord.canonical_id,
    "conventional_name": TextRecord.conventional_name,
    "date_earliest": TextRecord.date_earliest,
}


@router.get("", response_model=TextListResponse)
def list_texts(
    q: str | None = Query(None, description="Full-text search on conventional_name"),
    script_type: str | None = Query(None),
    text_type: str | None = Query(None),
    period: str | None = Query(None, description="Filter by period_label (substring match)"),
    date_from: int | None = Query(None, description="Earliest date >= this value"),
    date_to: int | None = Query(None, description="Earliest date <= this value"),
    completeness: str | None = Query(None),
    findspot: str | None = Query(None, description="Substring match on findspot"),
    source: str | None = Query(None, description="Filter by canonical_id prefix"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("canonical_id", description="Sort field"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    stmt = select(TextRecord)

    if q:
        stmt = stmt.where(TextRecord.conventional_name.ilike(f"%{q}%"))
    if script_type:
        stmt = stmt.where(TextRecord.script_type == script_type)
    if text_type:
        stmt = stmt.where(TextRecord.text_type == text_type)
    if period:
        stmt = stmt.where(TextRecord.period_label.ilike(f"%{period}%"))
    if date_from is not None:
        stmt = stmt.where(TextRecord.date_earliest >= date_from)
    if date_to is not None:
        stmt = stmt.where(TextRecord.date_earliest <= date_to)
    if completeness:
        stmt = stmt.where(TextRecord.completeness == completeness)
    if findspot:
        stmt = stmt.where(TextRecord.findspot.ilike(f"%{findspot}%"))
    if source:
        stmt = stmt.where(TextRecord.canonical_id.like(f"{source}%"))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Sort
    sort_col = SORT_COLUMNS.get(sort_by, TextRecord.canonical_id)
    if order == "desc":
        sort_col = sort_col.desc()
    stmt = stmt.order_by(sort_col)

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = db.execute(stmt).scalars().all()
    pages = max(1, (total + page_size - 1) // page_size)

    return TextListResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[TextRead.model_validate(r) for r in rows],
    )


@router.get("/{canonical_id}", response_model=TextDetail)
def get_text(canonical_id: str, db: Session = Depends(get_db)):
    text_rec = db.execute(
        select(TextRecord).where(TextRecord.canonical_id == canonical_id)
    ).scalar_one_or_none()
    if not text_rec:
        raise HTTPException(404, f"Text {canonical_id!r} not found")

    layers = db.execute(
        select(RepresentationLayer)
        .where(RepresentationLayer.canonical_id == canonical_id)
        .order_by(RepresentationLayer.layer_type)
    ).scalars().all()

    sentences = db.execute(
        select(Sentence)
        .where(Sentence.canonical_id == canonical_id)
        .order_by(Sentence.sequence_num.nulls_last(), Sentence.id)
    ).scalars().all()

    concordance = db.execute(
        select(Concordance)
        .where(Concordance.canonical_id == canonical_id)
        .order_by(Concordance.external_system)
    ).scalars().all()

    aliases = db.execute(
        select(Alias)
        .where(Alias.canonical_id == canonical_id)
        .order_by(Alias.alias_type)
    ).scalars().all()

    return TextDetail(
        **TextRead.model_validate(text_rec).model_dump(),
        layers=[RepresentationLayerRead.model_validate(l) for l in layers],
        sentences=[SentenceRead.model_validate(s) for s in sentences],
        concordance=[ConcordanceRead.model_validate(c) for c in concordance],
        aliases=[AliasRead.model_validate(a) for a in aliases],
    )
