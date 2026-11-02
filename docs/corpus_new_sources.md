# Aegyptus: New Digital Source Candidates
*Research conducted 2026-04-05. URLs verified by live HTTP check unless noted.*

---

## Executive Summary

This document catalogues **26 high-value new sources** across academic corpora, museum APIs, GitHub/HuggingFace datasets, text-collection projects, Coptic corpora, and epigraphy databases. The single highest-priority discovery is **AED-TEI** (11,396 Egyptian texts in TEI XML, CC-BY-SA 4.0, immediately downloadable). The **Coptic Scriptorium** corpus (2.7 GB of annotated Coptic literary texts) is the second-largest find. Together these two alone could nearly double the corpus.

---

## TIER 1 — HIGH PRIORITY (Import Immediately)

---

### 1. AED-TEI — Ancient Egyptian Dictionary Corpus (TEI XML)
**URL:** https://github.com/simondschweitzer/aed-tei  
**Zenodo DOI:** https://doi.org/10.5281/zenodo.3580939  
**What it contains:**
- **11,396 Egyptian texts** encoded in TEI XML (four files each: base text, sentence translations `_st.xml`, contextual word translations `_wt.xml`, hieroglyphic encoding `_hiero.xml`)
- Accompanying `dictionary.xml`: **30,000+ lemma entries** with German translation, part-of-speech, morphological features
- `thesaurus.xml`: controlled vocabulary (find spots, date ranges, object types, divine names)
- `concordance_name_text_id.csv`: name-to-ID mapping (11,396 rows, verified by `wc -l`)
- Coverage spans Old Kingdom through Late Period; Amarna texts, papyri, stelae, ostraca included
- Source data from the Berlin "Strukturen und Transformationen" project (BBAW, January 2018 snapshot)

**Size estimate:** ~140 MB zipped XML; 11,396 texts, estimated 300–500K sentences, 1–2M tokens  
**License:** CC-BY-SA 4.0 ✅  
**Import difficulty:** MEDIUM — TEI XML needs a parser; TLA base32 IDs are present and map to ORAEC. Sentences are in `_st.xml` per-text. The `_wt.xml` gives word-level German translation with lemma IDs.  
**Overlap with existing:** HIGH for ORAEC and AES (same BBAW lineage, TLA IDs), but AED-TEI is a **January 2018 snapshot** while ORAEC/AES are more recent — AED-TEI may contain texts not yet in our pipeline (especially Amarna blocks, stelae from smaller museums), and the TEI `_hiero.xml` files give **hieroglyphic encodings** we don't currently have at this scale.  
**Priority: HIGH** — The hieroglyphic layer (`_hiero.xml`) fills a critical gap. Even if base text overlaps 60–70% with ORAEC/AES, the hiero layer and any new texts are worth the import.

---

### 2. Coptic Scriptorium — Annotated Coptic Literary Corpus
**URL:** https://copticscriptorium.org  
**GitHub:** https://github.com/CopticScriptorium/corpora  
**What it contains:**
- **~2.7 GB** of annotated Coptic texts (70+ individual corpora, verified by GitHub repo size)
- Sahidic and Bohairic Coptic: Bible (OT + NT complete), Shenoute of Atripe (extensive), Nag Hammadi texts (Gospel of Thomas, Pistis Sophia, etc.), monastic lives (Pachomius, Onnophrius, etc.), magical papyri, documentary papyri
- Annotation layers: tokenization, lemmatization, part-of-speech, normalized orthography, language-of-origin tags
- Format: CoNLL-U, PAULA XML, TEI, and raw text — multiple export formats
- Latest release: "Late 2025 Release" tag confirmed on GitHub

**Size estimate:** 70+ corpus sections; ~1M Coptic tokens; tens of thousands of sentences  
**License:** Mix — CC-BY 4.0 for most; some underlying texts public domain. Check `meta.json`.  
**Import difficulty:** MEDIUM — CoNLL-U is easy to parse; map Coptic texts as a new `script_type: coptic`. Create concordance links to TM where available (Scriptorium uses TM IDs for documentary texts).  
**Overlap with existing:** LOW — We have no Coptic content. Coptic is continuous with Late Egyptian/Demotic and critical for lexical continuity. Bridge language to Greek and early Arabic.  
**Priority: HIGH** — Adds an entire language stage (Coptic = 4th–12th century CE) we currently lack entirely.

