# Aegyptus Importers Guide

Eleven structured data importers feed the central store, plus one concordance enricher and a manual ingest tool. Import order matters for the foundational sources; later importers are independent.

## Import Order

```
1.  oraec               — backbone, establishes TLA base32 ID space
2.  aes                 — attaches sentences to ORAEC records via shared TLA IDs
3.  tla-hf              — TLA Hugging Face datasets (independent after ORAEC)
4.  nederhof            — HieroJax hieroglyphic layers
5.  ramses              — Late Egyptian transliterations
6.  papyri-info         — EpiDoc XML (Coptic/Demotic/Egyptian filter)
7.  aed-dict            — AED lemma dictionary (validates lemmata table)
8.  aed-tei             — AED-TEI XML corpus (independent canonical IDs)
9.  coptic-scriptorium  — CoNLL-U Coptic texts with English translations
10. nederhof-philologeg — PhilologEg St Andrews corpus (from JAR)
11. met-api             — Metropolitan Museum API (rate-limited, partial)
12. trismegistos        — Concordance enrichment (run last, ~3hrs, 1 req/s)
```

All importers are **idempotent**. Re-running produces no duplicates.

Run via CLI (after `./scripts/bootstrap.sh`, which fetches the upstream data):
```bash
aegyptus import --source all   # every importer above, in this order
aegyptus import --source <name>
aegyptus import --status       # counts per source
```

Or directly:
```bash
python -m importers.<name>
```

---

## ORAEC — Open Richly Annotated Cuneiform Corpus Egyptian

**Module:** `importers/oraec/`
**Source:** https://github.com/oraec/corpus_raw_data (13,026 JSON files + mapping CSVs)
**Creator:** ORAEC Project
**License:** CC BY-SA 4.0
**Canonical ID prefix:** `aeg_oraec_{n}`

The structural backbone. Each JSON file is one text record. Provides the TLA base32 ID space that connects ORAEC, AES, and AED-TEI via concordance.

**Results:** 13,026 texts · 101,796 sentences · transliteration, hieroglyphic, translation, lemmatization layers · concordance to TLA, Trismegistos, Wikidata, Karnak

**Run:**
```bash
aegyptus import --source oraec
# ENV: ORAEC_DATA_DIR (default: data/upstream/oraec_corpus_raw_data)
```

---

## AES — Ancient Egyptian Sentences

**Module:** `importers/aes/`
**Source:** https://github.com/simondschweitzer/aes (14 subcorpus JSON files)
**Creator:** Simon D. Schweitzer
**License:** CC BY-SA 4.0
**Canonical ID prefix:** `aeg_aes_{id}`

Sentence-level companion to ORAEC. Sentences link to parent ORAEC records via shared TLA base32 IDs through the concordance table.

**Results:** 101,796 sentences · German and English translations · word-level token data

**Run:**
```bash
aegyptus import --source aes
# Must run after oraec
```

---

## TLA Hugging Face

**Module:** `importers/tla_hf/`
**Source:** https://huggingface.co/thesaurus-linguae-aegyptiae (3 datasets)
**Creator:** Thesaurus Linguae Aegyptiae Project, BBAW
**License:** CC BY-SA 4.0
**Canonical ID prefix:** `aeg_tla_hf_{id}`

Three TLA datasets: Earlier Egyptian (12,773 sentences), Late Egyptian (3,606), Demotic (13,383). Premium rows are `confidence: 'verified'`; non-premium are `confidence: 'unreviewed'`.

**Results:** 29,762 text records · 29,762 sentences · TLA entity metadata (dates, locations, object types, origin places)

**Run:**
```bash
aegyptus import --source tla-hf
```

---

## Nederhof HieroJax

**Module:** `importers/nederhof/`
**Source:** https://nederhof.github.io/hierojax/texts
**Creator:** Mark-Jan Nederhof, University of St Andrews
**License:** GPL-3.0 (tooling); texts public domain
**Canonical ID prefix:** `aeg_nederhof_{n}`

HTML-based hieroglyph viewer corpus. 120 texts with Unicode hieroglyphic representation layers. Primarily Urkunden IV texts and major inscriptions.

**Results:** 120 texts · hieroglyphic representation layers

