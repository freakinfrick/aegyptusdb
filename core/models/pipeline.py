"""Pipeline tables: crawl_queue, gaps."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class CrawlQueue(Base):
    __tablename__ = "crawl_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False)
    domain = Column(Text, nullable=False)
    content_type_hint = Column(Text)
    status = Column(Text, server_default="pending")
    fetched_at = Column(DateTime(timezone=True))
    object_store_key = Column(Text)
    extra_metadata = Column("metadata", JSONB)


class Gap(Base):
    __tablename__ = "gaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_id = Column(Text, ForeignKey("texts.canonical_id"))
    external_system = Column(Text, nullable=False)
    external_id = Column(Text, nullable=False)
    gap_type = Column(Text, nullable=False)
    priority = Column(Text, nullable=False)
    recommended_action = Column(Text)
    status = Column(Text, server_default="open")
    assigned_to = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_gaps_priority", "priority", "status"),
        Index("idx_gaps_canonical", "canonical_id"),
    )