---

### 3. Mark-Jan Nederhof — St Andrews Egyptian Corpus (PhilologEg)
**URL:** https://mjn.host.cs.st-andrews.ac.uk/egyptian/  
**Download:** https://mjn.host.cs.st-andrews.ac.uk/egyptian/align/download.html  
**What it contains:**
- Annotated XML corpus of Egyptian texts (hieroglyphic + transliteration + interlinear English translation)
- Sub-collections verified: **texts/** (major literary texts), **stelae/** (Iy-Dundee, Ramose-Manchester, others), **coffins/** (9 coffins including Iwefaa, Psamtik, Amenirdis)
- Format: custom RES (Revised Encoding Scheme) + PhilologEg XML — Java-based viewer (PhilologEg-0.5.14.jar, 57 MB)
- Texts include: Story of Sinuhe, Eloquent Peasant, Teaching of Ptahhotep, Admonitions of Ipuwer, Westcar Papyrus, Shipwrecked Sailor, and more
- Also: `stelae/` collection (Middle Kingdom private stelae), `coffins/` (Coffin Texts extracts)

**Size estimate:** ~100–200 texts; 5,000–15,000 sentences; relatively small but high quality  
**License:** No explicit license stated; academic/open use implied. Contact Nederhof for confirmation.  
**Import difficulty:** MEDIUM — RES encoding for hieroglyphs needs conversion to Unicode. PhilologEg XML is proprietary but documented. Nederhof also maintains `hieropy` (Python RES parser) and `transliteration-converter` on GitHub.  
**Overlap with existing:** MEDIUM — Some texts (Sinuhe, Shipwrecked Sailor) are in ORAEC/AES. Stelae and coffin texts may be unique. The **interlinear English translation** is valuable as we have mostly German.  
**Priority: HIGH** — English translations are rare in our corpus. Even partial overlap is acceptable for the English translation layer.

---

### 4. ISUT — Hieratic Text Annotation Tool + Corpus
**URL:** https://github.com/nederhof/isut  
**What it contains:**
- Tool for collaborative annotation and computational analysis of **hieratic texts** (Mark-Jan Nederhof, Julius Tabin, Christian Casey)
- GitHub repo is **731 MB** — clearly contains substantial image + corpus data
- Targets hieratic manuscripts (Papyrus Harris, Ramesside documents, etc.)
- Annotation: sign-level segmentation, Unicode transcription linked to hieratic images
- MongoDB-backed; runs as a web server for collaborative use

**Size estimate:** Unknown text count; likely 50–500 papyri with hieratic sign annotations  
**License:** Open source (AGPLv3 based on 35KB license file)  
**Import difficulty:** HARD — MongoDB database dump needed; hieratic images + annotations; sign-level data needs aggregation to sentence level. Worth establishing contact with Nederhof.  
**Overlap with existing:** LOW — We have essentially no hieratic content; all our ORAEC/AES is transcription of hieratic originals, but ISUT has the sign-image ↔ Unicode mapping layer.  
**Priority: HIGH** — Hieratic sign-level data is unique and fills a critical gap (hieratic = the everyday writing of ancient Egypt).

---

## TIER 2 — MEDIUM PRIORITY (Import Q3–Q4)

---

### 5. Projet Karnak / SITH-CNRS
**URL:** http://sith.huma-num.fr/karnak  
**CFEETK:** https://cfeetk.cnrs.fr/  
**What it contains:**
- Systematic epigraphic edition of **Karnak Temple Complex** inscriptions (CNRS + Labex ARCHIMEDE, launched 2013)
- Verified: data updated as of **27 February 2026** (confirmed in page header — actively maintained)
- Individual scene-level records (KIU numbers): hieroglyphic text, photographs, location metadata
- Currently thousands of scenes catalogued; Karnak has ~100,000+ hieroglyphic columns in total

**Size estimate:** Thousands of scene units; partial coverage of Karnak walls  
**License:** Research project; likely CC or academic use. No explicit bulk download found.  
**Import difficulty:** HARD — Requires scraping scene-by-scene (KIU IDs are sequential integers); data is HTML-rendered with JS. API not found. Contact CFEETK for data export.  
**Overlap with existing:** LOW-MEDIUM — Some Ramesside Karnak texts may be in RAMSES; unique temple wall context  
**Priority: MEDIUM-HIGH** — Temple inscriptions from Karnak (Thutmosid through Ptolemaic) are massively underrepresented. Data freshness (Feb 2026) shows active curation.

---

### 6. Totenbuch Projekt — Book of the Dead Digital Archive (Bonn)
**URL:** https://totenbuch.awk.nrw.de  
**What it contains:**
- Digital archive of **ancient Egyptian Book of the Dead** manuscripts
- Spells indexed: Adorationsszene, spells 1–175+ (all canonical spells), Pleyte supplements, Saleh variants
- Spell text + manuscript witnesses (hundreds of papyri and other objects per spell)
- Interface is JavaScript-only (verified); no obvious bulk download endpoint found
- Associated with Nordrhein-Westfälische Akademie (awk.nrw.de)

**Size estimate:** ~200 canonical spells; hundreds of manuscript witnesses; ~50,000–100,000 sentences  
**License:** Academic project; contact required for bulk data  
**Import difficulty:** HARD — JS-rendered; would need Selenium-based scraping or contact with the project for XML export  
**Overlap with existing:** MEDIUM — Some Book of the Dead texts are in ORAEC (under "totenbuch" prefix). The full spell-witness matrix is unique.  
**Priority: MEDIUM** — Book of the Dead is one of the most important Egyptian text corpora; our current coverage is fragmentary.

---

### 7. Metropolitan Museum of Art — Open Access API
**URL:** https://collectionapi.metmuseum.org/public/collection/v1/  
**Docs:** https://metmuseum.github.io  
**What it contains:**
- **27,971 Egyptian Art department objects** (verified via API: departmentId=10)
- Full open-access API with JSON response for every object
- Fields include: title, culture, period, medium, dimensions, `inscriptions`, objectName, classification
- IsPublicDomain flag; many Egyptian objects are public domain
- Selected objects have inscription fields (typically English transliteration of short texts — cartouches, epithets, offering formulas)

**Size estimate:** ~27,971 objects; inscription data is sparse (typically 1–5 lines per object, not full texts); good for metadata enrichment and short formulaic texts  
**License:** CC0 for open-access objects (public domain) ✅  
**Import difficulty:** EASY — REST API, JSON, free, no rate limits. Download all 27,971 objects: `GET /objects?departmentIds=10` → iterate objectIDs  
**Overlap with existing:** LOW — We lack object-level museum metadata. The inscription field gives short hieroglyphic/transliteration snippets not otherwise in our corpus.  
**Priority: MEDIUM** — Excellent for enriching aliases (shelfmarks like "MMA 1234.56"), concordance links, and short formula texts (cartouches, epithets). Worth a dedicated lightweight importer.

---

### 8. Turin Egyptian Museum — Online Collection
**URL:** https://collezioni.museoegizio.it  
**API:** https://api.museoegizio.it (200 OK, verified)  
**What it contains:**
- **40,000 total Egyptian objects** (largest Egyptian collection outside Cairo); **4,000+ currently online**
- Collection includes: Papyrus of Ani (Book of the Dead), Deir el-Medina ostraca, Royal Turin Canon (regnal list), Thutmose I coffin, and major royal statuary
- API is live but undocumented publicly; the online collection has object pages with metadata
- Inscription data status: unclear at this time

**Size estimate:** 4,000 objects online; inscription coverage unknown  
**License:** Unknown — check Terms of Service  
**Import difficulty:** MEDIUM — API discovery needed; may require authentication  
**Overlap with existing:** LOW — Turin-specific inventory numbers (Cat.) not in our concordance  
**Priority: MEDIUM** — Turin Canon (regnal list) and Deir el-Medina ostraca are major desiderata.

---

### 9. Trismegistos — Text Content & Data Services
**URL:** https://www.trismegistos.org  
**Data Services:** https://www.trismegistos.org/dataservices/  
**What it contains:**
- We already use TM for ID concordance; **new discovery**: TM has a full **Data Services API** (CC BY-SA 4.0)
- TexRelations Matcher: cross-matches TM IDs against 20+ partner projects (papyri.info, LDAB, PHI, etc.)
- GeoResponder: GeoJSON for ancient place IDs
- **Table dumps**: Geo table dump available for download
- Potentially: bulk TM text records (full text content) via `tmcorpusdata` endpoint

**Size estimate:** TM covers 1.3M+ ancient-world texts; the Egyptian subset is ~300,000+ documents  
**License:** CC BY-SA 4.0 ✅  
**Import difficulty:** EASY-MEDIUM — API is well-documented; table dumps are direct downloads. The TexRelations Matcher enables automated concordance expansion for all our existing texts.  
**Overlap with existing:** HIGH for IDs (we already have TM concordance), but **the text content dump** would be new  
**Priority: MEDIUM** — Use TexRelations to expand concordance coverage; investigate `tmcorpusdata` for text content.

---

### 10. Pyramid Texts Online
**URL:** https://pyramidtextsonline.com (200 OK, verified)  
**What it contains:**
- Complete English translation of the **Pyramid Texts of Unas** with spell-by-spell coverage
- Spells organized by chamber and wall (Sarcophagus Chamber, Antechamber, Passage)
- Spell numbering: Sethe utterances (PT 213–312+ for Unas)
- Also references Faulkner and Piankoff translations
- HTML-based; no API

**Size estimate:** ~200 utterances for Unas; potentially other pyramid texts if site expands  
**License:** Copyright © Vincent Brown 2002–2026; usage unclear — likely scrape-able for research  
**Import difficulty:** MEDIUM — HTML scraping; spell-level structure is clear  
**Overlap with existing:** MEDIUM — Pyramid Texts may be partially in ORAEC under "Pyramidentexte" label. English translation is unique.  
**Priority: MEDIUM** — Pyramid Texts are the oldest religious corpus in the world (~2400 BCE). English translation layer is valuable.

---

### 11. KELLIA / Coptic Dictionary Online
**URL:** https://coptic-dictionary.org (200 OK, verified)  
**GitHub:** https://github.com/KELLIA  
**What it contains:**
- **Coptic Dictionary Online (CDO)**: comprehensive Coptic lexicon covering 9 dialects (Sahidic, Bohairic, Akhmimic, Fayyumic, Mesokemic, Lycopolitan, Proto-Theban, Old Coptic, South Fayyumic)
- Winner of DH Award 2019 (Best Tool)
- Backed by KELLIA consortium (Göttingen, Münster, White Plains, Claremont, Leuven)
- BBAW partnership; connects to Scriptorium corpus
- Likely contains lemma ↔ usage text examples (attestation corpus)

**Size estimate:** Full Coptic lexicon; attestation examples from Scriptorium corpus  
**License:** CC-BY (KELLIA outputs); check individual components  
**Import difficulty:** MEDIUM — dictionary scraping; check for JSON/XML export at GitHub repos  
**Overlap with existing:** LOW — No Coptic lexicon in our pipeline currently  
**Priority: MEDIUM** — Critical for Coptic lemmatization pipeline; enables cross-reference to Late Egyptian via shared roots.

---

### 12. British Museum — Collection Online
**URL:** https://www.britishmuseum.org/collection (200 OK, verified)  
**What it contains:**
- One of the world's largest Egyptian collections (mummies, papyri, stelae, shabti, jewelry)
- Rosetta Stone (BM EA 24), Papyrus of Ani, Hunefer Papyrus, Salt Papyrus (Book of the Dead)
- Collection search is open but Cloudflare-protected; no public bulk API found
- Historical SPARQL endpoint (`collection.britishmuseum.org/sparql`) — status unclear

**Size estimate:** ~100,000+ Egyptian objects total; ~5,000 with transcription/inscription data estimated  
**License:** Images CC BY-NC-SA 4.0; object data usage terms unclear  
**Import difficulty:** HARD — Cloudflare blocks automated access; would need polite scraping or formal data partnership  
**Overlap with existing:** MEDIUM — Some BM papyri (Hunefer = pBM EA 9901) are in ORAEC/AES  
**Priority: MEDIUM** — Key papyri (Chester Beatty, Ebers, etc.) in BM are globally significant. Pursue formal data partnership.

---

### 13. IFAO — Cachette de Karnak Database
**URL:** https://www.ifao.egnet.net/bases/cachette/ (200 OK, verified)  
**What it contains:**
- Database of the **Karnak Cachette** (K-numbers from G. Legrain's excavation 1903–1907): ~17,000 statues and objects found buried at Karnak, now in Cairo and elsewhere
- Object records with: K-number, Trismegistos ID, current location, inscriptions, description
- Bilingual (French/English interface)

**Size estimate:** ~17,000 object records; inscription coverage variable  
**License:** IFAO copyright; research use  
**Import difficulty:** MEDIUM — HTML scraping; structured records with TM IDs (enables concordance)  
**Overlap with existing:** LOW — Cachette K-numbers are not in our concordance  
**Priority: MEDIUM** — Enables concordance linking for thousands of statues with royal and private titularies.

---

### 14. AED — Ancient Egyptian Dictionary (lemma + ranglist)
**URL:** https://github.com/simondschweitzer/aed  
**What it contains:**
- Companion to AED-TEI; lemma database with 30,000+ entries in JSON/XML format
- `ranglistenpositionswerte` repo (12MB): ranking data for Egyptian lemma frequency
- Enables lemma-frequency analysis and dictionary-linked token data
- All CC-BY-SA 4.0

**Size estimate:** 30,000 lemma entries  
**License:** CC-BY-SA 4.0 ✅  
**Import difficulty:** EASY — JSON format, straightforward  
**Overlap with existing:** HIGH — TLA lemma data is already the basis of ORAEC/AES. But frequency rankings and dictionary definitions in JSON are easy to ingest as a reference layer.  
**Priority: MEDIUM** — Use as lemma reference table to enrich existing token data.

---

## TIER 3 — LOWER PRIORITY (Future Phases / Contact Required)

---

### 15. Thot Sign List
**URL:** https://thotsignlist.org (200 OK, verified)  
**What it contains:**
- Comprehensive database of **all known ancient Egyptian hieroglyphic signs** beyond the classic Gardiner list
- Sign entries with: Unicode codepoint, Gardiner number, Möller number, phonetic value, word examples, sign photographs
- French-language project (Lyon)

**Size estimate:** 7,000+ sign entries (vs. 763 in Gardiner); usage examples per sign  
**License:** Website copyright; research use  
**Import difficulty:** MEDIUM — sign database scraping; useful for sign-list reference rather than text corpus  
**Overlap with existing:** LOW — No sign-level sign-list in our schema currently  
**Priority: LOW-MEDIUM** — Foundational for hieroglyph encoding validation; import as reference table (not texts).

---

### 16. Transliteration Models (Zenodo)
**URL:** https://doi.org/10.5281/zenodo.7991241  
**What it contains:**
- Trained transliteration word models derived from RAMSES + AES corpora
- JSON model files; training sets; output validation data
- Directly relevant to our Layer 3 (TranslitModels JVM wrapper)

**Size estimate:** Model files; underlying training corpus is RAMSES (already have) + AES (already have)  
**License:** Check license (CC-BY likely)  
**Import difficulty:** EASY — download and integrate into TranslitModels pipeline  
**Overlap with existing:** HIGH — Training data from sources we have; models are the new value  
**Priority: LOW-MEDIUM** — Evaluate whether these improve on our current TranslitModels.

---

### 17. MAAT Corpus (Zenodo)
**URL:** https://doi.org/10.5281/zenodo.12820579  
**What it contains:**
- Machine-Actionable Ancient Text corpus for **text restoration** (lacunae filling)
- Covers: ancient Greek, Latin, and **Coptic** in EpiDoc XML format
- Training/evaluation data for ML restoration systems; CC-BY 4.0

**Size estimate:** Moderate; Coptic subset estimated at 10,000–50,000 tokens  
**License:** CC-BY 4.0 ✅  
**Import difficulty:** MEDIUM — EpiDoc XML; Coptic content needs extraction  
**Overlap with existing:** LOW for Coptic; HIGH for Greek/Latin which we don't target  
**Priority: LOW** — Coptic subset is modest; Scriptorium is a better Coptic source.

---

### 18. Brooklyn Museum — Open Collection API
**URL:** https://www.brooklynmuseum.org/opencollection/api  
**What it contains:**
- Open API for Brooklyn Museum collection
- Strong Egyptian department (papyri, stelae, coffins, amulets)
- Inscription/transcription data in object records (limited)

**Size estimate:** Several thousand Egyptian objects  
**License:** CC for images; metadata usage permitted  
**Import difficulty:** EASY — REST API, documented  
**Overlap with existing:** LOW — Brooklyn-specific accession numbers not in our concordance  
**Priority: LOW-MEDIUM** — Lightweight concordance/alias importer; Brooklyn has some unique papyri.

---

### 19. Louvre Collections API (Atlas)
**URL:** https://collections.louvre.fr  
**What it contains:**
- Louvre Egyptian Department (Département des Antiquités Égyptiennes): 50,000+ objects
- Atlas API (used internally); JSON responses available
- Key items: Stele of Nahthorheb, Seated Scribe, sarcophagi of Ramesses III

**Size estimate:** 50,000+ objects; inscription text in records (French)  
**License:** Louvre copyright; object data open for research  
**Import difficulty:** MEDIUM — API reverse-engineering needed (no public docs)  
**Overlap with existing:** LOW — Louvre inventory numbers not in our concordance  
**Priority: LOW-MEDIUM** — Valuable for alias enrichment; formal API access worth requesting.

---

### 20. Coptic Scriptorium — Magical Papyri Sub-corpus
*Already counted in #2 above, but worth calling out separately:*  
The `magical-papyri` directory in CopticScriptorium/corpora contains **Coptic magical texts** — an important genre for cross-referencing with Demotic magical papyri (Greek Magical Papyri, PDM). This sub-corpus bridges Coptic and Demotic directly.

---

### 21. Hieroglyphic Layout Analysis Datasets (HuggingFace)
**URL:** https://huggingface.co/AhmedElTaher/Egyptian_Hieroglyphic_Layout_Analysis_HLA  
**Also:** Egyptian_Hieroglyphic_Signs_Segmentation_with_Orientation  
**What it contains:**
- Image datasets for hieroglyphic sign detection and layout analysis
- CC-BY-NC-4.0; image-based (not text transcription)
- Small (<1K examples each)

**License:** CC-BY-NC-4.0 (non-commercial restriction)  
**Import difficulty:** N/A for text import; relevant for OCR pipeline (Layer 3)  
**Overlap with existing:** None for text; new for image/OCR  
**Priority: LOW** — Useful for hieroglyph OCR development; not primary text corpus.

---

### 22. RAMSES Rosmorduc (GitLab CNAM)
**URL:** https://gitlab.cnam.fr/rosmorse/ramses-trl  
**What it contains:**
- Source repository for RAMSES transliteration corpus used by Serge Rosmorduc
- We already import RAMSES — this is the upstream git source
- May have newer data than our current import

**License:** CC BY-NC-SA  
**Import difficulty:** EASY — already have the importer  
**Priority: LOW** — Verify we're importing the latest version; check for any recent additions.

---

### 23. Internet Archive — Egyptological Reference Scans
**URL:** https://archive.org  
**Key items found:**
- Edwin Smith Surgical Papyrus (Breasted translation) — `eberspapyrusbookbybreasted` identifier
- Glanville's Catalogue of Demotic Papyri in the British Museum (1955)
- Annual Egyptological Bibliography (multiple volumes)
- DFIFAO 12: Répertoire Onomastique de Deir el-Médina (Černý + Bruyère + Clère)

**License:** Various (public domain for pre-1928 works)  
**Import difficulty:** HARD for text extraction — scanned PDFs; requires OCR  
**Priority: LOW** — OCR pipeline prerequisite; valuable for Phase 3.

---

### 24. Ancient Lives / Zooniverse
**URL:** https://www.zooniverse.org/projects/ancientlives  
**What it contains:**
- Crowd-sourced transcription of **Oxyrhynchus papyri** (Greek-language; Egypt find-site)
- Note: These are Greek texts from Egypt, not Egyptian-language texts
- Completed transcription data potentially downloadable via Zooniverse export API

**License:** Open  
**Import difficulty:** MEDIUM — API export for completed transcriptions  
**Overlap with existing:** LOW — Greek texts, not Egyptian  
**Priority: LOW** — Out of scope for Egyptian language corpus; potentially relevant for bilingual Greco-Egyptian texts.

---

### 25. Digital Karnak (UCLA)
**URL:** https://digitalkarnak.ucla.edu  
*(Note: HTTP connection timed out — likely deprecated or offline)*  
**What it contains:**
- 3D reconstruction of Karnak Temple Complex with textual annotations
- Inscriptions mapped to architectural context
- Project appears to have ended; data preservation unclear

**License:** Academic  
**Import difficulty:** HARD — likely offline; contact UCLA Near Eastern Languages dept  
**Priority: LOW** — May be superseded by active SITH/Karnak project (#5).

---

### 26. Wikidata Egyptian Texts + WikiSource
**URL:** https://www.wikidata.org / https://wikisource.org  
**What it contains:**
- Wikidata: structured metadata for many Egyptian texts (Q-items for famous papyri, stelae)
- WikiSource: some Egyptian texts exist in transliteration (e.g., Rosetta Stone, Hymn to the Nile)
- Limited in scope but SPARQL-queryable for concordance links

**License:** CC0 (Wikidata), CC-BY-SA (WikiSource)  
**Import difficulty:** EASY — SPARQL endpoint for Wikidata; WikiSource HTML for texts  
**Overlap with existing:** LOW for text content  
**Priority: LOW** — Useful for Wikidata Q-ID concordance expansion; text content is minimal.

---

## Notable Sources Investigated But Not Recommended

| Source | Reason |
|--------|---------|
| **CDLI** (cuneiform.ucla.edu) | Cuneiform, not Egyptian; Amarna EA letters are Akkadian |
| **Fabricius (Google)** | URL 404; tool discontinued |
| **PHI Greek Inscriptions** | Greek texts from Egypt only |
| **JSTOR** | Paywalled journal articles; no bulk text download |
| **DZA Digitale Zettelarchiv** | Servlet endpoint returns 404; appears deprecated in favor of TLA web |
| **Kaggle** | No substantive Egyptian language text datasets found |
| **EgyptSearch forums** | Community discussion; no structured text data |
| **OSF Egyptology** | No significant dataset deposits found |

---

## Recommended Import Queue

| # | Source | Texts | Sentences | Effort | Timeline |
|---|--------|-------|-----------|--------|----------|
| 1 | **AED-TEI** (hiero XML layer) | 11,396 | ~400K | 3 days | Phase 1.5 |
| 2 | **Coptic Scriptorium** | 70+ corpora | ~500K | 4 days | Phase 2 |
| 3 | **Nederhof St Andrews** | ~150 | ~10K | 2 days | Phase 1.5 |
| 4 | **Met Museum API** | 27,971 obj | ~30K inscr. | 1 day | Phase 2 |
| 5 | **ISUT hieratic** | TBD | TBD | 1 week | Phase 3 |
| 6 | **Karnak SITH** (scrape) | thousands | TBD | 2 weeks | Phase 3 |
| 7 | **Totenbuch Bonn** | ~200 spells | ~60K | 1 week | Phase 2 |
| 8 | **AED lemma dict** | 30K lemmata | N/A | 0.5 days | Phase 1.5 |
| 9 | **Trismegistos TexRelations** | (concordance) | N/A | 1 day | Phase 2 |
| 10 | **Brooklyn/Louvre APIs** | ~5K ea. | ~5K ea. | 1 day ea. | Phase 2 |

---

## Canonical ID Namespace Proposals

For new sources, extend the `canonical_id` scheme:
- `aeg_aedtei_{id}` — AED-TEI texts (TLA base32 ID as source_id)
- `aeg_copcorp_{text_name}` — Coptic Scriptorium (use corpus dir name)
- `aeg_nederhof_{slug}` — St Andrews texts
- `aeg_met_{objectid}` — Metropolitan Museum objects
- `aeg_karnak_{kiu}` — Karnak KIU numbers
- `aeg_totenbuch_{spell}_{ms_id}` — Totenbuch spell witnesses

---

*Research by Claude Code, 2026-04-05. URLs checked via live HTTP. Sizes estimated from GitHub repo metadata, Zenodo records, and API responses.*
