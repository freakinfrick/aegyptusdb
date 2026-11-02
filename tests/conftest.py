"""Shared fixtures for Aegyptus integration tests.

Uses the LIVE database -- these tests verify real data imported
by previous agents (W1-W9).
"""

import pytest
from sqlalchemy.orm import Session

from core.models import SessionLocal


@pytest.fixture(scope="session")
def db() -> Session:
    """Yield a DB session for the full test session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def db_counts(db: Session) -> dict[str, int]:
    """Pre-fetch all table counts once for the test session."""
    from sqlalchemy import text
    tables = ["texts", "sentences", "concordance", "representation_layers", "aliases", "gaps", "crawl_queue", "corpus_versions"]
    counts = {}
    for t in tables:
        row = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
        counts[t] = row or 0
    return counts
