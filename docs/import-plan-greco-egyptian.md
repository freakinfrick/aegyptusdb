# Import Plan: Greco-Egyptian Bridge Texts

*2026-04-07 · Fills gaps identified in "The Logos Before the Greeks" (Articles/the-logos-before-the-greeks.md)*

## Executive Summary

Three text collections are needed to close the circuit between Egyptian creation theology and Greek Logos philosophy. Two are **partially present** in upstream data but not imported. One requires a **new source**.

| Collection | Texts | Status | Effort |
|---|---|---|---|
| Shabaka Stone (Memphite Theology) | 1 text (~60 columns) | **Not in ORAEC or any upstream source** | Medium — manual ingest or new connector |
| Nag Hammadi Library | 13 codices, 52+ treatises | **In DCLP XML, not imported** (filter bug) | Low — fix importer filter |
| Corpus Hermeticum + related | ~20 texts | **Partially in DCLP** (3 fragments), full texts not available | Medium — new source needed |

---

## 1. Shabaka Stone / Memphite Theology (BM EA 498)

### What it is
A basalt slab inscribed by Pharaoh Shabaka (25th Dynasty, c. 710 BCE), copying an older text. Contains the "Memphite Theology" — Ptah creates the world through his heart (= Horus) and tongue (= Thoth). The most direct Egyptian ancestor of the Greek *logos* doctrine.

### Why it's missing
- Not in ORAEC corpus raw data (13,035 files searched, no match for any variant of "Shabaka," "Schabaka," "Memphite," "Denkmal memphitischer Theologie," or "BM EA 498")
- Not in Nederhof's HieroJax collection
- Not in DCLP (literary papyri, not a papyrus)
- Not in TLA-HF dataset
- Not in AES

### Import options

**Option A: Manual ingest (fastest)**
Use Breasted's or Junker's published transliteration + translation. Create a structured JSON and ingest via `aegyptus ingest`:

```bash
aegyptus ingest shabaka_stone.json \
  --name "Denkmal memphitischer Theologie / Shabaka Stone (BM EA 498)" \
  --script-type hieroglyphic \
  --source "manual" \
  --ids tm:23755,bm:EA498
```

Source texts (public domain / academic):
- Breasted, J.H. (1901) "The Philosophy of a Memphite Priest" — full transliteration + English
- Junker, H. (1940) "Die Götterlehre von Memphis" — full transliteration + German
- Lichtheim, M. (1973) *Ancient Egyptian Literature* Vol. 1, pp. 51–57 — normalized English
- Allen, J.P. (1988) "Genesis in Egypt" — updated translation

Key passages to ensure are sentence-segmented:
- Lines 48–61: Heart-tongue creation account (core Logos parallel)
- Lines 53–55: "The Ennead of Ptah... his teeth and his lips... which are the semen and hands of Atum"
- Lines 56–58: "Heart and tongue have power over all limbs"
- Lines 59–61: "Thus it was found and recognized that his power is greater than that of the other gods"

