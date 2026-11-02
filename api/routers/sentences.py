"""Sentence query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import SentenceDetail, SentenceListResponse
from core.models import Sentence, TextRecord
from core.schemas import SentenceRead

router = APIRouter(prefix="/api/v1/sentences", tags=["sentences"])


@router.get("", response_model=SentenceListResponse)
def list_sentences(
    q: str | None = Query(None, description="Search transliteration (substring)"),
    lemma_id: str | None = Query(None, description="Filter by lemma ID in tokens"),
    language: str | None = Query(None, description="Filter by translation language key"),
    source: str | None = Query(None, description="Filter by source"),
    confidence: str | None = Query(None),
    canonical_id: str | None = Query(None, description="Filter by parent text"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Sentence)

    if q:
        stmt = stmt.where(Sentence.transliteration.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Sentence.source == source)
    if confidence:
        stmt = stmt.where(Sentence.confidence == confidence)
    if canonical_id:
        stmt = stmt.where(Sentence.canonical_id == canonical_id)
    if language:
        # translation is JSONB {lang: text} -- filter for key existence
        stmt = stmt.where(Sentence.translation.has_key(language))
    if lemma_id:
        # tokens is JSONB array -- search for lemma_id inside token objects
        # Uses PostgreSQL JSONB containment: any token with matching lemma
        stmt = stmt.where(
            Sentence.tokens.op("@>")(f'[{{"lemma": "{lemma_id}"}}]')
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(Sentence.canonical_id, Sentence.sequence_num.nulls_last(), Sentence.id)
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = db.execute(stmt).scalars().all()
    pages = max(1, (total + page_size - 1) // page_size)

    return SentenceListResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[SentenceRead.model_validate(r) for r in rows],
    )


@router.get("/{sentence_id}", response_model=SentenceDetail)
def get_sentence(sentence_id: int, db: Session = Depends(get_db)):
    sentence = db.execute(
        select(Sentence).where(Sentence.id == sentence_id)
    ).scalar_one_or_none()
    if not sentence:
        raise HTTPException(404, f"Sentence {sentence_id} not found")

    text_rec = db.execute(
        select(TextRecord.canonical_id, TextRecord.conventional_name)
        .where(TextRecord.canonical_id == sentence.canonical_id)
    ).one_or_none()

    data = SentenceRead.model_validate(sentence).model_dump()
    data["text_canonical_id"] = text_rec[0] if text_rec else None
    data["text_conventional_name"] = text_rec[1] if text_rec else None

    return SentenceDetail(**data)
