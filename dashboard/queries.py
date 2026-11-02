"""Database queries for the dashboard."""

from __future__ import annotations

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session


def get_corpus_overview(session: Session) -> dict:
    """Core corpus counts."""
    counts = {}
    for table in ["texts", "sentences", "representation_layers", "concordance", "aliases", "gaps"]:
        safe_table = table  # all are hardcoded, no injection risk
        row = session.execute(sa_text(f"SELECT count(*) FROM {safe_table}")).scalar()
        counts[table] = row or 0
    return counts


def get_gap_statistics(session: Session) -> list[dict]:
    """Gap counts by type and priority."""
    rows = session.execute(sa_text("""
        SELECT gap_type, priority, status, count(*)
        FROM gaps
        GROUP BY gap_type, priority, status
        ORDER BY priority, gap_type
    """)).fetchall()
    return [
        {"gap_type": r[0], "priority": r[1], "status": r[2], "count": r[3]}
        for r in rows
    ]


def get_source_breakdown(session: Session) -> list[dict]:
    """Text counts by source prefix."""
    rows = session.execute(sa_text("""
        SELECT split_part(canonical_id, '_', 2) AS source, count(*)
        FROM texts
        GROUP BY source
        ORDER BY count(*) DESC
    """)).fetchall()
    return [{"source": r[0], "count": r[1]} for r in rows]


def get_confidence_distribution(session: Session) -> dict:
    """Confidence distribution across layers and sentences."""
    layer_rows = session.execute(sa_text("""
        SELECT confidence, count(*) FROM representation_layers GROUP BY confidence ORDER BY confidence
    """)).fetchall()

    sentence_rows = session.execute(sa_text("""
        SELECT confidence, count(*) FROM sentences GROUP BY confidence ORDER BY confidence
    """)).fetchall()

    return {
        "layers": [{"confidence": r[0], "count": r[1]} for r in layer_rows],
        "sentences": [{"confidence": r[0], "count": r[1]} for r in sentence_rows],
    }


def get_recent_activity(session: Session, limit: int = 10) -> list[dict]:
    """Most recently created texts."""
    rows = session.execute(sa_text("""
        SELECT canonical_id, conventional_name, script_type, period_label, created_at
        FROM texts
        ORDER BY created_at DESC
        LIMIT :lim
    """), {"lim": limit}).fetchall()
    return [
        {
            "canonical_id": r[0],
            "name": r[1] or "(unnamed)",
            "script_type": r[2] or "unknown",
            "period": r[3] or "unknown",
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


def get_layer_coverage(session: Session) -> list[dict]:
    """How many texts have each layer type."""
    rows = session.execute(sa_text("""
        SELECT layer_type, count(DISTINCT canonical_id), count(*)
        FROM representation_layers
        GROUP BY layer_type
        ORDER BY count(DISTINCT canonical_id) DESC
    """)).fetchall()
    return [
        {"layer_type": r[0], "texts_covered": r[1], "total_layers": r[2]}
        for r in rows
    ]


def get_sentences_by_source(session: Session) -> list[dict]:
    """Sentence counts by source."""
    rows = session.execute(sa_text("""
        SELECT source, count(*) FROM sentences GROUP BY source ORDER BY count(*) DESC
    """)).fetchall()
    return [{"source": r[0], "count": r[1]} for r in rows]


def get_layers_by_source(session: Session) -> list[dict]:
    """Layer counts by source."""
    rows = session.execute(sa_text("""
        SELECT source, count(*) FROM representation_layers GROUP BY source ORDER BY count(*) DESC
    """)).fetchall()
    return [{"source": r[0], "count": r[1]} for r in rows]