**Option B: TLA web scrape**
The Berlin TLA (thesaurus-linguae-aegyptiae.de) has the Shabaka Stone with full sentence-level analysis. Would require a new scraper/connector for the TLA web interface (distinct from the TLA-HF Hugging Face dataset which doesn't include it).

**Option C: ORAEC web check**
ORAEC may have it on their website but not in their GitHub corpus dump. Check https://oraec.github.io/ for the text ID. If present, could add it to the ORAEC connector's fetch list.

**Recommendation:** Option A for speed, Option B for depth (sentence-level tokens + morphology).

---

## 2. Nag Hammadi Library

### What it is
52+ Coptic treatises found at Nag Hammadi (1945). Includes Hermetic, Gnostic, philosophical, and early Christian texts. Key texts for the Logos bridge:

- **Codex VI** (TM 107746): *Discourse on the Eighth and Ninth* (Hermetic initiation), *Prayer of Thanksgiving*, *Asclepius 21–29*
- **Codex II** (TM 107742): *Gospel of Thomas*, *On the Origin of the World*, *Hypostasis of the Archons*
- **Codex I** (TM 107741): *Apocryphon of James*, *Gospel of Truth*, *Treatise on Resurrection*
- **Codex III** (TM 107743): *Apocryphon of John*, *Sophia of Jesus Christ*
- **Codex VII** (TM 107747): *Teachings of Silvanus*, *Three Steles of Seth*
- **Codex XI** (TM 107751): *Valentinian Exposition*
- **Codex XIII** (TM 107753): *Trimorphic Protennoia*, *On the Origin of the World*

### Why they're not imported
The DCLP data directory contains **16 Nag Hammadi XML files** (TM 107741–107753 + 108000 + 87192 + 108146). However, the `papyri_info` importer filters for Egyptian language markers using `EGYPTIAN_MARKERS`:

```python
EGYPTIAN_MARKERS = [
    "hieratic", "demotic", "coptic", "egyptian",
    ...
]
```

The Nag Hammadi DCLP files mention "Coptic" only in inventory numbers (`Cairo, Coptic Museum 10549 Nag Hammadi codex 6`) and religion tags (`Egyptian background`), **not** in `langUsage` elements. The grep-based pre-filter likely misses them, or the XML parser doesn't classify them as Egyptian.

### Fix

**Step 1: Verify the filter gap**
```bash
cd aegyptusdb
# Check which NH files the grep catches
grep -ril "coptic\|egyptian\|demotic" data/upstream/idp.data/DCLP/108/1077*.xml | wc -l
# vs total NH files
ls data/upstream/idp.data/DCLP/108/1077*.xml | wc -l
```

**Step 2: Patch the importer**
Add Nag Hammadi inventory-number patterns to detection:

```python
# In importers/papyri_info/connector.py
# Add to EGYPTIAN_MARKERS or add a separate NH_MARKERS list:
NH_MARKERS = [
    "Nag Hammadi", "Coptic Museum",
    "nag hammadi", "coptic museum",
]
```

Or add a force-include list of known TM IDs:

```python
FORCE_INCLUDE_TM_IDS = {
    "107741", "107742", "107743", "107744", "107745",
    "107746", "107747", "107748", "107749", "107750",
    "107751", "107752", "107753",
    "63986",   # Poimandres hymn
    "66868",   # Hermetic text
    "64247",   # Hermetic text + Book of Jannes/Jambres
}
```

**Step 3: Re-run importer**
```bash
python -m aegyptus.importers.papyri_info
```

**Expected yield:** ~16 codex-level records. Note: DCLP typically has metadata only (titles, dates, provenance) — full transcriptions may be sparse. The actual Coptic text of the Nag Hammadi library would need a supplementary source.

### Supplementary sources for full text

- **The Nag Hammadi Scriptures** (Marvin Meyer, ed., 2007) — English translations, copyrighted
- **The Coptic Gnostic Library** (Brill) — critical Coptic text + English, restricted
- **The Nag Hammadi Archive** at Claremont — some digitized images
- **CMCL (Corpus dei Manoscritti Copti Letterari)** — http://www.cmcl.it — structured Coptic literary catalog, CC license varies
- **Digital Coptic Corpus** (Coptic SCRIPTORIUM) — https://copticscriptorium.org — TEI XML, CC BY, **has Nag Hammadi texts with Coptic + English**

**Recommendation:** Import DCLP metadata now (fix filter). Then build a connector for **Coptic SCRIPTORIUM** to get full sentence-level Coptic text + English translations for all NH texts. Coptic SCRIPTORIUM is CC BY and structured as TEI XML — ideal for import.

---

## 3. Corpus Hermeticum + Related Hermetic Texts

### What it is
- **Corpus Hermeticum** (CH I–XVII): 17 Greek treatises attributed to Hermes Trismegistus. Composed 100–300 CE in Egypt. CH I (*Poimandres*) is the key Logos text.
- **Asclepius**: Latin translation of a Greek original (Coptic fragments in Nag Hammadi Codex VI — see above)
- **Stobaean Hermetica**: Excerpts preserved in Stobaeus' *Anthology*
- **Definitions of Hermes Trismegistus to Asclepius**: Armenian tradition, recently edited

### What's already in DCLP
| TM ID | Content | Status |
|---|---|---|
| 63986 | Prayers including hymn for Poimandres | In DCLP, not imported |
| 66868 | Hermetic text (unspecified) | In DCLP, not imported |
| 64247 | Christian Hermetic text + Book of Jannes/Jambres | In DCLP, not imported |
| 107746 | Includes Asclepius 21–29 + Discourse on 8th/9th (Coptic, Nag Hammadi) | In DCLP, not imported |

### What's not available digitally
The full Greek text of the Corpus Hermeticum is not in any open-access structured corpus that the current importers can reach. Options:

**Option A: Digital editions**
- **Perseus Digital Library** — does not include CH
- **TLG (Thesaurus Linguae Graecae)** — has CH, but requires institutional subscription
- **Nock/Festugière edition** (1945) — standard critical text, public domain in EU
- **Coptic SCRIPTORIUM** — has NH Asclepius and Discourse on 8th/9th in Coptic

**Option B: Manual ingest of key passages**
For the Logos article's purposes, only CH I (*Poimandres*) and CH XIII (*On Rebirth*) are essential. Manual ingest of these two texts with sentence-level segmentation:

```bash
aegyptus ingest corpus_hermeticum_1.json \
  --name "Corpus Hermeticum I: Poimandres" \
  --script-type greek \
  --source "manual" \
  --ids tm:63986
```

Note: This would be the first **Greek-language** text in the corpus. Would need to add `greek` to the allowed `script_type` values in the schema, or use a new field.

**Option C: New connector for early-editions.info or similar**
The *Hermetic Anthology* project and similar academic digital editions may offer structured XML. Would need investigation.

**Recommendation:** Import DCLP fragments now (same filter fix as NH). Manual ingest of CH I (*Poimandres*) for the Logos connection. Defer full CH import until a structured digital source is identified.

---

## Implementation Order

### Phase 1: Quick wins (1–2 hours)
1. **Fix papyri.info importer filter** — add `FORCE_INCLUDE_TM_IDS` or expand `EGYPTIAN_MARKERS` to catch Nag Hammadi + Hermetic DCLP files
2. **Re-run importer** — `python -m aegyptus.importers.papyri_info`
3. **Verify** — check that TM 107741–107753, 63986, 66868, 64247 are now in corpus

### Phase 2: Shabaka Stone (2–4 hours)
1. **Prepare structured JSON** from Breasted/Junker/Allen translations
2. **Sentence-segment** the heart-tongue creation passage (lines 48–61)
3. **Ingest** with proper concordance links (TM 23755, BM EA 498)
4. **Verify** — search for "Memphite" and "Shabaka" should now resolve

### Phase 3: Coptic SCRIPTORIUM connector (1–2 days)
1. **Research** Coptic SCRIPTORIUM TEI XML format
2. **Build connector** in `importers/coptic_scriptorium/`
3. **Import** Nag Hammadi texts with full Coptic + English sentence data
4. **Link** to existing DCLP metadata records via TM ID concordance

### Phase 4: Corpus Hermeticum CH I (2–4 hours)
1. **Prepare structured JSON** for Poimandres from public-domain edition
2. **Add `greek` script type** to schema if needed
3. **Ingest** with TM concordance
4. **Link** to existing DCLP Poimandres hymn record

### Phase 5: Schema consideration
Adding Greek texts to an Egyptian corpus raises a scope question. Options:
- **A) Expand scope:** Aegyptus becomes "texts from Egypt" not "Egyptian-language texts" — includes Greek, Latin, Coptic, Demotic, etc.
- **B) Tag boundary:** Keep focus on Egyptian-language texts but add a `bridge_text` tag for Greco-Egyptian material that contextualizes the core corpus
- **C) Separate collection:** Create a `greco_egyptian` collection within the corpus, queryable but distinct

