"""SQLAlchemy base and engine setup."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.environ.get("DB_URL", "postgresql://aegyptus:dev@localhost:5434/aegyptus")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
