"""Operations tables: corpus_versions."""

from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class CorpusVersion(Base):
    __tablename__ = "corpus_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_tag = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(Text)
    text_count = Column(Integer)
    sentence_count = Column(Integer)
    layer_count = Column(Integer)
    concordance_count = Column(Integer)
    alias_count = Column(Integer)
    export_key = Column(Text)
    extra_metadata = Column("metadata", JSONB)
