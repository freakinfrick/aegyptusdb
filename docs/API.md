# Aegyptus API Reference

The API runs on port 8000 via FastAPI. All data endpoints are under `/api/v1/`.

**Start the server:**
```bash
PYTHONPATH=. python3 -m api
```

**Auto-generated docs:** Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs), ReDoc at [http://localhost:8000/redoc](http://localhost:8000/redoc).

---

## Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info and version |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

```bash
curl http://localhost:8000/
# {"service":"aegyptus-api","version":"0.1.0","docs":"/docs"}
```

---

### Texts

#### GET /api/v1/texts

Search and filter text records with pagination.

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Full-text search on conventional_name (ILIKE) |
| `script_type` | string | Exact match: hieroglyphic, hieratic, demotic, coptic, greek, multiple |
| `text_type` | string | Exact match on text_type |
| `period` | string | Substring match on period_label |
| `date_from` | int | Filter: date_earliest >= value |
| `date_to` | int | Filter: date_earliest <= value |
| `completeness` | string | Exact match: complete, fragmentary, damaged, unknown |
| `findspot` | string | Substring match on findspot |
| `source` | string | canonical_id prefix match (e.g., `aeg_oraec`) |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (1-100, default: 20) |
| `sort_by` | string | Sort field: canonical_id, conventional_name, date_earliest |
| `order` | string | asc or desc (default: asc) |

```bash
# Search for stele texts
curl "http://localhost:8000/api/v1/texts?q=Stele&page_size=5"

# Filter by script type and date range
curl "http://localhost:8000/api/v1/texts?script_type=hieroglyphic&date_from=-2000&date_to=-1500"

# Get all ORAEC texts, sorted by date
curl "http://localhost:8000/api/v1/texts?source=aeg_oraec&sort_by=date_earliest&order=asc"
```

**Response:**
```json
{
  "total": 396,
  "page": 1,
  "page_size": 5,
  "pages": 80,
  "items": [
    {
      "canonical_id": "aeg_oraec_100",
      "conventional_name": "Stele of Sehetep-ib-Re",
      "script_type": "hieroglyphic",
      "date_earliest": -1900,
      "date_latest": -1800,
      "period_label": "Middle Kingdom",
      "findspot": null,
      "text_type": "Royal Decree",
      "completeness": "complete",
      "shelfmarks": [],
      "metadata": {},
      "created_at": "2026-04-01T...",
      "updated_at": "2026-04-01T..."
    }
  ]
}
```

#### GET /api/v1/texts/{canonical_id}

Single text with all related data (layers, sentences, concordance, aliases).

```bash
curl http://localhost:8000/api/v1/texts/aeg_oraec_1
```

Returns 404 if not found.

---

### Sentences

#### GET /api/v1/sentences

Search and filter sentences.

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Transliteration substring search (ILIKE) |
| `lemma_id` | string | JSONB containment search on tokens array |
| `language` | string | Filter by translation language key |
| `source` | string | Exact match on source |
| `confidence` | string | Exact match on confidence |
| `canonical_id` | string | Filter by parent text |
| `page` | int | Page number |
| `page_size` | int | 1-100 |

```bash
# Search for sentences containing "nswt"
curl "http://localhost:8000/api/v1/sentences?q=nswt&page_size=5"

# Filter by source
curl "http://localhost:8000/api/v1/sentences?source=tla_hf"

# Get sentences for a specific text
curl "http://localhost:8000/api/v1/sentences?canonical_id=aeg_oraec_1"
```

#### GET /api/v1/sentences/{id}

Single sentence with parent text info.

```bash
curl http://localhost:8000/api/v1/sentences/1
```

---

### Concordance, Aliases, Layers

#### GET /api/v1/concordance/{canonical_id}

All external ID links for a text.

```bash
curl http://localhost:8000/api/v1/concordance/aeg_oraec_1
# [{"id":1,"canonical_id":"aeg_oraec_1","external_system":"oraec","external_id":"oraec1","relationship":"exact_match"},...]
```

#### GET /api/v1/aliases/{canonical_id}

All aliases (conventional names, shelfmarks) for a text.

```bash
curl http://localhost:8000/api/v1/aliases/aeg_oraec_1
```

#### GET /api/v1/layers/{canonical_id}

All representation layers for a text.

```bash
curl http://localhost:8000/api/v1/layers/aeg_oraec_1
```

---

### Statistics

#### GET /api/v1/stats

Corpus-wide statistics: table counts, texts by source, sentences by source, layer coverage.

```bash
curl http://localhost:8000/api/v1/stats
```

**Response:**
```json
{
  "texts": 62118,
  "sentences": 304617,
  "layers": 58828,
  "concordance": 213766,
  "aliases": 35410,
  "gaps": 844,
  "texts_by_source": [{"source":"tla","count":29762}, ...],
  "sentences_by_source": [{"source":"aes","count":101796}, ...],
  "layer_coverage": [{"layer_type":"transliteration","texts_covered":12345,"total_layers":15000}, ...]
}
```

---

### Export

Streaming bulk export with optional filters. Large exports use batched DB reads.

#### GET /api/v1/export/texts

| Parameter | Type | Description |
|-----------|------|-------------|
| `format` | string | `json` (default), `csv`, or `tei` |
| `script_type` | string | Filter |
| `source` | string | canonical_id prefix filter |
| `text_type` | string | Filter |
| `period` | string | Filter |

```bash
# Export Nederhof texts as JSON
curl "http://localhost:8000/api/v1/export/texts?format=json&source=aeg_nederhof" -o nederhof.json

# Export as CSV
curl "http://localhost:8000/api/v1/export/texts?format=csv&source=aeg_nederhof" -o nederhof.csv

# Export as TEI-XML
curl "http://localhost:8000/api/v1/export/texts?format=tei&source=aeg_nederhof" -o nederhof.tei.xml
```

#### GET /api/v1/export/sentences

| Parameter | Type | Description |
|-----------|------|-------------|
| `format` | string | `json` (default) or `csv` |
| `source` | string | Filter |
| `canonical_id` | string | Filter |
| `confidence` | string | Filter |

```bash
curl "http://localhost:8000/api/v1/export/sentences?format=csv&source=tla_hf" -o tla_sentences.csv
```

#### GET /api/v1/export/concordance

| Parameter | Type | Description |
|-----------|------|-------------|
| `format` | string | `json` (default) or `csv` |
| `external_system` | string | Filter |
| `canonical_id` | string | Filter |

```bash
curl "http://localhost:8000/api/v1/export/concordance?format=json&external_system=TM" -o tm_concordance.json
```

---

### Cross-Reference Resolution

Resolve any external ID or shelfmark to canonical record(s).

#### GET /api/v1/resolve/{system}/{ext_id}

| System | Searches |
|--------|----------|
| `tla` | tla, tla_hf, tla_entity_* concordance entries |
| `trismegistos` | trismegistos, TM |
| `aes` | aes, aes_sentence |
| `oraec` | oraec |
| `ramses` | ramses |
| `wikidata` | wikidata |
| `karnak` | karnak |
| `papyri_info` | papyri_info |
| `nederhof` | nederhof |

```bash
# Resolve an ORAEC ID
curl http://localhost:8000/api/v1/resolve/oraec/oraec1

# Resolve a Trismegistos ID
curl http://localhost:8000/api/v1/resolve/trismegistos/1000069

# Resolve a Wikidata entity
curl http://localhost:8000/api/v1/resolve/wikidata/Q100
```

**Response:**
```json
{
  "query_system": "oraec",
  "query_id": "oraec1",
  "matches": [
    {
      "canonical_id": "aeg_oraec_1",
      "conventional_name": "...",
      "script_type": "hieroglyphic",
      "period_label": "...",
      "concordance": [...],
      "layers_summary": [{"layer_type": "transliteration", "count": 1}, ...]
    }
  ]
}
```

#### GET /api/v1/resolve/shelfmark/{shelfmark}

Shelfmark lookup (normalized, substring-matched against aliases and texts.shelfmarks).

```bash
# Resolve a shelfmark
curl "http://localhost:8000/api/v1/resolve/shelfmark/JE%2048862"
```

Returns 404 if no matches found.