**Run:**
```bash
aegyptus import --source nederhof
```

---

## Nederhof PhilologEg — St Andrews Corpus

**Module:** `importers/nederhof_philologeg/`
**Source:** `data/upstream/PhilologEg-0.5.14.jar` (corpus embedded in JAR)
**Creator:** Mark-Jan Nederhof, University of St Andrews
**License:** Academic use; contact author for redistribution
**Canonical ID prefix:** `aeg_nederhof_philologeg_{slug}`

PhilologEg is Aegyptus's direct scholarly predecessor: the same goal (unified machine-readable corpus of Egyptian texts), built as a desktop Java application over two decades. Nederhof solved the hieroglyph encoding problem first — his sign-to-Unicode mapping (`signunicode.xml`, 1,071 entries) is used verbatim by this importer.

The JAR contains the full St Andrews corpus as embedded XML and text files. No separate download needed — the importer reads directly from the JAR using Python's `zipfile`.

**What's in the JAR:**
- `corpus/texts/*.xml` — text manifests (94 texts)
- `corpus/resources/*Tr.txt` — transliteration + English translation in alternating pairs
- `corpus/resources/*Hi.xml` — hieroglyphic in RES encoding
- `data/fonts/signunicode.xml` — Gardiner sign → Unicode codepoint map
- `data/dict/` — dictionaries (gods, kings, names, places)

**Corpus highlights:** Shipwrecked Sailor · Westcar Papyrus · Instruction of Ptahhotep · Ebers Papyrus · Merneptah Stela · Dispute of a Man with his Ba · Autobiography of Ahmose son of Abana · Hatshepsut Punt expedition · Tuthmosis III Gebel Barkal stela · 45 Urkunden IV texts

**Results:** 94 texts · 5,934 sentences (100% with English translations, 100% with transliteration) · 53 hieroglyphic layers (RES→Unicode converted)

**Run:**
```bash
# Place JAR at data/upstream/PhilologEg-0.5.14.jar
aegyptus import --source nederhof-philologeg
# ENV: PHILOLOGEG_JAR (default: data/upstream/PhilologEg-0.5.14.jar)
```

**Note:** Aegyptus and PhilologEg are complementary, not competing. PhilologEg provides deep scholarly edition features — alignment, variant manuscripts, visual hieroglyph rendering. Aegyptus provides scale, federation, and a queryable database layer. The 94 PhilologEg texts are one source layer in a corpus of 77K+.

---

## RAMSES — Ramsès Late Egyptian Corpus

**Module:** `importers/ramses/`
**Source:** Zenodo DOI 10.5281/zenodo.4954597
**Creator:** Université de Liège
**License:** CC BY-NC-SA ⚠️ **Non-commercial restriction**
**Canonical ID prefix:** `aeg_ramses_{id}`

Late Egyptian transliteration data. Line-based MdC transliteration pairs.

**Results:** 71,263 sentences · Late Egyptian transliteration

⚠️ RAMSES data carries a non-commercial restriction. This is recorded in `source = 'ramses'` metadata. Downstream use must respect CC BY-NC-SA.

**Run:**
```bash
aegyptus import --source ramses
```

---

## papyri.info / DCLP / IDP

**Module:** `importers/papyri_info/`
**Source:** https://github.com/papyri/idp.data (EpiDoc XML)
**Creator:** Papyri.info Consortium
**License:** CC BY 3.0
**Canonical ID prefix:** `aeg_papyri_{id}`

EpiDoc XML corpus. Primarily Greek papyri; Egyptian-language content (Coptic, Demotic, hieratic) is filtered using keyword markers and a force-include list of known TM IDs.

**Force-included TM IDs** (Nag Hammadi codices + Hermetic fragments):
`107741–107753, 63986, 66868, 64247, 108000, 87192, 108146`

**Results:** ~19,207 text records · EpiDoc transcriptions · Trismegistos concordance links · Nag Hammadi metadata shells (full Coptic text provided by Coptic Scriptorium)

**Run:**
```bash
aegyptus import --source papyri-info
# ENV: IDP_DATA_DIR (default: data/upstream/idp.data)
# Clone first: git clone --depth 1 https://github.com/papyri/idp.data data/upstream/idp.data
```

