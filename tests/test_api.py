"""Integration tests for the FastAPI query API.

Tests key endpoints with httpx TestClient against the live database.
"""

import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "aegyptus-api"


class TestTextSearch:
    def test_list_texts_default(self):
        r = client.get("/api/v1/texts")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 60000
        assert data["page"] == 1
        assert len(data["items"]) == 20  # default page_size

    def test_search_by_name(self):
        r = client.get("/api/v1/texts", params={"q": "Stele"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 100

    def test_filter_by_script_type(self):
        r = client.get("/api/v1/texts", params={"script_type": "hieroglyphic"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1000

    def test_filter_by_date_range(self):
        r = client.get("/api/v1/texts", params={"date_from": -3000, "date_to": -2000})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    def test_filter_by_source_prefix(self):
        r = client.get("/api/v1/texts", params={"source": "aeg_oraec"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 13000

    def test_pagination(self):
        r1 = client.get("/api/v1/texts", params={"page": 1, "page_size": 5})
        r2 = client.get("/api/v1/texts", params={"page": 2, "page_size": 5})
        assert r1.status_code == 200
        assert r2.status_code == 200
        items1 = r1.json()["items"]
        items2 = r2.json()["items"]
        assert len(items1) == 5
        assert len(items2) == 5
        ids1 = {i["canonical_id"] for i in items1}
        ids2 = {i["canonical_id"] for i in items2}
        assert ids1.isdisjoint(ids2), "Pages should not overlap"

    def test_sort_by_date(self):
        r = client.get("/api/v1/texts", params={
            "sort_by": "date_earliest", "order": "desc", "page_size": 5
        })
        assert r.status_code == 200
        items = r.json()["items"]
        dates = [i["date_earliest"] for i in items if i["date_earliest"] is not None]
        assert dates == sorted(dates, reverse=True)

    def test_invalid_page_size_rejected(self):
        r = client.get("/api/v1/texts", params={"page_size": 200})
        assert r.status_code == 422


class TestTextDetail:
    def test_single_text(self):
        r = client.get("/api/v1/texts/aeg_oraec_1")
        assert r.status_code == 200
        data = r.json()
        assert data["canonical_id"] == "aeg_oraec_1"
        assert "layers" in data
        assert "sentences" in data
        assert "concordance" in data
        assert "aliases" in data

    def test_text_has_layers(self):
        r = client.get("/api/v1/texts/aeg_oraec_1")
        data = r.json()
        assert len(data["layers"]) >= 1

    def test_text_has_sentences(self):
        r = client.get("/api/v1/texts/aeg_oraec_1")
        data = r.json()
        assert len(data["sentences"]) >= 1

    def test_404_for_missing_text(self):
        r = client.get("/api/v1/texts/nonexistent_text_id_xyzzy_999")
        assert r.status_code == 404


class TestSentenceSearch:
    def test_list_sentences(self):
        r = client.get("/api/v1/sentences")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 300000

    def test_search_by_transliteration(self):
        r = client.get("/api/v1/sentences", params={"q": "nswt"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1000

    def test_filter_by_source(self):
        r = client.get("/api/v1/sentences", params={"source": "tla_hf"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 29000

    def test_single_sentence(self):
        # Get a real sentence ID
        r = client.get("/api/v1/sentences", params={"page_size": 1})
        items = r.json()["items"]
        assert len(items) == 1
        sid = items[0]["id"]

        r2 = client.get(f"/api/v1/sentences/{sid}")
        assert r2.status_code == 200
        data = r2.json()
        assert data["id"] == sid
        assert "text_canonical_id" in data

    def test_404_for_missing_sentence(self):
        r = client.get("/api/v1/sentences/999999999")
        assert r.status_code == 404


class TestConcordanceEndpoints:
    def test_get_concordance(self):
        r = client.get("/api/v1/concordance/aeg_oraec_1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all("external_system" in c for c in data)

    def test_get_aliases(self):
        r = client.get("/api/v1/aliases/aeg_oraec_1")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_layers(self):
        r = client.get("/api/v1/layers/aeg_oraec_1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1

    def test_concordance_404_for_missing(self):
        r = client.get("/api/v1/concordance/nonexistent_xyzzy_999")
        assert r.status_code == 404


class TestStatsEndpoint:
    def test_corpus_stats(self):
        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["texts"] >= 60000
        assert data["sentences"] >= 300000
        assert data["layers"] >= 50000
        assert data["concordance"] >= 200000
        assert data["aliases"] >= 30000
        assert data["gaps"] >= 800
        assert len(data["texts_by_source"]) >= 3
        assert len(data["sentences_by_source"]) >= 3
        assert len(data["layer_coverage"]) >= 1


class TestExportJSON:
    def test_export_texts_json(self):
        r = client.get("/api/v1/export/texts", params={"format": "json", "source": "aeg_nederhof"})
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]
        data = json.loads(r.text)
        assert isinstance(data, list)
        assert len(data) >= 100

    def test_export_sentences_json(self):
        r = client.get("/api/v1/export/sentences", params={
            "format": "json", "canonical_id": "aeg_oraec_1"
        })
        assert r.status_code == 200
        data = json.loads(r.text)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_export_concordance_json(self):
        r = client.get("/api/v1/export/concordance", params={
            "format": "json", "canonical_id": "aeg_oraec_1"
        })
        assert r.status_code == 200
        data = json.loads(r.text)
        assert isinstance(data, list)


class TestExportCSV:
    def test_export_texts_csv(self):
        r = client.get("/api/v1/export/texts", params={"format": "csv", "source": "aeg_nederhof"})
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        reader = csv.reader(io.StringIO(r.text))
        header = next(reader)
        assert "canonical_id" in header
        rows = list(reader)
        assert len(rows) >= 100

    def test_export_sentences_csv(self):
        r = client.get("/api/v1/export/sentences", params={
            "format": "csv", "canonical_id": "aeg_oraec_1"
        })
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]


class TestExportTEIXML:
    def test_export_tei_xml(self):
        r = client.get("/api/v1/export/texts", params={
            "format": "tei", "source": "aeg_nederhof"
        })
        assert r.status_code == 200
        assert "xml" in r.headers["content-type"]

        # Parse and validate structure
        root = ET.fromstring(r.text)
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        assert root.tag == "{http://www.tei-c.org/ns/1.0}TEI"

        # Has teiHeader
        header = root.find("tei:teiHeader", ns)
        assert header is not None

        # Has body with div elements
        body = root.find("tei:text/tei:body", ns)
        assert body is not None
        divs = body.findall("tei:div", ns)
        assert len(divs) >= 100

    def test_tei_namespace_correct(self):
        r = client.get("/api/v1/export/texts", params={
            "format": "tei", "source": "aeg_nederhof"
        })
        assert "http://www.tei-c.org/ns/1.0" in r.text


class TestCrossReferenceResolution:
    def test_resolve_oraec(self):
        r = client.get("/api/v1/resolve/oraec/oraec1")
        assert r.status_code == 200
        data = r.json()
        assert data["query_system"] == "oraec"
        assert len(data["matches"]) >= 1
        assert data["matches"][0]["canonical_id"] == "aeg_oraec_1"

    def test_resolve_tla(self):
        """Resolve a TLA ID via the concordance table."""
        r = client.get("/api/v1/resolve/tla/66ATQAWY55BNBFZYHSRGQK5RG4")
        if r.status_code == 404:
            pytest.skip("TLA ID not in concordance")
        assert r.status_code == 200
        data = r.json()
        assert len(data["matches"]) >= 1

    def test_resolve_shelfmark(self):
        """Resolve a shelfmark via the alias table."""
        r = client.get("/api/v1/resolve/shelfmark/JE 48862")
        if r.status_code == 404:
            pytest.skip("Shelfmark not found")
        assert r.status_code == 200
        data = r.json()
        assert len(data["matches"]) >= 1

    def test_resolve_404_for_missing(self):
        r = client.get("/api/v1/resolve/oraec/nonexistent_999999")
        assert r.status_code == 404

    def test_resolve_shelfmark_404_for_missing(self):
        r = client.get("/api/v1/resolve/shelfmark/Nonexistent Museum ZZZZZ")
        assert r.status_code == 404

    def test_resolve_returns_concordance(self):
        """Resolved records include concordance links."""
        r = client.get("/api/v1/resolve/oraec/oraec1")
        data = r.json()
        match = data["matches"][0]
        assert "concordance" in match
        assert len(match["concordance"]) >= 1

    def test_resolve_returns_layer_summary(self):
        """Resolved records include layer summary."""
        r = client.get("/api/v1/resolve/oraec/oraec1")
        data = r.json()
        match = data["matches"][0]
        assert "layers_summary" in match
