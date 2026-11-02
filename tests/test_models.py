"""Integration tests for core SQLAlchemy models.

Verifies model instantiation, FK/CHECK/UNIQUE constraints against the
live database.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.models import (
    Alias,
    Concordance,
    CorpusVersion,
    CrawlQueue,
    Gap,
    RepresentationLayer,
    Sentence,
    TextRecord,
)


class TestModelInstantiation:
    """All 8 models can be instantiated and basic queries work."""

    def test_text_record_query(self, db: Session):
        row = db.execute(text("SELECT canonical_id FROM texts LIMIT 1")).fetchone()
        assert row is not None
        rec = db.query(TextRecord).filter_by(canonical_id=row[0]).first()
        assert rec is not None
        assert rec.canonical_id == row[0]

    def test_sentence_query(self, db: Session):
        rec = db.query(Sentence).first()
        assert rec is not None
        assert rec.id is not None
        assert rec.canonical_id is not None

    def test_concordance_query(self, db: Session):
        rec = db.query(Concordance).first()
        assert rec is not None
        assert rec.external_system is not None
        assert rec.external_id is not None

    def test_alias_query(self, db: Session):
        rec = db.query(Alias).first()
        assert rec is not None
        assert rec.alias_text is not None

    def test_representation_layer_query(self, db: Session):
        rec = db.query(RepresentationLayer).first()
        assert rec is not None
        assert rec.layer_type is not None

    def test_gap_query(self, db: Session):
        rec = db.query(Gap).first()
        assert rec is not None
        assert rec.gap_type is not None

    def test_crawl_queue_query(self, db: Session):
        rec = db.query(CrawlQueue).first()
        assert rec is not None
        assert rec.url is not None

    def test_corpus_version_query(self, db: Session):
        rec = db.query(CorpusVersion).first()
        assert rec is not None
        assert rec.version_tag is not None


class TestForeignKeyConstraints:
    """FK constraints: sentence must reference a valid text."""

    def test_sentence_fk_rejects_invalid_text(self, db: Session):
        bad = Sentence(
            canonical_id="nonexistent_text_id_xyzzy_999",
            transliteration="test",
            source="test",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_concordance_fk_rejects_invalid_text(self, db: Session):
        bad = Concordance(
            canonical_id="nonexistent_text_id_xyzzy_999",
            external_system="test",
            external_id="test",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_alias_fk_rejects_invalid_text(self, db: Session):
        bad = Alias(
            canonical_id="nonexistent_text_id_xyzzy_999",
            alias_text="test",
            alias_normalized="test",
            alias_type="conventional_name",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_layer_fk_rejects_invalid_text(self, db: Session):
        bad = RepresentationLayer(
            canonical_id="nonexistent_text_id_xyzzy_999",
            layer_type="transliteration",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


class TestCheckConstraints:
    """CHECK constraints enforce valid enum values."""

    def test_script_type_rejects_invalid(self, db: Session):
        """Invalid script_type should be rejected by CHECK constraint."""
        bad = TextRecord(
            canonical_id="aeg_test_ck_script_invalid",
            script_type="cuneiform",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_completeness_rejects_invalid(self, db: Session):
        """Invalid completeness should be rejected by CHECK constraint."""
        bad = TextRecord(
            canonical_id="aeg_test_ck_completeness_invalid",
            completeness="perfect",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_valid_script_types_accepted(self, db: Session):
        """All valid script_type values exist in the database."""
        valid_types = {"hieroglyphic", "hieratic", "demotic", "coptic", "greek", "multiple"}
        rows = db.execute(
            text("SELECT DISTINCT script_type FROM texts WHERE script_type IS NOT NULL")
        ).fetchall()
        existing = {r[0] for r in rows}
        # At least some valid types should be present
        assert existing.issubset(valid_types), f"Unexpected script types: {existing - valid_types}"
        assert len(existing) >= 2, f"Expected at least 2 script types, got {existing}"


class TestUniqueConstraints:
    """UNIQUE constraints prevent duplicates."""

    def test_concordance_unique_rejects_duplicate(self, db: Session):
        """Duplicate (external_system, external_id, canonical_id) should be rejected."""
        row = db.execute(
            text("SELECT canonical_id, external_system, external_id FROM concordance LIMIT 1")
        ).fetchone()
        assert row is not None
        dup = Concordance(
            canonical_id=row[0],
            external_system=row[1],
            external_id=row[2],
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_alias_unique_rejects_duplicate(self, db: Session):
        """Duplicate (alias_text, canonical_id) should be rejected."""
        row = db.execute(
            text("SELECT canonical_id, alias_text FROM aliases LIMIT 1")
        ).fetchone()
        assert row is not None
        dup = Alias(
            canonical_id=row[0],
            alias_text=row[1],
            alias_normalized="test",
            alias_type="conventional_name",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_text_primary_key_rejects_duplicate(self, db: Session):
        """Duplicate canonical_id should be rejected."""
        row = db.execute(text("SELECT canonical_id FROM texts LIMIT 1")).fetchone()
        assert row is not None
        dup = TextRecord(canonical_id=row[0])
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
