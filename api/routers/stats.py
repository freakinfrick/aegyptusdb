"""Corpus statistics endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import CorpusStats, LayerCoverage, SourceCount
from core.models import (
    Alias,
    Concordance,
    Gap,
    RepresentationLayer,
    Sentence,
    TextRecord,
)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("", response_model=CorpusStats)
def corpus_stats(db: Session = Depends(get_db)):
    texts = db.execute(select(func.count()).select_from(TextRecord)).scalar() or 0
    sentences = db.execute(select(func.count()).select_from(Sentence)).scalar() or 0
    layers = db.execute(select(func.count()).select_from(RepresentationLayer)).scalar() or 0
    concordance = db.execute(select(func.count()).select_from(Concordance)).scalar() or 0
    aliases = db.execute(select(func.count()).select_from(Alias)).scalar() or 0
    gaps = db.execute(select(func.count()).select_from(Gap)).scalar() or 0

    # Texts by source prefix
    text_src_rows = db.execute(sa_text(
        "SELECT split_part(canonical_id, '_', 2) AS src, count(*) "
        "FROM texts GROUP BY src ORDER BY count(*) DESC"
    )).fetchall()
    texts_by_source = [SourceCount(source=r[0], count=r[1]) for r in text_src_rows]

    # Sentences by source
    sent_src_rows = db.execute(
        select(Sentence.source, func.count())
        .group_by(Sentence.source)
        .order_by(func.count().desc())
    ).all()
    sentences_by_source = [SourceCount(source=r[0] or "unknown", count=r[1]) for r in sent_src_rows]

    # Layer coverage
    layer_rows = db.execute(sa_text(
        "SELECT layer_type, count(DISTINCT canonical_id), count(*) "
        "FROM representation_layers GROUP BY layer_type "
        "ORDER BY count(DISTINCT canonical_id) DESC"
    )).fetchall()
    layer_coverage = [
        LayerCoverage(layer_type=r[0], texts_covered=r[1], total_layers=r[2])
        for r in layer_rows
    ]

    return CorpusStats(
        texts=texts,
        sentences=sentences,
        layers=layers,
        concordance=concordance,
        aliases=aliases,
        gaps=gaps,
        texts_by_source=texts_by_source,
        sentences_by_source=sentences_by_source,
        layer_coverage=layer_coverage,
    )
