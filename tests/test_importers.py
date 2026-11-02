"""Integration tests for importers.

Verifies each importer produced expected output in the live database.
Tests idempotency by checking counts and canonical_id format patterns.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


class TestORAECImporter:
    """ORAEC importer: 13,026 texts from corpus_raw_data."""

    def test_text_count(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_oraec_%'"
        )).scalar()
        assert count >= 13000, f"Expected >= 13,000 ORAEC texts, got {count}"

    def test_canonical_id_format(self, db: Session):
        """ORAEC canonical_ids follow aeg_oraec_{number} pattern."""
        row = db.execute(text(
            "SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_oraec_%' LIMIT 1"
        )).fetchone()
        assert row is not None
        assert row[0].startswith("aeg_oraec_")

    def test_sentences_created(self, db: Session):
        """ORAEC imports should have created sentence records."""
        count = db.execute(text(
            "SELECT count(*) FROM sentences WHERE source = 'oraec'"
        )).scalar()
        assert count >= 50000, f"Expected >= 50,000 ORAEC sentences, got {count}"

    def test_layers_created(self, db: Session):
        """ORAEC texts should have representation layers."""
        count = db.execute(text(
            "SELECT count(*) FROM representation_layers "
            "WHERE canonical_id LIKE 'aeg_oraec_%'"
        )).scalar()
        assert count >= 10000, f"Expected >= 10,000 ORAEC layers, got {count}"

    def test_concordance_links(self, db: Session):
        """ORAEC importer should create concordance links."""
        count = db.execute(text(
            "SELECT count(*) FROM concordance WHERE external_system = 'oraec'"
        )).scalar()
        assert count >= 10000, f"Expected >= 10,000 ORAEC concordance entries, got {count}"

    def test_idempotency_canonical_ids_unique(self, db: Session):
        """No duplicate canonical_ids (idempotency indicator)."""
        dups = db.execute(text(
            "SELECT canonical_id, count(*) FROM texts "
            "WHERE canonical_id LIKE 'aeg_oraec_%' "
            "GROUP BY canonical_id HAVING count(*) > 1"
        )).fetchall()
        assert len(dups) == 0, f"Found duplicate ORAEC canonical_ids: {dups[:5]}"


class TestAESImporter:
    """AES importer: 100k+ sentences from 14 subcorpus files."""

    def test_sentence_count(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM sentences WHERE source = 'aes'"
        )).scalar()
        assert count >= 90000, f"Expected >= 90,000 AES sentences, got {count}"

    def test_concordance_links(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM concordance WHERE external_system = 'aes_sentence'"
        )).scalar()
        assert count >= 90000, f"Expected >= 90,000 AES concordance entries, got {count}"


class TestTLAHFImporter:
    """TLA HF importer: ~29,762 sentences from 3 Hugging Face datasets."""

    def test_text_count(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_tla_%'"
        )).scalar()
        assert count >= 20000, f"Expected >= 20,000 TLA texts, got {count}"

    def test_sentence_count(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM sentences WHERE source = 'tla_hf'"
        )).scalar()
        assert count >= 29000, f"Expected >= 29,000 TLA HF sentences, got {count}"

    def test_canonical_id_format(self, db: Session):
        row = db.execute(text(
            "SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_tla_%' LIMIT 1"
        )).fetchone()
        assert row is not None
        assert row[0].startswith("aeg_tla_")

    def test_concordance_links(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM concordance WHERE external_system = 'tla_hf'"
        )).scalar()
        assert count >= 29000, f"Expected >= 29,000 TLA HF concordance entries, got {count}"


class TestNederhofImporter:
    """Nederhof importer: 118+ texts with Unicode hieroglyphs."""

    def test_text_count(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_nederhof_%'"
        )).scalar()
        assert count >= 100, f"Expected >= 100 Nederhof texts, got {count}"

    def test_concordance_links(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM concordance WHERE external_system = 'nederhof'"
        )).scalar()
        assert count >= 100, f"Expected >= 100 Nederhof concordance entries, got {count}"


class TestRAMSESImporter:
    """RAMSES importer: Late Egyptian transliteration data."""

    def test_sentences_imported(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM sentences WHERE source = 'ramses'"
        )).scalar()
        assert count >= 50000, f"Expected >= 50,000 RAMSES sentences, got {count}"

    def test_concordance_exists(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM concordance WHERE external_system = 'ramses'"
        )).scalar()
        assert count >= 1, f"Expected at least 1 RAMSES concordance entry, got {count}"


class TestPapyriInfoConnector:
    """papyri.info connector: EpiDoc XML from GitHub."""

    def test_texts_imported(self, db: Session):
        count = db.execute(text(
            "SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_papyri_%'"
        )).scalar()
        assert count >= 1000, f"Expected >= 1,000 papyri.info texts, got {count}"

    def test_concordance_links(self, db: Session):
        """papyri.info texts should have TM concordance links."""
        count = db.execute(text(
            "SELECT count(*) FROM concordance c "
            "JOIN texts t ON c.canonical_id = t.canonical_id "
            "WHERE t.canonical_id LIKE 'aeg_papyri_%' "
            "AND c.external_system IN ('TM', 'trismegistos')"
        )).scalar()
        assert count >= 100, f"Expected >= 100 papyri TM links, got {count}"


class TestIdempotency:
    """Cross-importer idempotency checks."""

    def test_no_duplicate_texts(self, db: Session):
        """No duplicate primary keys in texts table."""
        total = db.execute(text("SELECT count(*) FROM texts")).scalar()
        distinct = db.execute(text("SELECT count(DISTINCT canonical_id) FROM texts")).scalar()
        assert total == distinct

    def test_concordance_unique_constraint_holds(self, db: Session):
        """No violations of the (system, ext_id, canonical_id) unique constraint."""
        dups = db.execute(text(
            "SELECT external_system, external_id, canonical_id, count(*) "
            "FROM concordance GROUP BY external_system, external_id, canonical_id "
            "HAVING count(*) > 1"
        )).fetchall()
        assert len(dups) == 0, f"Concordance duplicates found: {dups[:5]}"
