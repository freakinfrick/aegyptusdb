"""Cross-reference resolution API."""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import LayerSummary, ResolvedRecord, ResolveResponse
from core.models import Alias, Concordance, RepresentationLayer, TextRecord
from core.schemas import ConcordanceRead

router = APIRouter(prefix="/api/v1/resolve", tags=["resolve"])


# Shelfmark route MUST come before the generic {system}/{ext_id} route
# so FastAPI matches the literal "shelfmark" prefix first.

@router.get("/shelfmark/{shelfmark:path}", response_model=ResolveResponse)
def resolve_shelfmark(
    shelfmark: str,
    db: Session = Depends(get_db),
):
    normalized = _normalize_shelfmark(shelfmark)

    # Search aliases table for shelfmark type
    alias_rows = db.execute(
        select(Alias.canonical_id)
        .where(Alias.alias_type == "shelfmark")
        .where(Alias.alias_normalized.ilike(f"%{normalized}%"))
    ).scalars().all()

    # Also search the texts.shelfmarks array with substring match
    text_rows = db.execute(
        sa_text(
            "SELECT canonical_id FROM texts "
            "WHERE EXISTS (SELECT 1 FROM unnest(shelfmarks) s WHERE lower(s) LIKE :pattern)"
        ),
        {"pattern": f"%{normalized}%"},
    ).scalars().all()

    canonical_ids = sorted(set(alias_rows) | set(text_rows))
    if not canonical_ids:
        raise HTTPException(404, f"No records found for shelfmark {shelfmark!r}")

    matches = [_build_record(cid, db) for cid in canonical_ids]

    return ResolveResponse(
        query_system="shelfmark",
        query_id=shelfmark,
        matches=matches,
    )


@router.get("/{system}/{ext_id}", response_model=ResolveResponse)
def resolve_external_id(
    system: str,
    ext_id: str,
    db: Session = Depends(get_db),
):
    lookup_systems = _expand_system(system)

    rows = db.execute(
        select(Concordance)
        .where(Concordance.external_system.in_(lookup_systems))
        .where(Concordance.external_id == ext_id)
    ).scalars().all()

    if not rows:
        raise HTTPException(404, f"No records found for {system}/{ext_id}")

    canonical_ids = list({r.canonical_id for r in rows})
    matches = [_build_record(cid, db) for cid in sorted(canonical_ids)]

    return ResolveResponse(
        query_system=system,
        query_id=ext_id,
        matches=matches,
    )


def _build_record(canonical_id: str, db: Session) -> ResolvedRecord:
    text_rec = db.execute(
        select(TextRecord).where(TextRecord.canonical_id == canonical_id)
    ).scalar_one_or_none()

    all_conc = db.execute(
        select(Concordance)
        .where(Concordance.canonical_id == canonical_id)
        .order_by(Concordance.external_system)
    ).scalars().all()

    layer_summary = db.execute(
        select(RepresentationLayer.layer_type, func.count())
        .where(RepresentationLayer.canonical_id == canonical_id)
        .group_by(RepresentationLayer.layer_type)
        .order_by(RepresentationLayer.layer_type)
    ).all()

    return ResolvedRecord(
        canonical_id=canonical_id,
        conventional_name=text_rec.conventional_name if text_rec else None,
        script_type=text_rec.script_type if text_rec else None,
        period_label=text_rec.period_label if text_rec else None,
        concordance=[ConcordanceRead.model_validate(c) for c in all_conc],
        layers_summary=[LayerSummary(layer_type=r[0], count=r[1]) for r in layer_summary],
    )


def _expand_system(system: str) -> list[str]:
    """Map user-facing system name to all concordance.external_system values that match."""
    mapping = {
        "tla": ["tla", "tla_hf", "tla_entity_date", "tla_entity_location",
                 "tla_entity_objecttype", "tla_entity_origplace"],
        "trismegistos": ["trismegistos", "TM"],
        "aes": ["aes", "aes_sentence"],
        "oraec": ["oraec"],
        "ramses": ["ramses"],
        "wikidata": ["wikidata"],
        "karnak": ["karnak"],
        "papyri_info": ["papyri_info"],
        "nederhof": ["nederhof"],
    }
    return mapping.get(system.lower(), [system])


def _normalize_shelfmark(s: str) -> str:
    """Basic shelfmark normalization: lowercase, collapse whitespace, strip punctuation variance."""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s