---

## AED Lemma Dictionary

**Module:** `importers/aed_dict/`
**Source:** `data/upstream/aed_tei/files/dictionary.xml` (embedded in AED-TEI repo)
**Creator:** Simon D. Schweitzer, BBAW
**License:** CC BY-SA 4.0

Populates the `lemmata` table. The AED GitHub repo (`simondschweitzer/aed`) is a placeholder — the actual dictionary is in the AED-TEI repo. Run after AED-TEI is cloned.

**Results:** 35,052 lemma entries · German + English translations · part of speech · bibliography · root cross-references

**Run:**
```bash
# Requires AED-TEI cloned first (see aed-tei below)
aegyptus import --source aed-dict
# ENV: AED_TEI_DIR (default: data/upstream/aed_tei)
```

---

## AED-TEI Corpus

**Module:** `importers/aed_tei/`
**Source:** https://github.com/simondschweitzer/aed-tei (646MB, 55,800 XML files)
**Creator:** Simon D. Schweitzer, BBAW Strukturen und Transformationen project (January 2018 snapshot)
**License:** CC BY-SA 4.0
**Canonical ID prefix:** `aeg_aedtei_{tla_base32_id}`

TEI XML corpus. Each text has up to four files: base metadata (`.xml`), sentence translations (`_st.xml`), word-level translations (`_wt.xml`), hieroglyphic encoding (`_hiero.xml`).

**Overlaps with ORAEC/AES** (same Berlin project lineage, same TLA IDs) — per design, AED-TEI records get their own canonical IDs and are linked via concordance. The new data is the hieroglyphic layer and word-level token annotations not present in the ORAEC dump.

**Results:** 13,748 texts · 98,265 sentences (German translations) · 2,802 hieroglyphic layers · 27,496 concordance links (tla + aed_tei) · 11,210 aliases

**Implementation notes:**
- `SENTENCE_BATCH_SIZE = 100` (JSONB token arrays hit PostgreSQL parameter limits at 500)
- Texts flush before sentences/concordance/layers (FK ordering)
- 202 XML parse errors skipped (~1.4% of files)

**Run:**
```bash
git clone --depth 1 https://github.com/simondschweitzer/aed-tei.git data/upstream/aed_tei
aegyptus import --source aed-tei
# ENV: AED_TEI_DIR (default: data/upstream/aed_tei)
```

---

## Coptic Scriptorium

**Module:** `importers/coptic_scriptorium/`
**Source:** https://github.com/CopticScriptorium/corpora (2.4GB, 1,694 CoNLL-U files)
**Creator:** Caroline T. Schroeder, Amir Zeldes, and contributors
**License:** CC BY 4.0 (most corpora; check individual `meta.json`)
**Canonical ID prefix:** `aeg_copcorp_{corpus}_{slug}`

70+ corpus sections in CoNLL-U format. Each `# newdoc id` comment creates one text record. Each sentence has Coptic text (`# text`), English translation (`# text_en`), and token-level annotation (lemma, UPOS, XPOS, morphological features, `Orig`, `OrigLang`, `Entity` from MISC field).

**Key content:** Nag Hammadi texts (Gospel of Thomas, Asclepius 21–29, Discourse on the 8th and 9th, Trimorphic Protennoia) · Shenoute of Atripe (extensive) · Sahidic Bible (OT + NT complete) · Bohairic texts · Apophthegmata Patrum · Gospel of Thomas

**Results:** 1,467 texts · 51,474 sentences · 51,469 with English translations (99.99%) · token-level annotation throughout

**Run:**
```bash
git clone --depth 1 https://github.com/CopticScriptorium/corpora.git data/upstream/coptic_scriptorium
aegyptus import --source coptic-scriptorium
# ENV: COPTIC_SCRIPTORIUM_DIR (default: data/upstream/coptic_scriptorium)
```

---

## Metropolitan Museum of Art

**Module:** `importers/met_api/`
**Source:** https://collectionapi.metmuseum.org/public/collection/v1/
**License:** CC0 (public domain)
**Canonical ID prefix:** `aeg_met_{objectID}`

