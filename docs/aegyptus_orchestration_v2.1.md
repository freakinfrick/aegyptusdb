# PROJECT AEGYPTUS
## Open Corpus of Ancient Egyptian Texts

### ORCHESTRATION DOCUMENTATION
**Agent Build Guide -- Software Framework**
Layers 0--3: Schema, Identity, Web Pipeline, ML Processing

**Version 0.2.1 -- April 2026**

DEFERRED: TTS Library Outreach | Gated Database Pipeline | Physical Acquisition Campaign | Glyph Recognition Pipeline

---

## Changelog

### v0.2.1 (from v0.2)

- **Sentences table added.** New `sentences` table provides relational sentence-level storage with token data in JSONB. Bridges the AES (sentence-oriented) and ORAEC (document-oriented) data models.
- **Concordance UNIQUE constraint revised.** Changed from `UNIQUE (external_system, external_id)` to `UNIQUE (external_system, external_id, canonical_id)` to support one-external-ID-to-many-canonical-records mappings (e.g., TLA entry covering recto+verso split into separate canonical texts).
- **Deterministic ID generation strategy defined.** `canonical_id` format: `aeg_{source}_{source_id}` for source-imported records, `aeg_adhoc_{hash}` for manual imports. First import wins; subsequent sources link via concordance.
- **Import order specified.** ORAEC imports first (document-level records), then AES sentences attach to existing ORAEC records via shared TLA base32 text IDs. L0-2b now depends on L0-2a.
- **TLA HF imports all rows, not just premium.** Premium rows tagged `confidence: 'verified'`, non-premium as `confidence: 'unreviewed'`. Total: ~98,543 sentences across 3 datasets.
- **Dev environment defined.** Docker Compose `dev` profile (Postgres + MinIO only). Bootstrap script for venv setup, upstream repo cloning, HF dataset download, and migration.
- **Backup and export strategy added.** `pg_dump` cron + portable JSONL corpus export stored in MinIO.
- **Corpus versioning defined.** Tag-based snapshots after major imports: git tag + `corpus_versions` DB table + MinIO export archive.
- **Contribution model clarified.** Single maintainer for now. Ad-hoc ingestion CLI is the practical contribution path.

### v0.2 (from v0.1)

- **TLA API connector (L2-1) removed.** TLA explicitly prohibits bulk scraping (>10 pages). The sanctioned bulk-access path is their Hugging Face datasets under CC BY-SA 4.0. All TLA data now enters via the expanded HF loader.
- **TLA HF loader expanded.** Three datasets now in scope: Earlier Egyptian (12,773 sentences), Late Egyptian (3,606), Demotic (13,383). Total: ~29,762 premium sentences.
- **Glyph recognition moved to deferred.** Google Fabricius workbench is archived (Nov 2025) and never open-sourced its ML models. EgyptianHieroglyphicText dataset has no license. Glyph recognition is a nice-to-have, not a primary approach.
- **Translations in any language are valid corpus content.** The corpus is not limited to original Egyptian-language texts. English, German, French, and other translations are first-class representation layers. This elevates sacred-texts.com, attalus.org, and other translation sources.
- **Alias table added to Phase 1.** Conventional name variants and shelfmark normalization are foundational for entity resolution in Phase 2.
- **Ad-hoc ingestion CLI added to Phase 1.** Not all data arrives through formal importers. A lightweight manual ingestion path is required from day one.
- **Orphan records are acceptable.** Texts with no cross-references are first-class corpus members. The entity resolution engine treats "no match" as an expected outcome, not a failure.
- **papyri.info connector pivoted.** Access via their public GitHub repo (papyri/idp.data, EpiDoc XML, CC BY 3.0) instead of crawling the site. Egyptian-language yield expected to be modest (primarily Greek papyri with some Coptic).
- **RAMSES license flagged.** CC BY-NC-SA (non-commercial) -- more restrictive than other sources.
- **TranslitModels integration note.** Java-only codebase -- requires JVM wrapper or subprocess integration into the Python stack.
- **Trismegistos scale corrected.** 966,921 total entries (not ~70k). Search behind subscription paywall since 2020; ID-lookup APIs remain open.

---

## Table of Contents

1. Project Overview and Scope
2. Architecture Summary
3. Layer 0: Schema and Identity Backbone
   - 3.1 Canonical Data Model
   - 3.2 Identity Graph and Concordance
   - 3.3 Alias Table and Shelfmark Normalizer
   - 3.4 Upstream Forks and Imports
   - 3.5 Ad-Hoc Ingestion
4. Layer 1: Open Web Acquisition Pipeline
   - 4.1 Seed URL Discovery
   - 4.2 Crawler Architecture
   - 4.3 PDF and OCR Processing
   - 4.4 HTML Text Extraction
   - 4.5 Deduplication and Entity Resolution
5. Layer 2: Structured Data Connectors
   - 5.1 Hugging Face Dataset Loader (TLA)
   - 5.2 RAMSES Corpus Importer
   - 5.3 Papyri.info / APIS Connector
6. Layer 3: ML Processing Pipeline
   - 6.1 Transliteration Language Models
   - 6.2 OCR Post-Correction
   - 6.3 Draft Translation Pipeline
7. Gap Tracker and Work Queue System
8. Repository Structure and Tech Stack
9. Build Phases and Agent Task Assignments
10. Deferred Components
11. Source Inventory and Verification Status
12. Operations
    - 12.1 Development Environment
    - 12.2 Backup and Export
    - 12.3 Corpus Versioning
    - 12.4 Contribution Model

Appendix A: External Repository Reference
Appendix B: Data Model Schema (Draft)

---

## 1. Project Overview and Scope

Project Aegyptus is an open-source initiative to build the first unified, computationally accessible corpus of all known ancient Egyptian texts. The project integrates data from scattered digital sources, structured databases, and eventually physical collections into a single schema with a shared identity graph.

**Goal:** A single queryable system where any known Egyptian text can be found with whatever representation layers exist for it: photograph, hieroglyphic transcription, transliteration, lemmatization, and translations in any language.

**Corpus philosophy:** The corpus is multilayer by design. A 19th-century English translation of the Book of the Dead is a valid representation layer sitting alongside a modern hieroglyphic transcription and a German TLA translation of the same text. All layers carry provenance, attribution, and confidence metadata. Translations in any language are first-class content.

**Orphan records are expected.** Not every text will have cross-references to external databases. Texts ingested from a single source with no concordance links are first-class corpus members. The gap tracker can flag them for future enrichment, but they are immediately queryable.

This document covers the software framework for Layers 0--3 only:

- **Layer 0:** Schema and Identity Backbone
- **Layer 1:** Open Web Acquisition Pipeline
- **Layer 2:** Structured Data Connectors (open/free sources only)
- **Layer 3:** ML Processing Pipeline (OCR, transliteration models, draft translation)

Deferred to future phases:

- TTS-based library outreach system
- Gated database pipeline (publisher negotiations, paywalled content)
- Physical acquisition campaign (bounty board, photogrammetry, field teams)
- Glyph recognition pipeline (image-to-Gardiner classification)

---

## 2. Architecture Summary

The system is organized as a set of pipelines feeding into a central store, with a gap tracker driving prioritization. Each pipeline is independently deployable and testable.

```
                  +------------------+
                  |   Gap Tracker    |
                  |  (prioritizes)   |
                  +--------+---------+
                           |
          +----------------+----------------+
          |                |                |
  +-------v------+  +-----v------+  +------v-------+
  | Layer 1:     |  | Layer 2:   |  | Layer 3:     |
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
                  |  PostgreSQL +    |
                  |  JSONB + MinIO   |
                  +--------+---------+
                           |
                  +--------v---------+
                  |   Query API      |
                  |   (FastAPI)      |
                  +------------------+
```

**Key components:**

