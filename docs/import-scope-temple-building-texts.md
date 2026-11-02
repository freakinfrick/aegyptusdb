# Import scope — temple building texts (Edfu, Dendera, Book of the Temple)

Scoped 2026-10-25 for the open-reading research thread
(`docs/outreach/unchartedx-abu-rawash-2026-10-25.md`, "Gaps").

**Status 2026-10-25: imported** as `aeg_manual_dendera_crypt_bauurkunde_duemichen1865` (158
sentences incl. the 136-name list), `aeg_manual_edfu_bauurkunde_duemichen1870` (40), `aeg_manual_edfu_foundation_rite_brugsch1870`
(17, incl. axis lengths, the Mesen's 8⅓ × 6⅔ cubits, brick-moulding rite). German as published; English and the two Dendera transliterations are `ml_draft`, needs review.
Open: Dendera lines 1–21 (printed pp. 38–39 missing from both scans). Full Edfu room
measurements are in Dümichen's *Tempel-Inschriften* pls. 92ff, not yet located online.

## What the corpus holds now

Almost nothing. "Tell Edfu" findspots (59) are Greek and Demotic ostraca and papyri,
not temple walls. Ptolemaic hieroglyphic texts: 2 (both `aed_tei`). No Edfu or
Dendera building inscriptions, no Book of the Temple.

## Sources found

### Importable now (public domain)

1. **Dümichen 1865, *Bauurkunde der Tempelanlagen von Dendera in einem der geheimen
   Corridore im Innern der Tempelmauer aufgefunden*.** Internet Archive
   `bub_gb_KR8GAAAAQAAJ` (Public Domain Mark) and `bauurkundederte00dmgoog`
   (NOT_IN_COPYRIGHT); 82–94 pages, ~16k words of OCR. The building record from
   Dendera's **crypts** (the "secret corridors"). Plates XV–XVI state that the
   great foundation of Dendera is a monumental restoration by Thutmose III "after
   it was found in ancient writings from the time of King Khufu", and Dümichen
   reports the document was found inside a wall of the palace under Pepi (6th dyn.).
   Hits three threads at once: a plan predating the builder king, kept and found in
   hidden places, and an *announced* restoration.
2. **Zeitschrift für ägyptische Sprache 8 (1870)**, Internet Archive
   `zeitschriftfr08brug`, ~95k words. Contains:
   - Dümichen, *Bauurkunde der Tempelanlagen von Edfu*: the historical building
     record of Edfu, with German translation.
   - Brugsch, *Bau und Maaße des Tempels von Edfu* (construction and measurements).
   - A long section on the **temple foundation ceremony**: the "stretching of the
     cord", Seshat as "Mistress of the foundation", orientation of the north point,
     the king's ritual speech holding peg, mallet and cord.

Both are pre-1900 German scholarship: real Egyptian text in an outdated
translation. They fill the cord-stretching gap (1 hit today) and give us the Edfu
building record in some form.

### Not importable (licensing or availability)

- **Edfu, full corpus.** Chassinat's *Le temple d'Edfou* (14 vols, hieroglyphic type)
  isn't on the Internet Archive; later volumes and the Cauville–Devauchelle revisions
  are in copyright. Kurth's German translations (*Die Inschriften des Tempels von
  Edfu*, Harrassowitz) are in copyright. The Göttingen Academy's **Edfu-Datenbank**
  (10,452 entries, Chassinat V–VIII) is a location index only: entries say
  transliteration and translation are "not available", it has no license, and
  robots.txt disallows its search pages. Getting the data means asking the Academy.
- **Book of the Temple.** No published full edition. Quack's 2016 chapter
  ("Translating the realities of cult") is on Heidelberg's propylaeumdok, behind a
  bot wall (not bypassed). Desk reading for a human, not an import.
- **Inventory Stela** (Cairo JE 2091): no public-domain scan found by title. Small
  text; defer.

## Plan for the importable pair

Follows the `scripts/ingest_manual.py` path, same as `data/manual/shabaka_stone.json`.

1. Download both PDFs to `data/upstream/pd_scans/` (2 requests, archive.org).
2. Re-OCR the relevant pages with the docling skill (tesseract, `deu`). The archive.org
   OCR is too noisy ("Gnindung", "Itmern"). **No `llm-clean`**: it would make the text
   ML output and force `ml_draft` tags on a public-domain translation.
3. Hand-segment into sentences keyed by Dümichen's plate/line numbers. German goes in
   `translation.de`. Dümichen's 1860s transliteration goes in `source_detail`, **not**
   the `transliteration` column, so it doesn't pollute modern-transliteration greps.
4. One JSON per text: `aeg_manual_dendera_bauurkunde_duemichen1865`,
   `aeg_manual_edfu_bauurkunde_duemichen1870`, `aeg_manual_edfu_grundsteinlegung_zas1870`.
   Metadata: `license: public_domain`, `confidence: low`, `needs_review: true`,
   source citation, archive.org identifier, note "19th-century translation".
5. `python3 scripts/ingest_manual.py data/manual/<file>.json`, then re-run the
   open-reading greps (Seshat, cord, Khufu, crypt) against the live DB.

**Not in scope:** a hieroglyph layer. The plates are lithographs; encoding them to
Unicode is manual sign-by-sign work.

**Time (agent):** ~2–2.5 h total. Dendera ~1 h; the two ZÄS pieces ~1–1.5 h. OCR
~10 min on CPU. No GPU, no model calls, no cost. Easy to undo (three
`aeg_manual_*` IDs).

**Human time:** none to import. Edfu at full scale needs the user's decision on
contacting the Göttingen Academy.
