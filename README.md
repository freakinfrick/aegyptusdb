# Project Aegyptus

An open corpus of ancient Egyptian texts. Aegyptus aggregates data from scattered digital sources into a single queryable PostgreSQL store with a shared identity graph. Every known text can be found with whatever representation layers exist for it: hieroglyphic transcription, transliteration, lemmatization, and translations in multiple languages.

The corpus is multilayer by design. A 19th-century English translation sits alongside a modern TLA German translation and a lemmatized hieroglyphic transcription of the same physical text. All layers carry provenance, attribution, and confidence metadata.

> **Official channels.** Aegyptus lives at [aegyptuslab.cc](https://aegyptuslab.cc), [github.com/freakinfrick/aegyptusdb](https://github.com/freakinfrick/aegyptusdb), [github.com/freakinfrick/aegyptusstacks](https://github.com/freakinfrick/aegyptusstacks) and [@FreakinFrick](https://x.com/FreakinFrick) on X. There are no others.
>
> **Aegyptus has no token, coin or contract address.** Any account selling one under this name is not this project.

## Current Scale

Snapshot from April 2026; `python3 cli.py status --pretty` gives live counts for your own build.

| Table | Count |
|-------|-------|
| Text records | 77,683 |
| Sentences | 460,333 |
| Concordance links | 268,419 |
| Representation layers | 62,324 |
| Aliases | 48,537 |
| Lemmata | 35,052 |

**Script types:** hieroglyphic 20,871 · demotic 18,299 · coptic 12,644 · hieratic 9,441 · greek 1

**Languages represented:** Middle Egyptian, Late Egyptian, Demotic, Coptic, Greek

**External systems cross-linked:** TLA, ORAEC, Trismegistos, British Museum, DDbDP, HGV, DCLP, Wikidata, Louvre, Penn Museum, Karnak, RAMSES, and 20+ more via Trismegistos TexRelations

## Sources & Attribution

Aegyptus would not exist without the foundational work of these projects. All corpus data is attributed, licensed, and traceable to its origin.

---

### ORAEC — Open Richly Annotated Cuneiform Corpus Egyptian
**URL:** https://github.com/oraec/corpus_raw_data
**Maintainers:** ORAEC Project
**License:** CC BY-SA 4.0
**Contribution:** 13,026 text records · 101,796 sentences · transliteration, hieroglyphic, translation, lemmatization layers · concordance links to TLA, Trismegistos, Wikidata, Karnak

The structural backbone of the corpus. ORAEC provides the canonical TLA base32 IDs that connect most other importers. Import first.

---

### AES — Ancient Egyptian Sentences
**URL:** https://github.com/simondschweitzer/aes
**Creator:** Simon D. Schweitzer
**License:** CC BY-SA 4.0
**Contribution:** 101,796 sentences · German and English translations · word-level token data

Sentence-level companion to ORAEC. Shares TLA base32 IDs — AES sentences are linked to their parent ORAEC text records via concordance. Import after ORAEC.

---

### AED-TEI — Ancient Egyptian Dictionary (TEI XML Corpus)
**URL:** https://github.com/simondschweitzer/aed-tei
**Creator:** Simon D. Schweitzer, BBAW Strukturen und Transformationen project (January 2018 snapshot)
**License:** CC BY-SA 4.0
**Contribution:** 13,748 text records · 98,265 sentences (German translations) · 2,802 hieroglyphic representation layers · 11,210 aliases · word-level lemma cross-references

TEI XML corpus from the same Berlin project as ORAEC/AES. Contains a January 2018 snapshot with hieroglyphic encodings not present in the ORAEC GitHub dump. Also contains `dictionary.xml` — the source for the lemmata table.

---

### AED Dictionary (`dictionary.xml`)
**URL:** https://github.com/simondschweitzer/aed-tei (embedded in AED-TEI repo)
**Creator:** Simon D. Schweitzer, BBAW
**License:** CC BY-SA 4.0
**Contribution:** 35,052 lemma entries · German + English translations · part of speech · bibliography · root cross-references

The first lexical dimension of the corpus. Enables vocabulary queries, frequency analysis, and hapax legomena detection across all sources.

---

### TLA — Thesaurus Linguae Aegyptiae (Hugging Face datasets)
**URL:** https://huggingface.co/thesaurus-linguae-aegyptiae
**Maintainers:** Thesaurus Linguae Aegyptiae Project, Berlin-Brandenburg Academy of Sciences
**License:** CC BY-SA 4.0
**Contribution:** 29,762 text records · 29,762 sentences · Earlier Egyptian, Late Egyptian, and Demotic coverage · metadata for dates, object types, locations, and origin places

---

### Coptic Scriptorium
**URL:** https://copticscriptorium.org · https://github.com/CopticScriptorium/corpora
**Maintainers:** Caroline T. Schroeder, Amir Zeldes, and contributors
**License:** CC BY 4.0 (most corpora)
**Contribution:** 1,467 text records · 51,474 sentences · Coptic text + English translations · token-level annotation (lemma, POS, morphological features, language-of-origin)

Transforms Coptic from "catalogued" to "linguistically queryable" in the corpus. Includes Nag Hammadi texts, the Sahidic Bible, Shenoute of Atripe (extensive), Apophthegmata Patrum, Gospel of Thomas, and 70+ other corpora.

---

### Nederhof PhilologEg — St Andrews Corpus
**URL:** https://mjn.host.cs.st-andrews.ac.uk/egyptian/
**Creator:** Mark-Jan Nederhof, University of St Andrews
**License:** Academic use; contact author for redistribution
**Contribution:** 94 text records · 5,934 sentences · 53 hieroglyphic representation layers · English translations for every sentence · RES→Unicode sign mapping (1,071 entries)

PhilologEg is the direct scholarly predecessor of Aegyptus: the same goal (one place, all Egyptian texts, machine-readable), built as a desktop Java application over roughly two decades of manual work. Nederhof solved the hieroglyph encoding problem first — his sign-to-Unicode mapping (`signunicode.xml`) is used verbatim in Aegyptus. The corpus covers canonical Middle Kingdom literary texts: Shipwrecked Sailor, Westcar Papyrus, Instruction of Ptahhotep, Ebers Papyrus, Merneptah Stela, Autobiography of Ahmose son of Abana, Hatshepsut Punt expedition, Tuthmosis III Gebel Barkal stela, and 45 Urkunden IV texts.

**Note:** Aegyptus imports PhilologEg's corpus as one source layer, not a replacement. Where Aegyptus provides scale and infrastructure, PhilologEg provides deep scholarly edition features (alignment, variant manuscripts, visual hieroglyph rendering). They are complementary.

---

### Nederhof HieroJax
**URL:** https://nederhof.github.io/hierojax/
**Creator:** Mark-Jan Nederhof, University of St Andrews
**License:** GPL-3.0 (tooling); texts public domain
**Contribution:** 120 text records · Unicode hieroglyphic representation layers

Earlier Nederhof corpus — HTML-based hieroglyph viewer. Urkunden IV texts and related inscriptions.

---

### RAMSES — Ramsès Late Egyptian Corpus
**URL:** https://ramses.ulg.ac.be · Zenodo DOI: 10.5281/zenodo.4954597
**Maintainers:** Université de Liège
**License:** CC BY-NC-SA (**non-commercial restriction**)
**Contribution:** 71,263 sentences · Late Egyptian transliteration · ~4,200 texts

⚠️ RAMSES data carries a non-commercial restriction. This is recorded in sentence metadata (`source = 'ramses'`). Any downstream use must respect CC BY-NC-SA terms.

---

### papyri.info / DCLP / IDP
**URL:** https://papyri.info · https://github.com/papyri/idp.data
**Maintainers:** Papyri.info Consortium
**License:** CC BY 3.0
**Contribution:** ~19,207 text records (primarily Greek; Coptic, Demotic, and Egyptian-language filtering applied) · EpiDoc XML transcriptions · Trismegistos concordance links

Includes 17 Nag Hammadi codices (TM 107741–107753 and related) and Hermetic DCLP fragments — force-included by TM ID to bypass the Greek-centric language filter.

---

### Trismegistos TexRelations
**URL:** https://www.trismegistos.org/dataservices/
**Maintainers:** Trismegistos Project, KU Leuven
**License:** CC BY-SA 3.0
**Contribution:** ~27,000+ new concordance links across 30+ external systems (British Museum 10,339 · DDbDP 4,630 · HGV 3,566 · DCLP 2,376 · ONB 838 · MertensPack 544 · TBP 518 · Louvre 444 · and more)

Not a text source — a concordance enricher. Queries the TexRelations Matcher API for every existing TM ID in the corpus and harvests cross-references to partner projects. Dramatically expands the identity graph.

---

### Metropolitan Museum of Art
**URL:** https://collectionapi.metmuseum.org/public/collection/v1/
**License:** CC0 (public domain)
**Contribution:** 248 text records (metadata_only) · accession number aliases · department 10 (Egyptian Art) objects

Partial import — Met API rate-limits aggressively. Future: use the [CSV bulk download](https://github.com/metmuseum/openaccess) for full 27,971 object coverage.

---

### Manual Ingests
**License:** Public domain (Breasted 1901, Scott 1924)
**Contribution:** 2 texts · 39 sentences · Greco-Egyptian bridge material

- **Shabaka Stone / Denkmal memphitischer Theologie (BM EA 498):** Basalt slab of Pharaoh Shabaka (25th Dynasty, c. 710 BCE). Contains the Memphite Theology — Ptah creates the world through heart and tongue. The most direct Egyptian ancestor of the Greek Logos doctrine. Sentences from Breasted (1901, public domain).

- **Corpus Hermeticum I: Poimandres:** Greek treatise (~2nd century CE, composed in Egypt). Hermes Trismegistus receives cosmogonic revelation. First Greek-language text in the corpus. Sentences from Scott (1924, public domain). Tagged `bridge_text: true`.

Both texts are absent from all other digital sources and were ingested to support the article *The Logos Before the Greeks* (`Articles/the-logos-before-the-greeks.md`).

---

## Quickstart

```bash
# 1. Start PostgreSQL (port 5434) and MinIO
docker compose --profile dev up -d

# 2. Run migrations
alembic upgrade head

# 3. Run importers (order matters: ORAEC before AES)
aegyptus import --source oraec
aegyptus import --source aes
aegyptus import --source tla-hf
aegyptus import --source nederhof
aegyptus import --source ramses
aegyptus import --source papyri-info
aegyptus import --source aed-dict
aegyptus import --source aed-tei
aegyptus import --source coptic-scriptorium
aegyptus import --source nederhof-philologeg
aegyptus import --source trismegistos   # concordance enrichment, run last

# 4. Check status
aegyptus import --status

# 5. Start the API (port 8000)
python -m api

# 6. Manual ingest
python scripts/ingest_manual.py data/manual/my_text.json
```

## Architecture

```
                  +------------------+
                  |   Gap Tracker    |
                  |  (prioritizes)   |
                  +--------+---------+
                           |
          +----------------+----------------+
          |                |                |
  +-------v------+  +-----v------+  +------v-------+
  | Web Crawler  |  | Structured |  | ML Pipeline  |
  | PDF/HTML     |  | Connectors |  | OCR/LM/Draft |
  +-------+------+  +-----+------+  +------+-------+
          |                |                |
          +-------+--------+--------+-------+
                  |                  |
          +-------v-------+  +------v-------+
          |   Entity      |  |  Ad-Hoc      |
          |   Resolution  |  |  Ingestion   |
          +-------+-------+  +------+-------+
                  |                  |
                  +--------+---------+
                           |
                  +--------v---------+
                  |  Central Store   |
                  |  PostgreSQL 16   |
                  |  (port 5434)     |
                  +--------+---------+
                           |
              +------------+------------+
              |                         |
     +--------v---------+     +--------v---------+
     |   Query API      |     |   Dashboard      |
     |   FastAPI :8000  |     |   Flask :8080    |
     +------------------+     +------------------+
```

## Key Commands

| Command | Description |
|---------|-------------|
| `aegyptus import --source <name>` | Run a single importer |
| `aegyptus import --source all` | Run all importers in order |
| `aegyptus import --status` | Corpus size per source |
| `python -m api` | Start FastAPI server (port 8000, Swagger at /docs) |
| `python -m dashboard` | Start dashboard (port 8080) |
| `python scripts/ingest_manual.py <file>` | Manual JSON ingest |
| `python scripts/export_corpus.py` | Export corpus to JSONL |
| `python scripts/import_corpus.py ./export/` | Reconstruct DB from export |
| `./scripts/backup.sh` | pg_dump backup (compressed, date-stamped) |
| `pytest tests/ -v` | Run integration tests |

## Database

PostgreSQL 16 on port 5434 (via Docker Compose).

**Connection:** `postgresql://aegyptus:dev@localhost:5434/aegyptus`

### Tables

| Table | Description |
|-------|-------------|
| `texts` | Canonical text records (PK: `canonical_id`) |
| `sentences` | Sentence-level data with transliteration, translation, tokens |
| `concordance` | Cross-reference links to TLA, ORAEC, Trismegistos, British Museum, etc. |
| `aliases` | Conventional name and shelfmark variants |
| `representation_layers` | Multi-layer content (transliteration, translation, hieroglyphic, etc.) |
| `lemmata` | Egyptian lexicon (35,052 entries from AED, with POS and translations) |
| `gaps` | Missing text tracker for prioritized acquisition |
| `crawl_queue` | Web crawler URL queue |
| `corpus_versions` | Version snapshot metadata |

### Canonical ID Format

| Prefix | Source |
|--------|--------|
| `aeg_oraec_{n}` | ORAEC corpus |
| `aeg_aes_{id}` | AES sentences |
| `aeg_tla_hf_{id}` | TLA Hugging Face |
| `aeg_nederhof_{n}` | Nederhof HieroJax |
| `aeg_nederhof_philologeg_{slug}` | Nederhof PhilologEg St Andrews corpus |
| `aeg_aedtei_{tla_base32}` | AED-TEI corpus |
| `aeg_copcorp_{corpus}_{slug}` | Coptic Scriptorium |
| `aeg_papyri_{id}` | papyri.info / IDP |
| `aeg_ramses_{id}` | RAMSES Late Egyptian |
| `aeg_met_{objectID}` | Metropolitan Museum |
| `aeg_manual_{slug}` | Manual ingests |
| `aeg_adhoc_{hash}` | Ad-hoc ingested texts |
| `aeg_crawl_{hash}` | Web-crawled texts |

## Project Structure

```
Aegyptus/
  api/              FastAPI query API
  core/
    models/         SQLAlchemy models (texts, sentences, concordance,
                    aliases, representation_layers, lemmata, gaps, etc.)
    schemas.py      Pydantic serialization schemas
    concordance/    Normalizer, alias seeder, bootstrap
    resolution/     Entity resolution engine + merge pipeline
  crawler/          Web crawler (seeds, workers, parsers, rate limiter)
  dashboard/        Flask dashboard
  gap_tracker/      Missing text analyzer
  importers/        Structured data importers (11 sources)
    oraec/          ORAEC bulk importer
    aes/            AES sentence importer
    tla_hf/         TLA Hugging Face loader
    nederhof/       Nederhof HieroJax importer
    nederhof_philologeg/  PhilologEg St Andrews corpus (from JAR)
    ramses/         RAMSES Late Egyptian importer
    papyri_info/    papyri.info EpiDoc connector
    aed_dict/       AED lemma dictionary
    aed_tei/        AED-TEI XML corpus
    coptic_scriptorium/  Coptic Scriptorium CoNLL-U
    met_api/        Metropolitan Museum API
    trismegistos/   Trismegistos TexRelations enricher
  scripts/          Operational scripts
    ingest_manual.py  Manual JSON text ingest
    export_corpus.py  JSONL export
    import_corpus.py  DB restore from export
    bootstrap.sh      Full environment bootstrap
  data/
    upstream/       Cloned repos and downloaded datasets
    manual/         Hand-prepared JSON texts (Shabaka Stone, Poimandres, etc.)
  docs/             Spec, API docs, importer guide, import plan, handoffs
  Articles/         Scholarly articles drawing on the corpus
  schema/           Alembic migrations
  tests/            Integration test suite
  docker-compose.yml
  pyproject.toml
```

## The Labyrinth (browser game)

A spatial reading room on top of the corpus: hexagonal chambers, each one a concept in the Egyptians' own vocabulary, stacked by era and linked by shafts. The same concept in an older text sits directly below. Code: `api/hackathon.py`, `graph/`, `web/`.

```bash
python3 -m api --port 8001     # then open http://localhost:8001/web/
```

The Librarian (navigation and hints) and the Scribe (multi-text synthesis) call an OpenAI-compatible endpoint; set `NOUS_API_KEY` in `.env`. Without a key the chambers, passages and reader still work.

## License

The **software** is MIT licensed (see `LICENSE`).

The **corpus data** has mixed licensing reflecting its sources:

| Source | License | Commercial use |
|--------|---------|----------------|
| ORAEC | CC BY-SA 4.0 | ✅ (ShareAlike) |
| AES | CC BY-SA 4.0 | ✅ (ShareAlike) |
| AED-TEI / AED dict | CC BY-SA 4.0 | ✅ (ShareAlike) |
| TLA Hugging Face | CC BY-SA 4.0 | ✅ (ShareAlike) |
| Coptic Scriptorium | CC BY 4.0 (most) | ✅ |
| Nederhof PhilologEg | Academic use | ⚠️ Contact author |
| Nederhof HieroJax | GPL-3.0 (tooling) | ⚠️ |
| RAMSES | CC BY-NC-SA | ❌ Non-commercial |
| papyri.info / DCLP | CC BY 3.0 | ✅ |
| Trismegistos | CC BY-SA 3.0 | ✅ (ShareAlike) |
| Metropolitan Museum | CC0 | ✅ |
| Manual ingests | Public domain | ✅ |

All corpus data carries `source`, `source_corpus`, and `confidence` metadata fields for full provenance tracking.

## Documentation

- [Importers Guide](docs/IMPORTERS.md) — all data sources, how to run each importer, expected output
- [API Reference](docs/API.md) — all endpoints with examples
- [Full Spec](docs/aegyptus_orchestration_v2.1.md) — complete project specification
- [Swagger UI](http://localhost:8000/docs) — interactive API docs (when server is running)