| Component | Type | Description |
|-----------|------|-------------|
| Central Store (PostgreSQL + JSONB) | Database | Canonical text records with extended AES-compatible schema |
| Identity Graph | Service | Concordance tables mapping canonical IDs to TLA, Trismegistos, ORAEC, RAMSES, Porter-Moss |
| Alias Table | Data | Conventional name variants and normalized shelfmarks for entity resolution |
| Importers (per-source) | Workers | AES, ORAEC, Nederhof, TLA HF, RAMSES, papyri.info data, crawler output |
| Ad-Hoc Ingestion CLI | Tool | Lightweight manual import path for one-off texts |
| Entity Resolution Engine | Service | Matches incoming records against existing, merges layers, flags unknowns |
| Web Crawler | Pipeline | Focused Egyptological web harvester with PDF/HTML extraction |
| OCR Pipeline | Pipeline | PDF scan processing with Egyptological transliteration post-correction |
| ML Pipeline | Pipeline | Transliteration models, OCR correction, draft translation |
| Gap Tracker | Service | Compares holdings against known-text inventories, generates work queues |
| API Layer | Service | Unified query interface over the entire corpus |

---

## 3. Layer 0: Schema and Identity Backbone

This is the foundation. Nothing else works without a stable data model and a reliable way to say "this text is the same text" across different sources.

### 3.1 Canonical Data Model

The schema is a superset of the AES (Ancient Egyptian Sentences) data model. Every AES record imports with zero transformation. Additional fields extend it for multi-layer representation.

**Text Record (top level):**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| canonical_id | string | Generated | Primary key. Format: `aeg_{source}_{source_id}` (see ID Generation Strategy below) |
| tla_id | string[] | TLA | May map to multiple TLA text IDs |
| trismegistos_id | string | TM | Primary for papyri/ostraca |
| oraec_id | string | ORAEC | Links to ORAEC corpus |
| aes_id | string | AES | Links to simondschweitzer/aes |
| ramses_id | string | RAMSES | Links to RAMSES corpus |
| porter_moss_ref | string | PM | For temple/tomb texts |
| conventional_name | string | Various | e.g., "Tale of Sinuhe", "pBerlin 3022" |
| shelfmarks | string[] | Various | Museum inventory numbers |
| script_type | enum | Classified | hieroglyphic, hieratic, demotic, coptic, greek |
| date_range | object | Various | {earliest, latest, period_label} |
| provenance | object | Various | {findspot, current_location} |
| text_type | string | Classified | literary, religious, administrative, medical, legal, ... |
| completeness | enum | Assessed | complete, fragmentary, damaged |

**Representation Layers (per text):**

| Layer | Format | Notes |
|-------|--------|-------|
| photograph | image references | Links to digitized images, with source attribution |
| hieroglyphic | Unicode / MdC | Machine-readable hieroglyphs. Prefer Unicode per ORAEC recommendations |
| transliteration | Unicode text | Egyptological transliteration. Must use Unicode (h with underdot, etc.) not legacy fonts |
| lemmatization | token-level JSON | Word-by-word with AED lemma IDs, POS tags, morphology |
| translations | keyed by language | Each translation carries: language, translator, publication, year, confidence |
| bibliography | structured refs | All publications that reference this text |

**Sentence-Level Data:**

The corpus stores sentence-level data in a dedicated `sentences` table. This bridges the AES data model (sentence-oriented: 100k+ sentence records) and the ORAEC model (document-oriented: 13k documents with nested sentences). Each sentence belongs to a canonical text and carries its own transliteration, translations, and token-level annotations.

| Field | Type | Notes |
|-------|------|-------|
| id | serial | Primary key |
| canonical_id | FK -> texts | Parent text |
| sequence_num | integer | Position within the text |
| transliteration | text | Sentence-level transliteration (Unicode) |
| translation | JSONB | Keyed by language: `{"de": "...", "en": "...", "fr": "..."}` |
| tokens | JSONB | Array of token objects: `[{written_form, lemma_id, pos, hiero, ...}]` |
| source | text | Origin: `'oraec'`, `'aes'`, `'tla_hf'`, ... |
| source_detail | JSONB | Provenance metadata |
| confidence | text | `'verified'`, `'unreviewed'`, `'ml_draft'` |

Token-level data lives in the JSONB `tokens` array rather than a separate table. This avoids millions of token rows while still supporting queries via GIN indexes on the JSONB column. Sentence-level queries (join, filter by source/confidence/language) use standard relational operations.

**ID Generation Strategy:**

Canonical IDs are deterministic and source-derived to ensure idempotent imports:

- **Source-imported records:** `aeg_{source}_{source_id}` — e.g., `aeg_oraec_1234`, `aeg_aes_IBcAYfWPD6`, `aeg_tla_hf_12773`
- **Ad-hoc imports:** `aeg_adhoc_{content_hash}` — hash of input content ensures the same file imported twice produces the same ID
- **Web-crawled records:** `aeg_crawl_{url_hash}` — derived from the source URL

**First-import-wins rule:** When a text is first created from any source, it gets its `canonical_id`. When a second source (e.g., AES) matches an existing record via entity resolution or shared IDs, it links to the existing record via concordance — it does not create a new ID.

**Import order matters:** ORAEC imports first (L0-2a) because it provides document-level records. AES sentences then attach to existing ORAEC records via shared TLA base32 text IDs found in AES's `text` field. This minimizes orphan-then-merge scenarios.

**Duplicate detection:** If entity resolution fails to match on the first pass (creating two canonical records for the same physical text), the gap tracker surfaces suspected duplicates for manual merge. This is an expected operational reality, not a bug.

### 3.2 Identity Graph and Concordance

The concordance is a many-to-many mapping table. A single canonical text may have IDs in TLA, Trismegistos, ORAEC, RAMSES, and multiple shelfmarks. Conversely, some database entries may map to parts of a canonical text (e.g., TLA may have separate entries for recto and verso of the same papyrus).

**Implementation:**

- PostgreSQL table: `concordance(canonical_id, external_system, external_id, relationship_type)`
- `relationship_type`: `exact_match | part_of | version_of | parallel_to`
- **UNIQUE constraint:** `UNIQUE (external_system, external_id, canonical_id)` — prevents the same link being recorded twice, but allows one external ID to map to multiple canonical records (e.g., a TLA entry covering both recto and verso, split into separate canonical texts). A lookup by external ID returns a list, not a single row — callers must handle this.
- Bootstrap from ORAEC's existing ID mappings (oraec_id <-> aes_id <-> tla_id <-> aed_id)
- Extend with Trismegistos cross-references via their TexRelations Matcher API (open, no subscription required for ID lookups)
- Extend with ORAEC's published mapping files: `mapping_oraec_trismegistos.csv`, `mapping_oraec_wikidata.tsv`, `mapping_oraec_karnak.tsv`
- Porter-Moss references added manually for temple inscription texts (no existing digital concordance)

**Orphan records:** A `texts` record with zero rows in `concordance` is valid. These are texts ingested from a single source with no known cross-references. They are fully queryable and can be enriched later.

### 3.3 Alias Table and Shelfmark Normalizer

The alias table maps variant conventional names and shelfmark formats to canonical records. This is essential for entity resolution when web-crawled content uses informal names.

**Examples of aliases that must resolve to the same canonical record:**

- "Tale of Sinuhe" / "Story of Sinuhe" / "Sinuhe" / "Die Geschichte des Sinuhe"
- "pBerlin 3022" / "P. Berlin 3022" / "Papyrus Berlin 3022" / "Berlin 3022"
- "Book of the Dead" / "Totenbuch" / "BD" (though this is a collection, not a single text)

**Implementation:**

- PostgreSQL table: `aliases(alias_text, alias_type, canonical_id, confidence)`
- `alias_type`: `conventional_name | shelfmark | abbreviation | foreign_title`
- Shelfmark normalizer: rule-based function that strips prefixes (P., p, Papyrus, O., Ostracon), normalizes spacing, and lowercases for comparison
- Seed data auto-generated from ORAEC `conventional_name` fields (13,026 records) and AES text metadata
- Manual curation pass required to link variant spellings

**Agent Task L0-5:** Build the alias table and shelfmark normalizer. Auto-generate seed data from ORAEC and AES imports. Implement the normalization rules. Provide a CLI for manual alias additions.

### 3.4 Upstream Forks and Imports

Day-one imports from existing repositories:

