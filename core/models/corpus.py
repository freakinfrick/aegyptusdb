"""Core corpus tables: texts, sentences, concordance, aliases, representation_layers."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from .base import Base


class TextRecord(Base):
    __tablename__ = "texts"

    canonical_id = Column(Text, primary_key=True)
    conventional_name = Column(Text)
    script_type = Column(Text)
    date_earliest = Column(Integer)
    date_latest = Column(Integer)
    period_label = Column(Text)
    findspot = Column(Text)
    current_location = Column(Text)
    text_type = Column(Text)
    completeness = Column(Text)
    shelfmarks = Column(ARRAY(Text))
    extra_metadata = Column("metadata", JSONB)
    source_corpus = Column(ARRAY(Text))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "script_type IN ('hieroglyphic','hieratic','demotic','coptic','greek','multiple')",
            name="ck_texts_script_type",
        ),
        CheckConstraint(
            "completeness IN ('complete','fragmentary','damaged','unknown','metadata_only')",
            name="ck_texts_completeness",
        ),
        Index("idx_texts_script", "script_type"),
        Index("idx_texts_period", "period_label"),
        Index("idx_texts_type", "text_type"),
    )


class Sentence(Base):
    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_id = Column(Text, ForeignKey("texts.canonical_id"), nullable=False)
    sequence_num = Column(Integer)
    transliteration = Column(Text)
    translation = Column(JSONB)
    tokens = Column(JSONB)
    source = Column(Text)
    source_id = Column(Text)
    source_detail = Column(JSONB)
    confidence = Column(Text, server_default="verified")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_sentences_canonical", "canonical_id"),
        Index("idx_sentences_source", "source"),
        Index("idx_sentences_confidence", "confidence"),
        Index("idx_sentences_tokens", "tokens", postgresql_using="gin"),
    )


class Concordance(Base):
    __tablename__ = "concordance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_id = Column(Text, ForeignKey("texts.canonical_id"), nullable=False)
    external_system = Column(Text, nullable=False)
    external_id = Column(Text, nullable=False)
    relationship = Column(Text, server_default="exact_match")

    __table_args__ = (
        UniqueConstraint("external_system", "external_id", "canonical_id", name="uq_concordance_system_ext_canonical"),
        Index("idx_concordance_canonical", "canonical_id"),
        Index("idx_concordance_external", "external_system", "external_id"),
    )


class Alias(Base):
    __tablename__ = "aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_id = Column(Text, ForeignKey("texts.canonical_id"), nullable=False)
    alias_text = Column(Text, nullable=False)
    alias_normalized = Column(Text, nullable=False)
    alias_type = Column(Text, nullable=False)
    confidence = Column(Text, server_default="auto")

    __table_args__ = (
        UniqueConstraint("alias_text", "canonical_id", name="uq_aliases_text_canonical"),
        Index("idx_aliases_normalized", "alias_normalized"),
        Index("idx_aliases_canonical", "canonical_id"),
    )


class RepresentationLayer(Base):
    __tablename__ = "representation_layers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_id = Column(Text, ForeignKey("texts.canonical_id"), nullable=False)
    layer_type = Column(Text, nullable=False)
    content = Column(JSONB)
    language = Column(Text)
    source = Column(Text)
    source_detail = Column(JSONB)
    confidence = Column(Text, server_default="verified")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_layers_canonical", "canonical_id"),
        Index("idx_layers_type", "layer_type"),
        Index("idx_layers_language", "language"),
    )


class Lemma(Base):
    __tablename__ = "lemmata"

    id = Column(Text, primary_key=True)
    form = Column(Text, nullable=False)
    translation = Column(JSONB)
    pos = Column(Text)
    language = Column(Text)
    source = Column(Text)
    frequency_rank = Column(Integer)
    extra = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_lemmata_form", "form"),
        Index("idx_lemmata_pos", "pos"),
        Index("idx_lemmata_source", "source"),
        Index("idx_lemmata_language", "language"),
    )


class ThothLexicon(Base):
    __tablename__ = "thoth_lexicon"

    lemma_id = Column(Text, ForeignKey("lemmata.id"), primary_key=True)
    definition_de = Column(Text)
    definition_en = Column(Text)
    glosses_de = Column(JSONB)
    glosses_en = Column(JSONB)
    glosses_bridged_en = Column(JSONB)
    coptic_cognates = Column(JSONB)
    hieroglyphs = Column(JSONB)
    pos = Column(Text)
    pos_distribution = Column(JSONB)
    frequency = Column(Integer)
    frequency_rank = Column(Integer)
    period_range = Column(JSONB)
    text_types = Column(JSONB)
    examples = Column(JSONB)
    sources = Column(JSONB)
    confidence = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_thoth_frequency", "frequency", postgresql_ops={"frequency": "DESC"}),
        Index("idx_thoth_pos", "pos"),
        Index("idx_thoth_glosses_en", "glosses_en", postgresql_using="gin"),
        Index("idx_thoth_confidence", "confidence"),
    )


class RosettaLemmaIndex(Base):
    __tablename__ = "rosetta_lemma_index"

    lemma_id = Column(Text, nullable=False)
    sentence_id = Column(Integer, ForeignKey("sentences.id"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("lemma_id", "sentence_id"),
        Index("idx_rosetta_lemma_sent", "sentence_id"),
    )