Fetches Egyptian department (department ID 10) objects from the Met's public API. Objects are imported as `completeness = 'metadata_only'` records — provenance, dynasty, medium, dimensions, accession numbers. Some objects have inscription text.

**Status:** Partial — Met API aggressively rate-limits (~100 requests/session). 248 objects imported from cached responses.

**Recommended path to full import:** Use the [CSV bulk download](https://github.com/metmuseum/openaccess) (`MetObjects.csv`, ~500K objects). Filter to `Department = "Egyptian Art"`. No API rate limits.

**Results:** 248 texts (metadata_only) · 248 concordance links · 248 accession number aliases

**Run:**
```bash
# Requires User-Agent header (already set in importer)
aegyptus import --source met-api
# ENV: MET_CACHE_DIR (default: data/upstream/met_api)
```

---

## Trismegistos TexRelations Enricher

**Module:** `importers/trismegistos/`
**Source:** https://www.trismegistos.org/dataservices/texrelations/
**Creator:** Trismegistos Project, KU Leuven
**License:** CC BY-SA 3.0
**Rate limit:** 1 req/sec (polite)

Not a text importer — a concordance enricher. Queries the TexRelations Matcher API for every existing TM ID in the corpus and inserts cross-references to partner projects. Run last.

**External systems discovered:** British Museum (10,339) · DDbDP (4,630) · HGV (3,566) · DCLP (2,376) · ONB (838) · MertensPack (544) · TBP (518) · Louvre (444) · Kyprianos · Pinakes · Penn Museum · APIS · and 20+ more

**Results:** ~27,000+ new concordance links · 30+ new external systems

**Run:**
```bash
aegyptus import --source trismegistos
# Long-running: ~10,000 TM IDs at 1/sec ≈ 3 hours
# Cache: data/upstream/tm_texrelations/{tm_id}.json (resumable)
# ENV: TM_CACHE_DIR (default: data/upstream/tm_texrelations)
```

---

## Manual Ingest Tool

**Script:** `scripts/ingest_manual.py`

For texts not covered by any importer. Reads a structured JSON file (or directory of JSON files) and inserts into texts, sentences, concordance, and aliases tables.

**JSON format:**
```json
{
  "canonical_id": "aeg_manual_my_text",
  "conventional_name": "My Text Name",
  "script_type": "hieroglyphic",
  "date_earliest": -1550,
  "date_latest": -1070,
  "period_label": "New Kingdom",
  "completeness": "complete",
  "shelfmarks": ["BM EA 10470"],
  "source_corpus": ["manual"],
  "extra_metadata": {"bridge_text": true},
  "concordance": [
    {"external_system": "trismegistos", "external_id": "12345"}
  ],
  "aliases": ["Alternate Name", "BM EA 10470"],
  "sentences": [
    {
      "sequence_num": 1,
      "transliteration": "jw=f Hr sDm",
      "translation": {"en": "He is listening."},
      "source_detail": {"line": "1", "section": "opening"}
    }
  ]
}
```

**Run:**
```bash
python scripts/ingest_manual.py data/manual/my_text.json
python scripts/ingest_manual.py data/manual/           # all files in dir
```

**Existing manual texts:**
- `data/manual/shabaka_stone.json` — Memphite Theology / Shabaka Stone (BM EA 498), 18 sentences, Breasted 1901
- `data/manual/corpus_hermeticum_1.json` — Poimandres / Corpus Hermeticum I, 21 sentences, Scott 1924

---

## Idempotency

All importers are safe to re-run:

| Table | Dedup mechanism |
|-------|----------------|
| `texts` | `ON CONFLICT DO NOTHING` on `canonical_id` |
| `sentences` | Pre-load existing `source_id` set; skip duplicates before insert |
| `concordance` | `ON CONFLICT DO NOTHING` on `(external_system, external_id, canonical_id)` |
| `aliases` | `ON CONFLICT DO NOTHING` on `(alias_text, canonical_id)` |
| `representation_layers` | Pre-load existing `canonical_id` set per source; skip duplicates |
| `lemmata` | `ON CONFLICT DO NOTHING` on `id` |

To force a clean re-import of one source, truncate its records by `canonical_id` prefix, then re-run.