| Repository | Action | What It Gives You | License | Verified |
|------------|--------|-------------------|---------|----------|
| oraec/corpus_raw_data | Fork, extend schema | 13,026 texts with transliteration, lemmatization, German translations, cross-ref IDs. JSON per-document. | CC-BY-SA-4.0 / CC0 (mappings) | Yes -- active, last updated Jun 2024 |
| simondschweitzer/aes | Import as base data | 100,000+ sentences across 11,000+ texts, 14 subcorpora, sentence-level structure, editor attribution | CC-BY-SA-4.0 | Yes -- static since May 2021, stable snapshot |
| oraec/formerly-mdc-now_unicode | Import directly | 360+ Unicode hieroglyphic texts (200+ from AES, 150+ from JSesh, 14 from Wikisource) + Gardiner-to-Unicode mapping CSV | CC (unspecified variant) | Yes -- active, last updated Apr 2024 |
| nederhof hierojax/texts | Import directly | 118 texts in Unicode hieroglyphs: papyri, ostraca, stelae, Coffin Texts, Urkunden IV (43 texts) | GPL-3.0 (tooling); text provenance needs clarification | Yes -- active |
| TLA Hugging Face datasets | Import via loader | 3 datasets: Earlier Egyptian (12,773), Late Egyptian (3,606), Demotic (13,383). Hieroglyphs, transliteration, UPOS, glossing, German translation | CC-BY-SA-4.0 | Yes -- active, corpus at v20 |
| oraec/recommendations-encoding-hieroglyphs | Adopt as standard | Normalization rules for ~880 Unicode hieroglyph codepoints (character vs. glyph variant classification) | None stated | Yes -- static since Oct 2022, reference doc |

**ID linkage confirmed by recon:** ORAEC and AES share the AED lemma ID space (numeric, 5-6 digits) and TLA base32 entity IDs. The Gardiner-to-Unicode mapping in `complete_mapping.csv` bridges between AES's Gardiner `hiero` field and ORAEC's Unicode `hiero` field. The encoding recommendations provide normalization rules for which Unicode codepoints are canonical.

**AES data structure (important for importer design):** AES uses 14 large JSON files organized by subcorpus (`_aes_bbawamarna.json`, `_aes_sawlit.json`, etc.), not per-document files like ORAEC. Each file contains many sentence records keyed by 26-character base32 IDs. The importer must handle files up to ~10 MB+.

**ORAEC data structure:** 13,026 individual JSON files (`oraec1.json` through `oraec10891.json`, non-contiguous numbering). Each contains a single text record with nested sentences and token-level annotations. Plus 5 mapping CSV/TSV files at repo root.

**Agent Task L0-1:** Set up PostgreSQL database with the schema from Appendix B. Write Alembic migration scripts.

**Agent Task L0-2a:** Write ORAEC bulk importer. Input: 13,026 JSON files from oraec/corpus_raw_data. Output: populated central store with texts, representation layers, and concordance entries. Must also import the 5 mapping files (Trismegistos, Wikidata, Karnak, Karnak lemmata, VEGA).

**Agent Task L0-2b:** Write AES bulk importer. Input: 14 subcorpus JSON files from simondschweitzer/aes. Output: sentences inserted into the `sentences` table, linked to existing ORAEC canonical records via shared TLA base32 text IDs. **Depends on L0-2a completing first** — AES sentences attach to ORAEC document records. Where no matching ORAEC record exists, create a new canonical record. Must handle files up to ~10 MB+.

**Agent Task L0-3:** Write Nederhof/hierojax importer. Parse 118 Unicode hieroglyphic text files (HTML/JSON format), assign canonical IDs, insert as hieroglyphic representation layers.

**Agent Task L0-4:** Write concordance bootstrap script. Extract all existing ID mappings from ORAEC mapping files and AES metadata. Seed the concordance table with ORAEC <-> AES <-> TLA <-> Trismegistos <-> Wikidata <-> Karnak linkages.

### 3.5 Ad-Hoc Ingestion

Not all data arrives through formal importers. Researchers may contribute individual texts, translations, or bibliographic references outside of any structured pipeline. The ad-hoc ingestion path handles these cases.

**Requirements:**

- CLI tool: `aegyptus ingest <file> [--name "..."] [--script-type ...] [--source "..."] [--ids tla:XXXXX,tm:YYYYY]`
- Accepts: plain text, JSON, CSV
- Creates a canonical record with minimal metadata
- Inserts whatever representation layers can be inferred from the input
- Tags all layers with `source: 'ad_hoc'` and `confidence: 'unreviewed'`
- Optionally runs entity resolution against existing corpus (but does not require a match)
- No external IDs required -- orphan records are valid

**Agent Task L0-6:** Build the ad-hoc ingestion CLI. Must support text, JSON, and CSV input. Must create valid canonical records with minimal metadata. Must tag all output as ad-hoc sourced.

---

## 4. Layer 1: Open Web Acquisition Pipeline

This layer systematically harvests Egyptological texts and translations from the open web. It targets both original-language transcriptions and translations in any language.

### 4.1 Seed URL Discovery

Rather than broad web crawling, start from curated Egyptological indexes:

| Source | URL | Description | Verified Status |
|--------|-----|-------------|-----------------|
| ORAEC metasearch index | oraec.github.io | Maps content across TLA, JSesh, Wikisource, PNM | Active |
| EEF Digitized Source Texts | egyptologyforum.org/EEFSourcetexts.html | ~60 URLs to scanned publications. Compiled by Michael Tilgner. | Exists, last updated Oct 2013. Expect link rot. |
| EEF Guide to Internet Resources | egyptologyforum.org/EEFtexts.html | 100+ text entries with links to translations, photographs, transcriptions. Chronologically organized. | Exists, version 21, Sep 2013. Richest single index but many dead links expected. |
| Pyramid Texts Online library | pyramidtextsonline.com/library.html | Links to freely available PDFs (Maspero, Speleers, Faulkner, Edwin Smith, etc.) | Exists, returns 403 to automated fetchers. PDFs hosted externally (Archive.org, etc.). |
| Internet Archive Egyptology | archive.org | Pre-1930 publications (public domain). Bulk download via their API. | Active, official API available. |
| sacred-texts.com/egy | sacred-texts.com/egy/index.htm | 127+ texts: English translations of Egyptian religious and literary texts (Budge, Faulkner era). | Exists, returns 403 to bots. Content is 19th/20th century English translations -- valid as translation layers. |
| attalus.org/egypt | attalus.org/egypt | ~200+ texts across 9 categories. Late/Ptolemaic period. English translations by Andre Dollinger. | Active, better than expected scale. |
| AWOL (Ancient World Online) | ancientworldonline.blogspot.com | Aggregates open-access Egyptological resources. | Active |

**Note on content classification:** Many web sources provide translations rather than original-language Egyptian text. These are valid corpus content ingested as translation representation layers (`layer_type: 'translation'`, `language: 'en'`/`'fr'`/`'de'`, `confidence: 'unreviewed'`). The entity resolution engine links them to canonical records where possible.

**Note on bot protection:** Several target sites (sacred-texts.com, pyramidtextsonline.com) return 403 to automated fetchers. The crawler must use respectful access patterns: appropriate User-Agent strings, rate limiting, robots.txt compliance. If a site blocks automated access, document it and move on -- do not attempt evasion.

**Agent Task L1-1:** Build seed URL harvester. Scrape the above index pages (where permitted), extract all outbound URLs, classify by expected content type (PDF, HTML, image), deduplicate, and store in a crawl queue database table. Run a link-rot check on EEF pages and report dead links.

### 4.2 Crawler Architecture

A distributed task queue where each job is a URL + expected content type.

**Stack:**

- Task queue: Redis-backed (Celery)
- Workers: stateless, pull jobs, fetch pages, classify output
- Rate limiter: per-domain adaptive. Respect robots.txt. Default: 1 req/sec/domain.
- Cache layer: content-addressed store (hash of URL + fetch date). Never re-fetch.
- Output: raw fetched content stored in object storage (MinIO, S3-compatible), metadata in PostgreSQL.

**Politeness rules:**