**Recommendation:** Option B. The corpus already has 11,177 Coptic texts (a language with heavy Greek vocabulary). Greek Hermetic texts composed in Egypt, about Egyptian theology, by Egyptian-Greek authors, are within scope as bridge material.

---

## Expected Yield

| Source | Texts | Sentences | Languages |
|---|---|---|---|
| Nag Hammadi (DCLP metadata) | ~16 | 0 (metadata only) | Coptic |
| Nag Hammadi (Coptic SCRIPTORIUM) | ~52 | ~5,000+ | Coptic + English |
| Hermetic DCLP fragments | ~4 | ~10–50 | Greek/Coptic |
| Shabaka Stone | 1 | ~60–80 | Egyptian (hieroglyphic) |
| Corpus Hermeticum I | 1 | ~30–40 | Greek |
| **Total new** | **~74** | **~5,100–5,170** | |

Post-import corpus: ~62,200 texts, ~309,800 sentences. The Logos article's gap section can then be updated to "filled."

---

## License Notes

| Source | License | Commercial use |
|---|---|---|
| DCLP / papyri.info | CC BY 3.0 | ✅ Yes |
| Coptic SCRIPTORIUM | CC BY 4.0 | ✅ Yes |
| Shabaka Stone (Breasted 1901) | Public domain | ✅ Yes |
| Shabaka Stone (Allen 1988) | Copyrighted | ❌ Translation only for reference |
| Corpus Hermeticum (Nock/Festugière) | Public domain in EU | ⚠️ Check jurisdiction |
