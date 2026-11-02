"""Integration tests for the ad-hoc ingestion CLI.

Tests text, JSON, and CSV input, plus the alias CLI.
Uses temporary files to avoid polluting the test fixtures directory.
"""

import json
import os
import tempfile

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ingest.cli import (
    content_hash,
    detect_format,
    ingest_csv_file,
    ingest_json_file,
    ingest_text_file,
    parse_ids,
)


class TestHelpers:
    def test_content_hash_deterministic(self):
        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_varies(self):
        h1 = content_hash("hello world")
        h2 = content_hash("goodbye world")
        assert h1 != h2

    def test_detect_format_text(self):
        assert detect_format("file.txt") == "text"
        assert detect_format("file.md") == "text"

    def test_detect_format_json(self):
        assert detect_format("file.json") == "json"

    def test_detect_format_csv(self):
        assert detect_format("file.csv") == "csv"

    def test_parse_ids_valid(self):
        result = parse_ids("tla:ABC123,tm:12345")
        assert result == [("tla", "ABC123"), ("tm", "12345")]

    def test_parse_ids_empty(self):
        assert parse_ids("") == []
        assert parse_ids(None) == []

    def test_parse_ids_malformed(self):
        result = parse_ids("nocolon,tla:valid")
        assert len(result) == 1
        assert result[0] == ("tla", "valid")


class TestTextIngestion:
    def test_ingest_text_file(self, db: Session):
        """Ingest a plain text file and verify the record is created."""
        content = "jw=f sDm\nnswt-bjty\nTest ingestion line three"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmppath = f.name

        try:
            result = ingest_text_file(
                tmppath, name="Test Text Ingest", script_type="hieroglyphic",
                source="test_suite", ids=[]
            )
            assert result["status"] in ("created", "exists")
            assert result["canonical_id"].startswith("aeg_adhoc_")

            # Verify in DB
            cid = result["canonical_id"]
            row = db.execute(text(
                "SELECT canonical_id FROM texts WHERE canonical_id = :cid"
            ), {"cid": cid}).fetchone()
            assert row is not None
        finally:
            os.unlink(tmppath)

    def test_ingest_text_idempotent(self, db: Session):
        """Re-ingesting the same file should not create a duplicate."""
        content = "unique idempotency test content 42"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmppath = f.name

        try:
            r1 = ingest_text_file(tmppath, name=None, script_type=None, source=None, ids=[])
            r2 = ingest_text_file(tmppath, name=None, script_type=None, source=None, ids=[])
            assert r1["canonical_id"] == r2["canonical_id"]
            assert r2["status"] == "exists"
        finally:
            os.unlink(tmppath)


class TestJSONIngestion:
    def test_ingest_json_single(self, db: Session):
        record = {
            "name": "JSON Test Record",
            "text": "jw=f Hr sDm.t nswt-bjty nb tAwy",
            "script_type": "hieroglyphic",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(record, f)
            tmppath = f.name

        try:
            result = ingest_json_file(tmppath, name=None, script_type=None, source="test", ids=[])
            assert result["created"] + result["existed"] == 1
        finally:
            os.unlink(tmppath)

    def test_ingest_json_array(self, db: Session):
        records = [
            {"name": "JSON Array Test 1", "text": "content A for array test"},
            {"name": "JSON Array Test 2", "text": "content B for array test"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(records, f)
            tmppath = f.name

        try:
            result = ingest_json_file(tmppath, name=None, script_type=None, source="test", ids=[])
            assert result["created"] + result["existed"] == 2
        finally:
            os.unlink(tmppath)


class TestCSVIngestion:
    def test_ingest_csv(self, db: Session):
        csv_content = "name,text,script_type\nCSV Test Record,test csv content alpha,hieroglyphic\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            tmppath = f.name

        try:
            result = ingest_csv_file(tmppath, name=None, script_type=None, source="test", ids=[])
            assert result["created"] + result["existed"] == 1
        finally:
            os.unlink(tmppath)


class TestAliasOperations:
    def test_alias_module_imports(self):
        """Verify the alias CLI module is importable."""
        from ingest.alias import cmd_add, cmd_list, cmd_search  # noqa: F401