- Internet Archive: use their bulk download API, not page scraping
- IFAO: max 1 req/3sec, cache aggressively
- University repositories: follow robots.txt strictly
- All domains: exponential backoff on 429/503 responses
- Sites returning 403: log and skip. Do not spoof user agents or attempt bypass.

**Agent Task L1-2:** Build the crawler worker framework. Input: URL + content type hint from queue. Output: fetched content in object storage + metadata record. Must support PDF, HTML, and image downloads.

**Agent Task L1-3:** Build the rate limiter and politeness layer. Per-domain config, robots.txt parser, adaptive backoff.

### 4.3 PDF and OCR Processing

Most pre-2000 Egyptological publications are scanned PDFs. Standard OCR fails on transliteration characters.

**Pipeline:**

1. **Classify PDF** (text-searchable vs scan). If text layer exists, extract directly with pdftotext.
2. **For scans**, run Tesseract with custom trained model for Egyptological transliteration. Fallback: Google Cloud Vision API.
3. **Post-correction** using TranslitModels (MaReTEgyptologists/TranslitModels). Note: Java-based -- requires JVM subprocess wrapper. The statistical language model re-ranks OCR hypotheses and corrects common misreadings (h with underdot <-> h, etc.).
4. **Structure extraction**: identify text blocks as hieroglyphic transcription, transliteration, translation, or commentary based on font/layout heuristics.
5. **Output** structured records into staging area for entity resolution.

**Agent Task L1-4:** Build the PDF classification and text extraction pipeline. Input: PDF from object store. Output: extracted text blocks with structural classification.

**Agent Task L1-5:** Integrate TranslitModels as a post-correction service. Input: raw OCR output. Output: corrected transliteration. Implementation: JVM subprocess wrapper around the Java JARs.

### 4.4 HTML Text Extraction

Many websites contain transcriptions and translations as formatted HTML. These need site-specific parsers.

**Approach:**

- Build a parser registry: each domain gets a custom parser class
- Parsers extract: text content, structural markers (utterance numbers, column/line references), language, and source attribution
- Fallback generic parser using readability-style extraction for unknown domains
- All parsers output the same intermediate format for the entity resolution pipeline
- **Language detection** on extracted text to correctly tag translation layers (English, French, German, etc.)

**Priority parser targets (by corpus value):**

1. sacred-texts.com/egy -- 127+ English translation pages, chapter-by-chapter HTML
2. attalus.org/egypt -- 200+ English translation pages, well-structured by category
3. pyramidtextsonline.com -- index page with outbound PDF links
4. EEF pages -- link indexes pointing to external resources
5. AWOL links -- heterogeneous, requires generic fallback parser

**Agent Task L1-6:** Build the HTML parser registry and implement parsers for the top 5 source sites. Output: structured text records with language tags and source attribution.

### 4.5 Deduplication and Entity Resolution

The same text appears across many sources under different names. The entity resolution engine must unify them.

**Matching strategy (applied in order):**

1. **Exact ID match:** If incoming record carries a TLA ID, Trismegistos ID, or ORAEC ID, look up directly in concordance table.
2. **Shelfmark match:** Normalize shelfmarks using the L0-5 normalizer and match against known inventory.
3. **Title/alias match:** Look up conventional name in the alias table. Fuzzy match against aliases with configurable similarity threshold.
4. **Content match:** For unidentified texts, compare transliteration sequences against the corpus using n-gram similarity. Flag high-similarity matches for human review.

**On match:** Add the new representation layer(s) to the existing canonical record. Tag with source provenance.

**On no match:** Create a new canonical record, assign a new `canonical_id`, tag with `source` provenance. Orphan records are expected and valid. Flag for optional human review but do not block ingestion.

**Agent Task L1-7:** Build the entity resolution engine. Implement the four matching strategies above. Integrate the alias table and shelfmark normalizer from L0-5.

**Agent Task L1-8:** Build the staging-to-central-store merge pipeline. On match: layer merge. On no match: new record creation.

---

## 5. Layer 2: Structured Data Connectors

These connectors pull from databases and APIs that provide structured, machine-readable data. Only freely accessible sources are covered here. Paywalled/gated sources are deferred.

**Guiding principle:** Respect all API terms and access restrictions. Use official bulk-access paths where they exist. Never scrape when an API or data dump is available.

### 5.1 Hugging Face Dataset Loader (TLA)

The TLA team publishes curated datasets on Hugging Face under the `thesaurus-linguae-aegyptiae` organization. This is the **official sanctioned path** for bulk TLA data access.

**Datasets (verified April 2026):**

| Dataset | Premium Rows | Total in Corpus | Corpus Version | Last Updated | Action |
|---------|-------------|-----------------|----------------|-------------|--------|
| tla-Earlier_Egyptian_original-v18-premium | 12,773 | 55,026 | v18 | Jun 2024 | Import all 55,026 |
| tla-late_egyptian-v19-premium | 3,606 | 12,361 | v19 | Jan 2025 | Import all 12,361 |
| tla-demotic-v18-premium | 13,383 | 31,156 | v18 | May 2024 | Import all 31,156 |

**Schema (Earlier Egyptian, 8 fields):**

- `hieroglyphs` -- Unicode v15 hieroglyphs, space-separated (JSesh `<g>` tags for non-Unicode chars)
- `transliteration` -- Leiden Unified Transliteration standard
- `lemmatization` -- TLA Lemma ID + pipe + lemma transliteration (e.g., `90880|nd`)
- `UPOS` -- Universal POS tags (NOUN, VERB, ADJ, ADP, PRON, etc.)
- `glossing` -- inflectional/morphological glosses
- `translation` -- German only
- `dateNotBefore` / `dateNotAfter` -- BCE integer dates

**Note:** The Demotic dataset has no `hieroglyphs` field (Demotic is not hieroglyphic) and adds an `authors` field. The Late Egyptian dataset may have schema differences -- verify at import time.

**Note:** The TLA corpus is now at v20. Newer dataset versions may be released. The loader should support version tracking and incremental updates.

**License:** CC BY-SA 4.0 International on all three datasets.

**Import strategy:** Import all rows from all three datasets (~98,543 sentences total), not just premium. Premium rows are tagged `confidence: 'verified'`; non-premium rows are tagged `confidence: 'unreviewed'`. This nearly triples the TLA sentence count. Users can filter by confidence level at query time.

**Agent Task L2-2:** Write a Hugging Face dataset loader for all three TLA datasets. Import all rows (premium and non-premium). Map TLA HF schema fields to central store schema. Tag premium rows as `verified`, non-premium as `unreviewed`. Insert into the `sentences` table with token-level data in JSONB. Support version tracking for future dataset updates.

### 5.2 RAMSES Corpus Importer

The RAMSES (Ramses Online) transliteration corpus covers Late Egyptian texts extensively. Published on GitLab and Zenodo.

**Source details:**

- GitLab: gitlab.cnam.fr/rosmorse/ramses-trl (may need `/gitlab/` prefix in URL; repo was slow/unreliable during recon)
- Zenodo: DOI 10.5281/zenodo.4954597 (published June 2021)
- Zenodo contains: `network.h5` (106.2 MB trained model) + `ramses-trl_2021_05_29.zip` (9.4 MB software+data)
- Scale: ~500,000 MdC-encoded words across 4,200+ texts
- Format: line-based files with source (glyph codes) and target (transliteration) pairs
- **License: CC BY-NC-SA** (non-commercial). The Zenodo record says CC BY 4.0 -- there is a license inconsistency. Clarify before large-scale use.
- RAMSES Online (ramses.ulg.ac.be): 65,000 words publicly accessible of 520,000+ total. Appears dormant. No API.

**Agent Task L2-3:** Build RAMSES importer. Download from Zenodo, parse transliteration files, map to central schema, insert as transliteration layer. Document the license situation and flag the NC restriction.

### 5.3 Papyri.info / APIS Connector

Papyri.info aggregates data from APIS, the Duke Databank, and the Heidelberger Gesamtverzeichnis. **This is primarily a Greek papyri database.** Egyptian-language yield is expected to be modest -- mainly Coptic with limited hieratic/demotic.

