"""Shared FastAPI dependencies."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from core.models import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session, closing it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
