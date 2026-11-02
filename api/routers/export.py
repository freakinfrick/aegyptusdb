"""Bulk export endpoints with streaming responses."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Generator

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from core.models import Concordance, RepresentationLayer, Sentence, TextRecord

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ---- Texts ----

@router.get("/texts")
def export_texts(
    format: str = Query("json", pattern="^(json|csv|tei)$"),
    script_type: str | None = Query(None),
    source: str | None = Query(None, description="canonical_id prefix"),
    text_type: str | None = Query(None),
    period: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(TextRecord)
    if script_type:
        stmt = stmt.where(TextRecord.script_type == script_type)
    if source:
        stmt = stmt.where(TextRecord.canonical_id.like(f"{source}%"))
    if text_type:
        stmt = stmt.where(TextRecord.text_type == text_type)
    if period:
        stmt = stmt.where(TextRecord.period_label.ilike(f"%{period}%"))
    stmt = stmt.order_by(TextRecord.canonical_id)

    if format == "tei":
        return _stream_tei(stmt, db)
    elif format == "csv":
        return _stream_csv(
            stmt, db,
            columns=["canonical_id", "conventional_name", "script_type", "text_type",
                      "period_label", "date_earliest", "date_latest", "findspot",
                      "current_location", "completeness"],
            filename="texts.csv",
        )
    else:
        return _stream_json(stmt, db, _text_to_dict, "texts.json")


# ---- Sentences ----

@router.get("/sentences")
def export_sentences(
    format: str = Query("json", pattern="^(json|csv)$"),
    source: str | None = Query(None),
    canonical_id: str | None = Query(None),
    confidence: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Sentence)
    if source:
        stmt = stmt.where(Sentence.source == source)
    if canonical_id:
        stmt = stmt.where(Sentence.canonical_id == canonical_id)
    if confidence:
        stmt = stmt.where(Sentence.confidence == confidence)
    stmt = stmt.order_by(Sentence.canonical_id, Sentence.sequence_num.nulls_last())

    if format == "csv":
        return _stream_csv(
            stmt, db,
            columns=["id", "canonical_id", "sequence_num", "transliteration",
                      "source", "source_id", "confidence"],
            filename="sentences.csv",
        )
    else:
        return _stream_json(stmt, db, _sentence_to_dict, "sentences.json")


# ---- Concordance ----

@router.get("/concordance")
def export_concordance(
    format: str = Query("json", pattern="^(json|csv)$"),
    external_system: str | None = Query(None),
    canonical_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Concordance)
    if external_system:
        stmt = stmt.where(Concordance.external_system == external_system)
    if canonical_id:
        stmt = stmt.where(Concordance.canonical_id == canonical_id)
    stmt = stmt.order_by(Concordance.canonical_id, Concordance.external_system)

    if format == "csv":
        return _stream_csv(
            stmt, db,
            columns=["id", "canonical_id", "external_system", "external_id", "relationship"],
            filename="concordance.csv",
        )
    else:
        return _stream_json(stmt, db, _concordance_to_dict, "concordance.json")


# ---- Streaming helpers ----

BATCH = 1000


def _stream_json(stmt, db: Session, to_dict, filename: str) -> StreamingResponse:
    def generate() -> Generator[str, None, None]:
        yield "["
        first = True
        offset = 0
        while True:
            rows = db.execute(stmt.offset(offset).limit(BATCH)).scalars().all()
            if not rows:
                break
            for row in rows:
                if not first:
                    yield ","
                yield json.dumps(to_dict(row), ensure_ascii=False, default=str)
                first = False
            offset += BATCH
            if len(rows) < BATCH:
                break
        yield "]"

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stream_csv(stmt, db: Session, columns: list[str], filename: str) -> StreamingResponse:
    def generate() -> Generator[str, None, None]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        offset = 0
        while True:
            rows = db.execute(stmt.offset(offset).limit(BATCH)).scalars().all()
            if not rows:
                break
            for row in rows:
                vals = [getattr(row, c, None) for c in columns]
                writer.writerow([_csv_safe(v) for v in vals])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            offset += BATCH
            if len(rows) < BATCH:
                break

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stream_tei(stmt, db: Session) -> StreamingResponse:
    """Generate TEI-XML corpus export."""

    def generate() -> Generator[str, None, None]:
        yield '<?xml version="1.0" encoding="UTF-8"?>\n'
        yield '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        yield '  <teiHeader>\n'
        yield '    <fileDesc>\n'
        yield '      <titleStmt><title>Aegyptus Corpus Export</title></titleStmt>\n'
        yield '      <publicationStmt><p>Exported from Aegyptus open corpus</p></publicationStmt>\n'
        yield '      <sourceDesc><p>Multi-source aggregated Egyptian text corpus</p></sourceDesc>\n'
        yield '    </fileDesc>\n'
        yield '  </teiHeader>\n'
        yield '  <text>\n'
        yield '    <body>\n'

        offset = 0
        while True:
            rows = db.execute(stmt.offset(offset).limit(BATCH)).scalars().all()
            if not rows:
                break
            for text_rec in rows:
                yield _tei_text_element(text_rec, db)
            offset += BATCH
            if len(rows) < BATCH:
                break

        yield '    </body>\n'
        yield '  </text>\n'
        yield '</TEI>\n'

    return StreamingResponse(
        generate(),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="corpus.tei.xml"'},
    )


def _tei_text_element(text_rec: TextRecord, db: Session) -> str:
    """Build a TEI <div> element for one text."""
    cid = text_rec.canonical_id
    name = _xml_escape(text_rec.conventional_name or cid)
    lines = []
    lines.append(f'      <div type="text" xml:id="{_xml_escape(cid)}">\n')
    lines.append(f'        <head>{name}</head>\n')

    # Metadata
    if text_rec.script_type or text_rec.period_label or text_rec.findspot:
        lines.append('        <note type="metadata">\n')
        if text_rec.script_type:
            lines.append(f'          <term type="script">{_xml_escape(text_rec.script_type)}</term>\n')
        if text_rec.period_label:
            lines.append(f'          <date>{_xml_escape(text_rec.period_label)}</date>\n')
        if text_rec.findspot:
            lines.append(f'          <placeName type="findspot">{_xml_escape(text_rec.findspot)}</placeName>\n')
        if text_rec.date_earliest is not None:
            lines.append(f'          <date type="earliest" when="{text_rec.date_earliest}"/>\n')
        if text_rec.date_latest is not None:
            lines.append(f'          <date type="latest" when="{text_rec.date_latest}"/>\n')
        lines.append('        </note>\n')

    # Layers
    layers = db.execute(
        select(RepresentationLayer)
        .where(RepresentationLayer.canonical_id == cid)
        .order_by(RepresentationLayer.layer_type)
    ).scalars().all()

    for layer in layers:
        ltype = _xml_escape(layer.layer_type)
        src = _xml_escape(layer.source or "unknown")
        conf = _xml_escape(layer.confidence or "unknown")
        content_str = ""
        if layer.content:
            if isinstance(layer.content, dict) and "text" in layer.content:
                content_str = _xml_escape(str(layer.content["text"]))
            elif isinstance(layer.content, dict) and "lines" in layer.content:
                content_str = _xml_escape("\n".join(str(ln) for ln in layer.content["lines"]))
            else:
                content_str = _xml_escape(json.dumps(layer.content, ensure_ascii=False, default=str))
        lang_attr = f' xml:lang="{_xml_escape(layer.language)}"' if layer.language else ""
        lines.append(
            f'        <ab type="{ltype}" source="{src}" cert="{conf}"{lang_attr}>'
            f'{content_str}</ab>\n'
        )

    lines.append('      </div>\n')
    return "".join(lines)


# ---- Serializers ----

def _text_to_dict(r: TextRecord) -> dict[str, Any]:
    return {
        "canonical_id": r.canonical_id,
        "conventional_name": r.conventional_name,
        "script_type": r.script_type,
        "text_type": r.text_type,
        "date_earliest": r.date_earliest,
        "date_latest": r.date_latest,
        "period_label": r.period_label,
        "findspot": r.findspot,
        "current_location": r.current_location,
        "completeness": r.completeness,
        "shelfmarks": r.shelfmarks,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _sentence_to_dict(r: Sentence) -> dict[str, Any]:
    return {
        "id": r.id,
        "canonical_id": r.canonical_id,
        "sequence_num": r.sequence_num,
        "transliteration": r.transliteration,
        "translation": r.translation,
        "tokens": r.tokens,
        "source": r.source,
        "source_id": r.source_id,
        "source_detail": r.source_detail,
        "confidence": r.confidence,
        "created_at": r.created_at,
    }


def _concordance_to_dict(r: Concordance) -> dict[str, Any]:
    return {
        "id": r.id,
        "canonical_id": r.canonical_id,
        "external_system": r.external_system,
        "external_id": r.external_id,
        "relationship": r.relationship,
    }


def _csv_safe(val: str | int | list | dict | None) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False, default=str)
    return str(val)


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