**Access path:** The public GitHub repository [papyri/idp.data](https://github.com/papyri/idp.data) mirrors all data hourly in EpiDoc XML format. CC BY 3.0. ~233k commits. This is the bulk access path -- do not crawl the site (has Anubis bot protection).

**Collections in idp.data:** DDbDP, DCLP, HGV, APIS, Biblio -- all in EpiDoc XML.

**Agent Task L2-4:** Build papyri.info connector. Clone the idp.data GitHub repo, filter for Egyptian-language texts (hieratic, demotic, Coptic), parse EpiDoc XML, cross-reference with Trismegistos IDs, and output metadata and transcription layers for central store. Expect modest yield.

---

## 6. Layer 3: ML Processing Pipeline

ML tools process incoming materials that lack machine-readable text. All ML output is treated as draft quality requiring human review. Provenance tags always indicate whether a layer was human-authored or ML-generated, and which model version produced it.

### 6.1 Transliteration Language Models

The MaReTEgyptologists/TranslitModels repo provides statistical word models trained on RAMSES and AES data. These serve multiple purposes:

- OCR post-correction for scanned transliterations
- Spell-checking and validation for human-entered transliterations
- Eventually: input features for neural translation models

**Integration note:** TranslitModels is Java-only (JARs + Java source code). Options for integration into the Python stack:

1. **JVM subprocess wrapper** (recommended): call the Java JARs via subprocess. Simplest, preserves original models.
2. **Rewrite in Python**: more effort, better integration. Consider only if subprocess latency is a bottleneck.
3. **Defer**: use TLA HF lemmatization data directly for language model features.

**License:** CC BY 4.0 International.

**Agent Task L3-3:** Evaluate TranslitModels capabilities. Build JVM subprocess wrapper. Retrain on expanded corpus (AES + RAMSES + all newly imported transliterations) if the training pipeline supports it.

### 6.2 OCR Post-Correction

Specialized post-correction for Egyptological OCR output. The main failure modes are:

- Transliteration diacritics: h-underdot misread as h, etc.
- Hieroglyphic sign names (Gardiner codes) garbled
- Mixed-script text (transliteration + German/French/English commentary) incorrectly segmented

**Agent Task L3-4:** Build an OCR post-correction service. Input: raw OCR text. Output: corrected text with confidence scores. Use TranslitModels (via JVM wrapper) + a trained character-level correction model.

### 6.3 Draft Translation Pipeline

For texts that have transliteration and lemmatization but no translation in a target language, an LLM-based pipeline can produce draft translations. These are always flagged as machine-generated and queued for expert review.

**Approach:**

- Input: lemmatized sentence with AED lemma IDs and POS tags
- Look up lemma meanings from AED dictionary data
- Feed to a prompted LLM (e.g., Claude API) with Egyptological context
- Output: draft translation with uncertainty markers
- All output tagged: `{source: 'ml_draft', model: '...', confidence: 'low', needs_review: true}`
- Target languages: English first, then French and German

**Agent Task L3-5:** Build the draft translation service. Must clearly tag all output as machine-generated. Design the prompt template for Egyptological translation with access to AED lemma definitions.

---

## 7. Gap Tracker and Work Queue System

The gap tracker continuously compares what the corpus holds against what should exist, and generates prioritized work queues.

**Known-text inventories to compare against:**

- **Trismegistos:** 966,921+ text records across all languages (Egyptian is the historical core). Use their TexRelations Matcher API for ID-based lookups. Bulk discovery of Egyptian-specific texts may require institutional subscription (search restricted since Jan 2020).
- **Porter-Moss (Topographical Bibliography):** Comprehensive index of temple/tomb inscriptions with locations. Partially digitized.
- **TLA text list:** Texts in the TLA that aren't yet in HF datasets (gap between v20 corpus and published datasets).
- **EEF source text bibliography:** Published text editions. Cross-reference against what we actually have digitized.

**Gap types and priorities:**

| Gap Type | Priority | Action |
|----------|----------|--------|
| Text exists digitally, not yet imported | P0 -- Immediate | Add to importer queue |
| Text published in print, not digitized | P1 -- High | Add to OCR/scanning queue |
| Text exists in museum, unpublished | P2 -- Medium | Deferred: physical acquisition |
| Text has transcription but no translation | P3 -- Lower | Add to ML draft translation queue |
| Text has translation but no lemmatization | P3 -- Lower | Add to NLP processing queue |
| Text is an orphan record (no cross-references) | P3 -- Lower | Add to enrichment/matching queue |

**Agent Task GT-1:** Build the gap tracker service. Input: central store contents + Trismegistos API lookups. Output: prioritized gap list with recommended action per gap.

**Agent Task GT-2:** Build the work queue dashboard. Web UI showing gap statistics, queue depths, recent imports, and data quality metrics.

---

## 8. Repository Structure and Tech Stack

**Monorepo structure:**

```
aegyptus/
├── core/                    # Shared Python library (models, utils, normalizers)
│   ├── models/             # SQLAlchemy/Pydantic data models
│   ├── concordance/        # Alias tables, shelfmark normalizers
│   └── resolution/         # Entity resolution engine
├── schema/                  # Alembic migrations, JSON schema definitions
├── importers/
│   ├── oraec/              # ORAEC bulk importer (L0-2a)
│   ├── aes/                # AES subcorpus importer (L0-2b) — runs after ORAEC
│   ├── nederhof/           # hierojax Unicode text importer (L0-3)
│   ├── tla_hf/             # Hugging Face dataset loader, all 3 datasets (L2-2)
│   ├── ramses/             # RAMSES corpus importer (L2-3)
│   └── papyri_info/        # papyri.info EpiDoc XML connector (L2-4)
├── crawler/
│   ├── seeds/              # Seed URL harvester
│   ├── workers/            # Fetch workers
│   ├── parsers/            # Site-specific HTML parsers
│   └── rate_limiter/       # Per-domain rate limiting
├── processing/
│   ├── ocr/               # PDF OCR pipeline
│   ├── post_correction/   # TranslitModel integration (JVM wrapper)
│   └── draft_translation/ # LLM-based draft translator
├── gap_tracker/            # Gap analysis and work queues
├── ingest/                 # Ad-hoc ingestion CLI
├── api/                    # Unified query API (FastAPI)
├── dashboard/              # Web UI for gap tracker and admin
├── scripts/
│   ├── bootstrap.sh       # One-command dev environment setup
│   ├── export_corpus.py   # Portable JSONL corpus export
│   ├── import_corpus.py   # Reconstruct DB from export
│   └── backup.sh          # pg_dump cron wrapper
├── data/
│   ├── upstream/          # Cloned source repos (gitignored)
│   ├── aliases/           # Alias tables, shelfmark normalizers (seed data)
│   └── seed_urls/         # Curated URL lists
├── docker/
│   ├── Dockerfile.base    # Shared base image with common Python deps
│   ├── Dockerfile.api     # API service
│   ├── Dockerfile.crawler # Crawler workers
│   ├── Dockerfile.ocr     # OCR pipeline (heavier deps)
│   └── ...
├── docker-compose.yml      # dev profile (Postgres+MinIO) and full profile (+Redis)
├── pyproject.toml          # Monorepo Python packaging
└── README.md
```

**Shared core library:** The `core/` package contains data models, the concordance/alias system, shelfmark normalizer, and entity resolution logic. It is installed as an editable dependency in all services (`pip install -e ./core`). In Docker, it is copied and installed into each service image from a shared base.

**Dual execution model:** Every pipeline runs both as a plain Python module (`python -m aegyptus.importers.oraec`) with a `DB_URL` environment variable for development, and as a Docker service for deployment and integration testing.

**Tech stack:**

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Central store | PostgreSQL 16 + JSONB | Relational for structured queries, JSONB for flexible schema evolution |
| Object storage | MinIO (S3-compatible) | Stores PDFs, images, raw fetched content |
| Task queue | Redis + Celery | Mature, well-documented distributed task processing |
| API | FastAPI (Python) | Async, auto-documented, good ecosystem for data work |
| ML pipeline | PyTorch + Hugging Face | Standard ML stack, direct compatibility with TLA HF datasets |
| Crawler | Python (httpx + BeautifulSoup) | Async HTTP client, robust HTML parsing |
| TranslitModels | Java (subprocess) | Wrapped via subprocess; native Java JARs preserved |
| Dashboard | Jinja2 templates (initially) | Admin-only initially; React upgrade if needed later |
| Containerization | Docker + docker-compose | Reproducible dev environment, easy deployment |
| Migrations | Alembic | Standard SQLAlchemy migration tooling |
| Python packaging | pyproject.toml + pip | Monorepo with editable installs for core library |

---

## 9. Build Phases and Agent Task Assignments

Tasks are organized into sequential phases. Each phase has a clear deliverable and can be verified before proceeding.

### Phase 1: Foundation (Weeks 1--3)

**Deliverable:** Central store populated with all freely available existing data. Alias table seeded. Ad-hoc ingestion operational.

| Task ID | Description | Dependencies | Est. Effort |
|---------|-------------|--------------|-------------|
| L0-1 | PostgreSQL schema + Alembic migrations | None | 2--3 days |
| L0-2a | ORAEC bulk importer (13,026 JSON files + 5 mapping files) | L0-1 | 3--4 days |
| L0-2b | AES bulk importer (14 subcorpus JSON files, 100k+ sentences -> sentences table) | L0-1, L0-2a | 3--4 days |
| L0-3 | Nederhof/hierojax importer (118 texts) | L0-1 | 1--2 days |
| L0-4 | Concordance bootstrap from ORAEC mappings + AES metadata | L0-2a, L0-2b | 2--3 days |
| L0-5 | Alias table + shelfmark normalizer (auto-seed + manual curation tools) | L0-4 | 3--4 days |
| L0-6 | Ad-hoc ingestion CLI | L0-1 | 2--3 days |
| L2-2 | TLA HF dataset loader (all 3 datasets, ~98.5k sentences, premium + non-premium) | L0-1 | 2--3 days |
| L2-3 | RAMSES corpus importer (Zenodo download) | L0-1 | 2--3 days |

**Verification:** Central store contains ~25,000+ text records with at least one representation layer each. Sentences table contains ~200,000+ sentence records (ORAEC nested sentences + AES sentences + TLA HF sentences). Concordance table links records across TLA, ORAEC, AES, and Trismegistos ID systems. Alias table covers major conventional names extracted from ORAEC/AES metadata. Ad-hoc CLI can ingest a freestanding text with no external IDs. Corpus tagged as `v0.1.0-phase1`.

### Phase 2: Web Pipeline (Weeks 3--6)

**Deliverable:** Automated web harvesting operational. First batch of newly acquired texts and translations merged into corpus.

| Task ID | Description | Dependencies | Est. Effort |
|---------|-------------|--------------|-------------|
| L1-1 | Seed URL harvester + link-rot check | None | 2--3 days |
| L1-2 | Crawler worker framework | L1-1 | 4--5 days |
| L1-3 | Rate limiter + politeness layer | L1-2 | 2--3 days |
| L1-6 | HTML parser registry + top 5 site parsers | L1-2 | 4--5 days |
| L1-7 | Entity resolution engine (integrates alias table) | L0-5 | 5--7 days |
| L1-8 | Staging-to-store merge pipeline | L1-7 | 3--4 days |
| L2-4 | Papyri.info connector (GitHub repo, EpiDoc XML) | L0-1 | 3--4 days |

**Verification:** Crawler has processed all accessible seed URLs. New texts and translations discovered and merged. Entity resolution correctly links duplicates and creates orphan records for unmatched content. Papyri.info connector yields Egyptian-language content (document actual yield).

### Phase 3: Processing and ML (Weeks 6--9)

**Deliverable:** PDF/OCR pipeline operational. TranslitModels integrated. Gap tracker generating work queues. Draft translation producing output.

| Task ID | Description | Dependencies | Est. Effort |
|---------|-------------|--------------|-------------|
| L1-4 | PDF classification + text extraction | L1-2 | 4--5 days |
| L1-5 | TranslitModels post-correction service (JVM wrapper) | L1-4 | 3--4 days |
| L3-3 | TranslitModels evaluation + expanded corpus retraining | Phase 1 complete | 3--4 days |
| L3-4 | OCR post-correction service | L1-5, L3-3 | 3--4 days |
| L3-5 | Draft translation service (LLM-based) | Phase 1 complete | 4--5 days |
| GT-1 | Gap tracker service (central store vs. Trismegistos) | Phase 1 complete | 4--5 days |
| GT-2 | Work queue dashboard | GT-1 | 3--4 days |

**Verification:** PDF pipeline processes a test batch of 50 scanned publications. TranslitModels wrapper produces corrected transliterations. Gap tracker identifies the top 100 highest-priority missing texts. Draft translator produces English translations for 100 test sentences with appropriate confidence tagging.

### Phase 4: API and Integration (Weeks 9--12)

**Deliverable:** Unified query API operational. Full pipeline from discovery through processing to storage running end-to-end.

| Task ID | Description | Dependencies | Est. Effort |
|---------|-------------|--------------|-------------|
| API-1 | FastAPI query endpoints (search by text, lemma, date, provenance, language) | Phase 1 | 5--7 days |
| API-2 | Bulk export endpoints (JSON, CSV, TEI-XML) | API-1 | 3--4 days |
| API-3 | Cross-reference resolution API (input any ID, get canonical record) | L0-4 | 2--3 days |
| INT-1 | End-to-end integration testing | All above | 5--7 days |
| INT-2 | Documentation and contributor onboarding guide | INT-1 | 3--4 days |

---

## 10. Deferred Components

The following components are explicitly out of scope for this build phase. They are documented here for planning continuity.

### Glyph Recognition Pipeline (moved from Layer 3)

Image-to-Gardiner-code classification for photographs of hieroglyphic inscriptions. Deferred because:

- Google Fabricius workbench (the plan's original reference implementation) is archived (Nov 2025) and never open-sourced its ML models or 50k+ training dataset.
- The primary alternative training dataset (rfuentesfe/EgyptianHieroglyphicText, 13,729 images, 310 classes) has no license file.
- Nederhof's `hocr` repo (hieroglyphic OCR to Unicode) is a potential starting point but needs evaluation.
- Glyph recognition is a nice-to-have addition, not a primary data acquisition strategy.

When revisited, the infrastructure supports it: `layer_type: 'hieroglyphic'` with `confidence: 'ml_draft'` is already in the schema.

### TTS Library Outreach System

Voice bot infrastructure for systematically contacting museums, archives, and university departments to inquire about unpublished holdings. Requires the gap tracker (Phase 3) to generate target lists.

### Gated Database Pipeline

Connectors for paywalled content: De Gruyter, Brill/Peeters (OLA series), IFAO paid publications. Requires publisher negotiations and licensing agreements.

### Physical Acquisition Campaign

Bounty board for photographing unpublished materials, photogrammetry of temple walls, RTI imaging of worn inscriptions. Depends on Phases 1--3 being operational.

---

## 11. Source Inventory and Verification Status

All sources were verified by automated reconnaissance in April 2026. This table summarizes the current state.

### Structured Data Sources

| Source | Scale | Format | License | Status | Notes |
|--------|-------|--------|---------|--------|-------|
| ORAEC corpus_raw_data | 13,026 texts | JSON per-doc | CC-BY-SA-4.0 | Active (Jun 2024) | Primary import source |
| AES (simondschweitzer/aes) | 100k+ sentences, 11k+ texts | JSON per-subcorpus (14 files) | CC-BY-SA-4.0 | Static (May 2021) | Stable snapshot |
| TLA HF Earlier Egyptian | 12,773 sentences | JSONL/Parquet | CC-BY-SA-4.0 | Active (Jun 2024) | Corpus v18 |
| TLA HF Late Egyptian | 3,606 sentences | JSONL/Parquet | CC-BY-SA-4.0 | Active (Jan 2025) | Corpus v19 |
| TLA HF Demotic | 13,383 sentences | JSONL/Parquet | CC-BY-SA-4.0 | Active (May 2024) | No hieroglyphs field |
| ORAEC formerly-mdc-now_unicode | 360+ texts | Markdown + CSV | CC (variant unclear) | Active (Apr 2024) | Gardiner-to-Unicode mapping |
| Nederhof hierojax | 118 texts | HTML/JSON (Unicode hieroglyphs) | GPL-3.0 (tooling) | Active | 43 Urkunden IV texts |
| RAMSES (Zenodo) | ~500k words, 4,200+ texts | Line-based MdC pairs | CC BY-NC-SA (GitLab) / CC BY 4.0 (Zenodo) | Static (Jun 2021) | License inconsistency |
| papyri.info (idp.data) | ~233k commits | EpiDoc XML | CC BY 3.0 | Active | Mostly Greek; Egyptian yield modest |
| ORAEC encoding recommendations | 880 codepoints | CSV + Markdown | None stated | Static (Oct 2022) | Normalization reference |
| TranslitModels | Statistical models | Java JARs | CC BY 4.0 | Exists | Java-only; needs wrapping |
| ORAEC mapping files | 5 files | CSV/TSV | CC0 | Active | TM, Wikidata, Karnak, VEGA |

### Web Sources (for crawler)

| Source | Scale | Content Type | Access | Notes |
|--------|-------|-------------|--------|-------|
| sacred-texts.com/egy | 127+ pages | English translations (19th/20th c.) | 403 to bots | Translation layers |
| attalus.org/egypt | 200+ texts | English translations (Late/Ptolemaic) | Accessible | Better than expected |
| pyramidtextsonline.com | Dozens of PDFs | Links to external PDFs | 403 to bots | PDFs on Archive.org etc. |
| EEF SourceTexts | ~60 URLs | Links to scanned publications | Accessible | Last updated Oct 2013, link rot expected |
| EEF Texts Guide | 100+ entries | Links to translations/transcriptions | Accessible | Last updated Sep 2013 |
| Internet Archive | Thousands | Pre-1930 scanned PDFs | API available | Public domain |
| AWOL | Large URL corpus | Links to open-access resources | Accessible | Heterogeneous |

### External Reference APIs

| Source | Scale | Access | Notes |
|--------|-------|--------|-------|
| Trismegistos | 966,921 entries | TexRelations Matcher API (open); search requires subscription since Jan 2020 | ID cross-referencing viable; bulk discovery may need institutional access |
| TLA LexFCS API | Lemmata only | Open, SRU protocol | Searches lemmata, not full texts. Max 250 records/request. Corpus v19. |

---

## 12. Operations

### 12.1 Development Environment

**Docker Compose dev profile:**

The `docker-compose.yml` includes a `dev` profile for local development that stands up only infrastructure services. Application code runs natively on the host.

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: aegyptus
      POSTGRES_USER: aegyptus
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    profiles: [dev, full]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data
    profiles: [dev, full]

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    profiles: [full]  # Not needed until Phase 2 crawler

volumes:
  pgdata:
  miniodata:
```

- `docker compose --profile dev up` -- Postgres + MinIO only (Phase 1 development)
- `docker compose --profile full up` -- All infrastructure including Redis (Phase 2+)
- Application services (importers, API, crawler) run as plain Python during development: `python -m aegyptus.importers.oraec`

**Bootstrap script (`scripts/bootstrap.sh`):**

One command to go from fresh clone to ready-to-import:

1. Create Python venv and install all dependencies from `pyproject.toml`
2. Clone upstream repos into `data/upstream/`:
   - `oraec/corpus_raw_data`
   - `simondschweitzer/aes`
   - `oraec/formerly-mdc-now_unicode`
   - `oraec/recommendations-encoding-hieroglyphs`
3. Download Nederhof hierojax texts
4. Download TLA HF datasets via `huggingface_hub` Python API
5. Download RAMSES archive from Zenodo
6. Start Docker dev profile
7. Run Alembic migrations against local Postgres
8. Print summary of data sizes and readiness

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_URL` | `postgresql://aegyptus:dev@localhost:5432/aegyptus` | PostgreSQL connection string |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `DATA_DIR` | `./data/upstream` | Path to cloned upstream repos |

### 12.2 Backup and Export

**Database backup:** `pg_dump` on a daily cron. Compressed dumps stored in MinIO with date-stamped keys (`backups/aegyptus_2026-04-15.sql.gz`). Retain 30 days.

**Portable corpus export:** `scripts/export_corpus.py` dumps the full corpus to a portable format:

- One JSONL file per table (`texts.jsonl.gz`, `sentences.jsonl.gz`, `concordance.jsonl.gz`, `aliases.jsonl.gz`, `representation_layers.jsonl.gz`)
- Includes a `manifest.json` with row counts, export date, corpus version, and schema version
- Stored in MinIO under `exports/aegyptus_v{version}_{date}/`
- Anyone can reconstruct the full database from the export using `scripts/import_corpus.py`

This is both backup and replication. The export is the canonical distribution format.

### 12.3 Corpus Versioning

Tag-based snapshots after each major import phase or significant corpus change.

**Version format:** `v{major}.{minor}.{patch}-{label}`

- `v0.1.0-phase1` -- after Phase 1 foundation imports complete
- `v0.2.0-phase2` -- after Phase 2 web pipeline first batch
- `v0.3.0-phase3` -- after Phase 3 ML processing integrated
- Patch versions for incremental imports or corrections

**What gets tagged:**

| Artifact | Location | Purpose |
|----------|----------|---------|
| Git tag | Repository | Code state at time of snapshot |
| `corpus_versions` DB row | PostgreSQL | Row counts, date, description, data quality metrics |
| Export archive | MinIO | Full portable corpus snapshot |

**`corpus_versions` table:**

```sql
CREATE TABLE corpus_versions (
  id            SERIAL PRIMARY KEY,
  version_tag   TEXT UNIQUE NOT NULL,  -- 'v0.1.0-phase1'
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  description   TEXT,
  text_count    INTEGER,
  sentence_count INTEGER,
  layer_count   INTEGER,
  concordance_count INTEGER,
  alias_count   INTEGER,
  export_key    TEXT,                  -- MinIO key for the export archive
  metadata      JSONB                 -- additional metrics, data quality stats
);
```

### 12.4 Contribution Model

**Current status:** single maintainer. No external contributors, no PR workflow, no CLA.

**Practical contribution path:** Someone sends data (file, spreadsheet, PDF) to the maintainer, who ingests it via the ad-hoc CLI (`aegyptus ingest`). The CLI handles record creation, layer insertion, and provenance tagging.

**Future:** If the project opens to contributors, the infrastructure already supports it:

- Ad-hoc ingestion CLI for manual contributions
- Entity resolution for deduplication
- Provenance tracking via `source` and `source_detail` fields
- `confidence: 'unreviewed'` flag for unvalidated contributions

Contributor documentation (INT-2) is deprioritized but remains in the Phase 4 task list as a placeholder.

---

## Appendix A: External Repository Reference

| Repository | URL | Role in Aegyptus | License | Verified |
|------------|-----|-----------------|---------|----------|
| ORAEC corpus_raw_data | github.com/oraec/corpus_raw_data | Fork as schema skeleton; day-one data import | CC-BY-SA-4.0 | Yes |
| ORAEC MdC-to-Unicode | github.com/oraec/formerly-mdc-now_unicode | Import Unicode hieroglyphic texts + mapping CSV | CC | Yes |
| ORAEC encoding recs | github.com/oraec/recommendations-encoding-hieroglyphs | Adopt as Unicode standard for all hieroglyphic data | None stated | Yes |
| AES | github.com/simondschweitzer/aes | Base data model; 11,000+ text import | CC-BY-SA-4.0 | Yes |
| Nederhof hierojax | nederhof.github.io/hierojax/texts | Import 118 Unicode hieroglyphic texts | GPL-3.0 | Yes |
| TLA HF datasets | huggingface.co/thesaurus-linguae-aegyptiae | Highest-quality bulk import (3 datasets, ~29.7k sentences) | CC-BY-SA-4.0 | Yes |
| RAMSES corpus | gitlab.cnam.fr/rosmorse/ramses-trl + Zenodo 4954597 | Late Egyptian transliteration data | CC BY-NC-SA / CC BY 4.0 | Yes (GitLab slow) |
| TranslitModels | github.com/MaReTEgyptologists/TranslitModels | Language models for OCR post-correction | CC BY 4.0 | Yes |
| papyri/idp.data | github.com/papyri/idp.data | Papyrological data in EpiDoc XML | CC BY 3.0 | Yes |
| EgyptianHieroglyphicText | github.com/rfuentesfe/EgyptianHieroglyphicText | (Deferred) Training data: 13,729 glyph images, 310 classes | NO LICENSE | Yes |
| Google Fabricius | github.com/googleartsculture/workbench | (Deferred) Archived Nov 2025. Frontend only, no ML models. | Apache 2.0 | Yes -- archived |
| Ancient-Language-Decipherer | github.com/JamesPiggott/Ancient-Language-Decipherer | Reference for dataset catalogs and benchmarks | NO LICENSE | Yes |
| Nederhof hocr | github.com/nederhof/hocr | (Deferred) Hieroglyphic OCR to Unicode -- potential glyph pipeline starter | Unknown | Not yet verified |

---

## Appendix B: Data Model Schema (Draft)

PostgreSQL DDL for core tables:

```sql
-- ============================================================
-- Core corpus tables
-- ============================================================

CREATE TABLE texts (
  canonical_id     TEXT PRIMARY KEY,  -- Format: aeg_{source}_{source_id}
  conventional_name TEXT,
  script_type      TEXT CHECK (script_type IN ('hieroglyphic','hieratic','demotic','coptic','greek','multiple')),
  date_earliest    INTEGER,     -- negative = BCE
  date_latest      INTEGER,
  period_label     TEXT,
  findspot         TEXT,
  current_location TEXT,
  text_type        TEXT,
  completeness     TEXT CHECK (completeness IN ('complete','fragmentary','damaged','unknown')),
  shelfmarks       TEXT[],
  metadata         JSONB,       -- extensible metadata
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sentences (
  id               SERIAL PRIMARY KEY,
  canonical_id     TEXT NOT NULL REFERENCES texts(canonical_id),
  sequence_num     INTEGER,          -- position within the text (NULL if unknown)
  transliteration  TEXT,             -- sentence-level transliteration (Unicode)
  translation      JSONB,            -- {"de": "...", "en": "...", "fr": "..."}
  tokens           JSONB,            -- [{written_form, lemma_id, pos, hiero, morphology, ...}]
  source           TEXT,             -- 'oraec' | 'aes' | 'tla_hf' | 'ad_hoc' | ...
  source_id        TEXT,             -- original sentence ID from source system
  source_detail    JSONB,            -- {dataset_version, editor, subcorpus, ...}
  confidence       TEXT DEFAULT 'verified',  -- 'verified' | 'unreviewed' | 'ml_draft'
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE concordance (
  id               SERIAL PRIMARY KEY,
  canonical_id     TEXT NOT NULL REFERENCES texts(canonical_id),
  external_system  TEXT NOT NULL,  -- 'tla' | 'trismegistos' | 'oraec' | 'aes' | 'ramses' | 'wikidata' | 'karnak' | 'vega' | ...
  external_id      TEXT NOT NULL,
  relationship     TEXT DEFAULT 'exact_match',  -- exact_match | part_of | version_of | parallel_to
  UNIQUE (external_system, external_id, canonical_id)
  -- Note: one external_id CAN map to multiple canonical_ids (e.g., TLA recto+verso -> two texts)
  -- Lookups by external_id return a list, not a single row
);

CREATE TABLE aliases (
  id               SERIAL PRIMARY KEY,
  canonical_id     TEXT NOT NULL REFERENCES texts(canonical_id),
  alias_text       TEXT NOT NULL,
  alias_normalized TEXT NOT NULL,  -- lowercased, stripped, for matching
  alias_type       TEXT NOT NULL,  -- 'conventional_name' | 'shelfmark' | 'abbreviation' | 'foreign_title'
  confidence       TEXT DEFAULT 'auto',  -- 'auto' | 'curated' | 'fuzzy'
  UNIQUE (alias_text, canonical_id)
);

CREATE TABLE representation_layers (
  id               SERIAL PRIMARY KEY,
  canonical_id     TEXT NOT NULL REFERENCES texts(canonical_id),
  layer_type       TEXT NOT NULL,  -- 'photograph' | 'hieroglyphic' | 'transliteration' | 'lemmatization' | 'translation' | 'bibliography'
  content          JSONB,         -- layer-specific structured content
  language         TEXT,           -- for translations: 'de' | 'en' | 'fr' | 'ar' | ...
  source           TEXT,           -- 'oraec' | 'tla_hf' | 'web_crawler' | 'ml_draft' | 'ad_hoc' | ...
  source_detail    JSONB,         -- {url, publication, translator, year, model_version, ...}
  confidence       TEXT DEFAULT 'verified',  -- 'verified' | 'unreviewed' | 'ml_draft'
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Pipeline tables
-- ============================================================

CREATE TABLE crawl_queue (
  id               SERIAL PRIMARY KEY,
  url              TEXT UNIQUE NOT NULL,
  domain           TEXT NOT NULL,
  content_type_hint TEXT,
  status           TEXT DEFAULT 'pending',  -- pending | fetched | processed | failed | blocked
  fetched_at       TIMESTAMPTZ,
  object_store_key TEXT,
  metadata         JSONB
);

CREATE TABLE gaps (
  id               SERIAL PRIMARY KEY,
  canonical_id     TEXT REFERENCES texts(canonical_id),  -- NULL for not-yet-imported texts
  external_system  TEXT NOT NULL,
  external_id      TEXT NOT NULL,
  gap_type         TEXT NOT NULL,  -- 'not_imported' | 'no_transcription' | 'no_translation' | 'orphan' | ...
  priority         TEXT NOT NULL,  -- 'P0' | 'P1' | 'P2' | 'P3'
  recommended_action TEXT,
  status           TEXT DEFAULT 'open',
  assigned_to      TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Operations tables
-- ============================================================

CREATE TABLE corpus_versions (
  id               SERIAL PRIMARY KEY,
  version_tag      TEXT UNIQUE NOT NULL,  -- 'v0.1.0-phase1'
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  description      TEXT,
  text_count       INTEGER,
  sentence_count   INTEGER,
  layer_count      INTEGER,
  concordance_count INTEGER,
  alias_count      INTEGER,
  export_key       TEXT,                  -- MinIO key for the export archive
  metadata         JSONB                 -- additional metrics, data quality stats
);

-- ============================================================
-- Indexes
-- ============================================================

-- Concordance lookups (both directions)
CREATE INDEX idx_concordance_canonical ON concordance(canonical_id);
CREATE INDEX idx_concordance_external ON concordance(external_system, external_id);

-- Sentence queries
CREATE INDEX idx_sentences_canonical ON sentences(canonical_id);
CREATE INDEX idx_sentences_source ON sentences(source);
CREATE INDEX idx_sentences_confidence ON sentences(confidence);
CREATE INDEX idx_sentences_tokens ON sentences USING GIN (tokens);  -- enables JSONB queries into token data

-- Alias matching
CREATE INDEX idx_aliases_normalized ON aliases(alias_normalized);
CREATE INDEX idx_aliases_canonical ON aliases(canonical_id);

-- Representation layer queries
CREATE INDEX idx_layers_canonical ON representation_layers(canonical_id);
CREATE INDEX idx_layers_type ON representation_layers(layer_type);
CREATE INDEX idx_layers_language ON representation_layers(language);

-- Text filtering
CREATE INDEX idx_texts_script ON texts(script_type);
CREATE INDEX idx_texts_period ON texts(period_label);
CREATE INDEX idx_texts_type ON texts(text_type);

-- Gap tracker
CREATE INDEX idx_gaps_priority ON gaps(priority, status);
CREATE INDEX idx_gaps_canonical ON gaps(canonical_id);
```
