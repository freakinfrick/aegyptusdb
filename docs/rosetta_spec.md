# The Rosetta Stone — Multilingual Decoding Engine

*Project specification for the Aegyptus corpus universal translation system.*
*By the power of Thoth, who gave writing to humanity and weighs the heart against the feather.*

---

## 1. Purpose

The ancient Egyptian textual tradition spans three thousand years, six scripts, and a dozen modern scholarly languages. The texts survive in fragments — a sentence translated into German here, a word glossed in French there, a Coptic cognate preserving a meaning lost in the hieroglyphic original. No single translation covers the whole. The knowledge remains locked behind linguistic barriers that exclude everyone except a handful of specialists.

**Rosetta** is the system that breaks those barriers. It uses every available witness — every translation, every word gloss, every cognate, every dictionary entry, every parallel passage — to produce grounded English translations of every sentence in the Aegyptus corpus. It does what the original Rosetta Stone did: uses the known to decode the unknown, except at the scale of the entire surviving textual record of ancient Egypt.

The output is not a black box. Every English rendering links back to the evidence that produced it — which dictionary entry, which German gloss, which parallel sentence, which Coptic cognate. The reader can follow the chain from hieroglyph to English and judge the translation for themselves. The scholarly apparatus is preserved; the barrier to understanding is removed.

---

## 2. Current Assets

### 2.1 Parallel Sentence Corpus

| Source | Sentences | English | German | Tokens | Token-aligned |
|---|---|---|---|---|---|
| ORAEC | 101,796 | 90,061 | 100,633 | ✅ lemmaID + hiero + POS + DE gloss | ✅ |
| AES | 101,796 | 91,561 | 100,633 | ✅ lemmaID + POS + DE gloss | ✅ |
| AED-TEI | 98,265 | 0 | 98,265 | ✅ DE word-level gloss + corresp IDs | ✅ |
| RAMSES | 71,263 | 71,032 | 0 | ✅ POS + morphology | ✅ |
| Coptic Scriptorium | 51,474 | 51,469 | 0 | ✅ lemma + POS + features + entity | ✅ |
| TLA-HF | 29,762 | 25,297 | 29,762 | ✅ glossing field | partial |
| Manual | 39 | 39 | 0 | — | — |
| **Total** | **454,399** | **329,459** | **329,293** | **454,393** | |

**Key fact:** 329K sentences have English. 125K do not. Of those 125K, **98K have German translations + word-level German glosses** (AED-TEI). The remaining ~27K have partial coverage (German only, or tokens without translations).

### 2.2 Lexical Assets

| Asset | Entries | Languages | Content |
|---|---|---|---|
| AED Lemmata table | 35,052 | DE (all), EN (16,971) | Transliteration, POS, translations, bibliography, root cross-refs |
| ORAEC token vocabulary | ~15K unique lemmaIDs | DE (cotext_translation) | Word-in-context German glosses |
| AES token vocabulary | ~15K unique lemmaIDs | DE (cotext_translation) | Word-in-context German glosses |
| AED-TEI token vocabulary | ~20K unique words | DE (word-level) | Aligned German word translations per sentence |
| Coptic Scriptorium lemmas | ~8K unique lemmas | Coptic + POS | Sahidic lemma forms with Greek loan markers |

### 2.3 Bridge Assets

| Asset | What it provides |
|---|---|
| Shabaka Stone (manual) | Heart-tongue creation theology — Egyptian→English, annotated Logos parallel |
| Poimandres (manual) | Greek Logos theology — Greek→English, annotated Egyptian parallel |
| Coptic texts with English | 51K sentences where Late Egyptian vocabulary survives in Coptic script with English translation |
| Concordance graph (265K+ links) | Cross-references linking the same physical text across 40+ external systems |

### 2.4 Existing Translation Infrastructure

The `processing/draft_translation/` module already implements:
- `LemmaDictionary` — builds a word-meaning lookup from corpus tokens (German glosses + TLA glossing)
- `DraftTranslationService` — LLM-based translation with local llama-server or Anthropic Claude backends
- `TranslationPrompt` — structured prompt with transliteration, token glosses, POS sequence
- Batch translation mode (JSON array output, 20 sentences/request)
- Quality validation (length checks, echo detection, artifact filtering)
- Save pipeline with `ml_draft` / `needs_review` tagging
- Gemini and Haiku translation scripts for batch processing

**What's missing:** The existing system treats translation as a monolingual problem (Egyptian→English via LLM). It doesn't leverage the German translations, doesn't cross-reference Coptic cognates, doesn't use parallel sentences as few-shot examples, and doesn't build a persistent enriched lexicon. Rosetta adds these capabilities.

---

## 3. Architecture

Three layers, built in sequence, each feeding the next:

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 3: TRANSLATION ENGINE                   │
│  For each untranslated sentence:                                │
│    1. Decompose into tokens                                     │
│    2. Look up each token in the Thoth Lexicon                   │
│    3. Retrieve parallel examples from the Witness Index          │
│    4. Assemble grounded prompt with all witnesses                │
│    5. LLM renders fluent English from multilingual evidence      │
│    6. Tag, validate, store with provenance chain                 │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 2: WITNESS INDEX                        │
│  For each sentence, gather all available evidence:               │
│    - German translation (sentence-level)                         │
│    - German word glosses (token-level)                           │
│    - Similar translated sentences (by vocabulary overlap)        │
│    - Coptic cognate sentences (by lemma linkage)                 │
│    - Period/genre context from text metadata                     │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 1: THOTH LEXICON                        │
│  For each Egyptian lemma, a multilingual dossier:                │
│    - AED dictionary definition (DE + EN)                         │
│    - Corpus-attested German glosses (from token alignments)      │
│    - Corpus-attested English contexts (from parallel sentences)  │
│    - Coptic descendant forms (from Scriptorium lemma links)      │
│    - Hieroglyphic encoding                                       │
│    - POS, morphology, frequency, attestation range               │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                    Existing corpus data
                    (454K sentences, 35K lemmata, 290K aligned tokens)
```

---

## 4. Layer 1: The Thoth Lexicon

### 4.1 Purpose

A persistent, queryable, multilingual Egyptian lexicon derived from corpus evidence. Each entry aggregates everything the corpus knows about a single Egyptian word. This is both a scholarly artifact (an open-access Egyptian–English–German–Coptic dictionary grounded in attestations) and the foundation for machine translation.

### 4.2 Schema

New table: `thoth_lexicon` (or extend the existing `lemmata` table with enrichment columns).

```sql
CREATE TABLE thoth_lexicon (
    lemma_id TEXT PRIMARY KEY REFERENCES lemmata(id),

    -- Dictionary definitions (from AED lemmata table)
    definition_de TEXT,
    definition_en TEXT,

    -- Corpus-mined meanings
    glosses_de JSONB,        -- {"Hirt, Hüter": 45, "Hirte": 12, ...} (gloss → frequency)
    glosses_en JSONB,        -- {"shepherd": 30, "herdsman": 8, ...} (mined from EN sentence contexts)
    glosses_bridged_en JSONB,-- {"shepherd": 0.92, ...} (German gloss → English via bridge)

    -- Coptic cognates
    coptic_cognates JSONB,   -- [{"form": "ⲥⲱⲧⲙ", "lemma": "ⲥⲱⲧⲙ", "meaning_en": "to hear", "source": "coptic_scriptorium"}]

    -- Hieroglyphic forms
    hieroglyphs JSONB,       -- ["𓃢", "𓃢𓏤"] (all attested Unicode hieroglyphic writings)

    -- Morphological profile
    pos TEXT,                -- primary POS
    pos_distribution JSONB,  -- {"substantive": 340, "verb": 12} (POS as attested in corpus)

    -- Attestation statistics
    frequency INTEGER,       -- total token occurrences across corpus
    frequency_rank INTEGER,  -- rank (from AED ranglist or computed)
    period_range JSONB,      -- {"earliest": -2500, "latest": -300}
    text_types JSONB,        -- {"stela": 45, "papyrus": 23, "coffin_text": 12}

    -- Usage examples (best parallel sentence pairs per meaning)
    examples JSONB,          -- [{"translit": "...", "en": "...", "de": "...", "sentence_id": 12345}, ...]

    -- Metadata
    sources JSONB,           -- ["aed", "oraec_tokens", "aes_tokens", "coptic_scriptorium"]
    confidence TEXT,         -- "high" (dictionary + corpus), "medium" (corpus only), "low" (single attestation)
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_thoth_frequency ON thoth_lexicon (frequency DESC);
CREATE INDEX idx_thoth_pos ON thoth_lexicon (pos);
CREATE INDEX idx_thoth_glosses_en ON thoth_lexicon USING gin (glosses_en);
```

### 4.3 Build Pipeline

**Phase 1a: Seed from AED lemmata** (existing data, minutes)
- Copy `lemmata.id`, `lemmata.form`, `lemmata.translation->>'de'`, `lemmata.translation->>'en'`, `lemmata.pos` into `thoth_lexicon`.
- 35,052 entries. 16,971 already have English definitions.

**Phase 1b: Mine German glosses from aligned tokens** (corpus scan, ~10 min)
- Scan all 290K token-aligned sentences (ORAEC, AES, AED-TEI).
- For each token with a `lemmaID`, collect its `cotext_translation` (ORAEC/AES) or `translation_de` (AED-TEI).
- Aggregate by lemmaID → `glosses_de` with frequency counts.
- Estimated yield: ~20K lemmas with German gloss distributions.

**Phase 1c: Mine English contexts from parallel sentences** (corpus scan, ~15 min)
- For each sentence with English translation AND token-level lemmaIDs:
  - Record which lemmaIDs appear in sentences with which English translations.
  - Use TF-IDF or co-occurrence to associate lemmaIDs with English terms.
  - This produces `glosses_en` — statistical English glosses from sentence-level alignment.
- Not word-level precise, but gives distributional English associations per lemma.
- Estimated yield: ~15K lemmas with English context distributions.

**Phase 1d: Bridge German glosses to English** (LLM batch, ~1 hour)
- For the ~18K lemmas that have German glosses but no English definition:
  - Batch the German glosses to an LLM: "Translate these Egyptological German terms to English: Hirt, Hüter → shepherd, guardian"
  - This is a high-confidence step — scholarly German→English for domain terms.
  - Store results in `glosses_bridged_en`.
- After this step, ~33K+ lemmas have English meanings (up from 16,971).

**Phase 1e: Link Coptic cognates** (corpus cross-reference, ~5 min)
- Match Egyptian lemma forms to Coptic Scriptorium lemma forms using known Egyptian→Coptic phonological correspondences.
- Where a Coptic lemma appears in a sentence with English translation, the English meaning validates/enriches the Egyptian lemma.
- This is a diachronic witness — the same word, 2000 years later, in a language we can read directly.
- Store in `coptic_cognates`.

**Phase 1f: Compute attestation statistics** (corpus scan, ~5 min)
- Count token frequency per lemma across all sources.
- Extract period range from parent text metadata (`date_earliest`, `date_latest`).
- Extract text type distribution from parent text metadata.
- Select best example sentences (highest quality translation + most representative usage).

### 4.4 Quality Tiers

Each lexicon entry gets a confidence tier:

| Tier | Criteria | Expected count |
|---|---|---|
| **Gold** | AED dictionary EN + DE + corpus attestations ≥ 10 | ~12K |
| **Silver** | AED dictionary DE + bridged EN + corpus attestations ≥ 3 | ~15K |
| **Bronze** | Corpus-mined only, or single attestation | ~8K |

---

## 5. Layer 2: The Witness Index

### 5.1 Purpose

For any sentence that needs translation, the Witness Index gathers all available evidence — the sentence's own tokens and glosses, similar already-translated sentences, the German translation if available, and relevant Coptic parallels. This is the "Rosetta assembly" step.

### 5.2 Witness Types

| Witness | Source | Weight | Coverage |
|---|---|---|---|
| **Lexicon gloss** | Thoth Lexicon per token | High | ~95% of tokens with lemmaIDs |
| **German sentence translation** | `sentences.translation->>'de'` | High | 329K sentences |
| **German word glosses** | Token-level `cotext_translation` / `translation_de` | High | 290K sentences |
| **Parallel examples** | Similar translated sentences (vocabulary overlap) | Medium | Up to 5 per sentence |
| **Coptic cognates** | Thoth Lexicon `coptic_cognates` per token | Low-Medium | ~2K lemmas |
| **Hieroglyphic determinatives** | Semantic classifiers from hiero data | Low | Supplementary |
| **Text metadata** | Period, genre, findspot — constrains interpretation | Low | Contextual |

### 5.3 Parallel Sentence Retrieval

For each untranslated sentence, find the most similar already-translated sentences:

1. Extract the set of lemmaIDs from the untranslated sentence's tokens.
2. Query an inverted index: `lemmaID → [sentence_ids that contain this lemma]`.
3. Score candidate sentences by Jaccard similarity of lemmaID sets.
4. Return top-5 candidates with their English + German translations.

This gives the LLM concrete examples of how similar vocabulary has been translated in context — the few-shot grounding.

**Implementation:** Pre-build an inverted index table:

```sql
CREATE TABLE rosetta_lemma_index (
    lemma_id TEXT NOT NULL,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id),
    PRIMARY KEY (lemma_id, sentence_id)
);
CREATE INDEX idx_rosetta_lemma_sent ON rosetta_lemma_index (sentence_id);
```

Populate by scanning all token-aligned sentences. ~2M rows (454K sentences × ~5 tokens avg with lemmaIDs).

### 5.4 Witness Assembly

For a given untranslated sentence, assemble the **Witness Dossier**:

```python
@dataclass
class WitnessDossier:
    """All available evidence for translating a single sentence."""

    # The sentence itself
    sentence_id: int
    canonical_id: str
    transliteration: str
    tokens: list[dict]

    # Per-token evidence from Thoth Lexicon
    token_witnesses: list[TokenWitness]  # [{lemma_id, form, en_gloss, de_gloss, pos, hiero, coptic_cognate}]

    # Sentence-level German translation (if available)
    german_translation: str | None

    # German word glosses assembled into interlinear
    german_interlinear: str | None

    # Similar already-translated sentences
    parallel_examples: list[ParallelExample]  # [{translit, en, de, similarity_score}]

    # Text context
    period: str | None
    text_type: str | None
    source: str

    # Confidence estimate (before LLM)
    pre_confidence: str  # "high" (DE translation + good lexicon), "medium", "low"
```

---

## 6. Layer 3: The Translation Engine

### 6.1 Purpose

Produce fluent, grounded English translations from Witness Dossiers. The LLM is not translating Egyptian — it is synthesizing English from multilingual evidence. This is a much easier and more reliable task.

### 6.2 Translation Tiers

Not all 125K untranslated sentences are equal. Tier them by available evidence:

| Tier | Evidence available | Strategy | Sentences | Expected quality |
|---|---|---|---|---|
| **T1** | German translation + word glosses + lexicon | LLM synthesizes from German + glosses | ~98K (AED-TEI) | High |
| **T2** | German translation only (no word glosses) | LLM translates German + lexicon context | ~4K | High |
| **T3** | Tokens + lexicon only (no German, no English) | LLM translates from interlinear gloss + parallels | ~12K | Medium |
| **T4** | Transliteration only (no tokens) | LLM translates from transliteration + lexicon lookup | ~5K | Low |
| **T5** | Fragments / damaged / minimal data | Flag for human review | ~6K | Skip or low |

### 6.3 Prompt Structure

Extends the existing `TranslationPrompt` in `processing/draft_translation/prompt.py`:

```
SYSTEM: You are an expert Egyptologist producing English translations from
multilingual evidence. You are given:
- The Egyptian transliteration
- Token-level English/German glosses from the Thoth Lexicon
- A German scholarly translation of the same text (if available)
- Similar sentences already translated into English
Your task: produce a fluent, accurate English translation grounded in this evidence.

USER:
**Transliteration:** ḥtp dj nswt Wsjr nb Ḏdw...
**German translation:** Ein Opfer, das der König gibt, und Osiris, der Herr von Busiris...
**Token glosses:**
  - ḥtp (lemma 111780): offering [substantive] | Opfer
  - dj (lemma 851711): to give [verb] | geben
  - nswt (lemma 88040): king [substantive] | König
  - Wsjr (lemma 49460): Osiris [god_name] | Osiris
  - nb (lemma 81650): lord [substantive] | Herr
  - Ḏdw (lemma 185290): Busiris [place_name] | Busiris
**Similar translated sentences:**
  1. "An offering which the king gives and Osiris, lord of Busiris..." (aeg_oraec_1234)
  2. "A royal offering to Osiris, lord of Abydos..." (aeg_oraec_5678)

Produce: English translation, notes, confidence (HIGH/MEDIUM/LOW).
```

### 6.4 Backend Strategy

Use the existing `DraftTranslationService` infrastructure with enhancements:

| Backend | Use case | Rate | Cost |
|---|---|---|---|
| **Local llama-server (RTX 4090)** | T3/T4 sentences (lexicon-only, lower quality acceptable) | ~15 sent/min (batch mode) | Free |
| **Gemini Flash** | T1 sentences (German→English, high volume) | 15 RPM × 50 sent/batch = 750/min | Free tier |
| **Claude Haiku** | T2 sentences and quality validation | ~200 sent/min | ~$0.001/sent |

**Estimated throughput for 125K sentences:**
- T1 (98K via Gemini batch): ~3 hours
- T2 (4K via Haiku): ~20 minutes
- T3/T4 (17K via local): ~19 hours
- T5 (6K): flagged, not translated
- **Total: ~1 day of processing**

### 6.5 Output Format

Translations are stored on the existing `sentences.translation` JSONB column:

```json
{
  "en": "An offering which the king gives and Osiris, lord of Busiris...",
  "de": "Ein Opfer, das der König gibt, und Osiris, der Herr von Busiris...",
  "_rosetta": {
    "source": "ml_draft",
    "model": "gemini-3.1-flash-lite",
    "tier": "T1",
    "confidence": "HIGH",
    "confidence_llm": "HIGH",
    "witnesses_used": ["german_translation", "token_glosses", "parallel_examples"],
    "parallel_ids": [12345, 67890],
    "needs_review": true,
    "translated_at": "2026-04-08T12:00:00Z"
  }
}
```

The `_rosetta` key preserves the full provenance chain. Any consumer can inspect which witnesses informed the translation and at what confidence.

### 6.6 Validation Pipeline

Before saving, every translation passes:

1. **Length check** — too short or too long relative to source
2. **Echo detection** — LLM repeated the transliteration or German instead of translating
3. **Hallucination check** — proper nouns in translation that don't appear in any witness
4. **Cross-validation** — for T1 sentences, compare LLM English against the German translation semantics (does the English cover the same content as the German?)
5. **Confidence calibration** — if LLM says HIGH but the lexicon coverage of the sentence's tokens is < 50%, downgrade to MEDIUM

---

## 7. Implementation Plan

### Phase 1: Thoth Lexicon Build (2–3 days)

```
1a. Create thoth_lexicon table (migration 003)                    [1 hr]
1b. Seed from lemmata table                                        [30 min]
1c. Mine German glosses from ORAEC/AES/AED-TEI tokens             [2 hr]
1d. Mine English contexts from parallel sentences                  [2 hr]
1e. Bridge German→English for lemmas missing English               [4 hr]
1f. Link Coptic cognates                                          [2 hr]
1g. Compute attestation stats + select example sentences           [2 hr]
1h. Validate lexicon: spot-check 100 entries across tiers          [2 hr]
```

**Deliverable:** `thoth_lexicon` table with ~33K+ entries, >90% with English meanings.

### Phase 2: Witness Index Build (1–2 days)

```
2a. Build rosetta_lemma_index inverted index table                 [2 hr]
2b. Implement parallel sentence retrieval (Jaccard similarity)     [4 hr]
2c. Implement WitnessDossier assembly                              [4 hr]
2d. Test dossier quality on 50 sentences across all tiers          [2 hr]
```

**Deliverable:** `WitnessDossier.assemble(sentence)` returns complete multilingual evidence package.

### Phase 3: Translation Engine (3–5 days)

```
3a. Extend TranslationPrompt with witness dossier fields           [2 hr]
3b. Implement tier classification (T1–T5)                          [2 hr]
3c. Build German→English batch pipeline (T1, Gemini)               [4 hr]
3d. Build lexicon-grounded pipeline (T3/T4, local LLM)            [4 hr]
3e. Build validation pipeline enhancements                         [4 hr]
3f. Run T1 batch (98K AED-TEI sentences)                          [3 hr runtime]
3g. Run T2 batch (4K German-only sentences)                       [30 min runtime]
3h. Run T3/T4 batch (17K token-only sentences)                    [19 hr runtime]
3i. Quality audit: sample 200 translations across tiers            [4 hr]
```

**Deliverable:** 119K new English translations. Corpus goes from 329K to ~448K English sentences (99% coverage of all non-fragment sentences).

### Phase 4: Continuous Enrichment (ongoing)

```
4a. As new texts are imported, auto-classify translation tier
4b. Nightly batch: translate new untranslated sentences
4c. Lexicon growth: new lemmas from new imports feed back into thoth_lexicon
4d. Quality loop: human corrections update lexicon confidence scores
4e. Coptic lexicon expansion (KELLIA import → coptic_cognates enrichment)
```

---

## 8. Integration with Existing Infrastructure

### 8.1 Files to Create

```
rosetta/
├── __init__.py
├── lexicon/
│   ├── __init__.py
│   ├── builder.py          # Thoth Lexicon build pipeline (phases 1a–1g)
│   ├── miner.py            # Token mining: extract glosses from corpus
│   ├── bridge.py           # German→English bridging via LLM
│   ├── coptic.py           # Coptic cognate linking
│   └── models.py           # ThothLexicon SQLAlchemy model
├── witness/
│   ├── __init__.py
│   ├── index.py            # Inverted index build + parallel retrieval
│   ├── dossier.py          # WitnessDossier assembly
│   └── models.py           # RosettaLemmaIndex model
├── engine/
│   ├── __init__.py
│   ├── classifier.py       # Tier classification (T1–T5)
│   ├── translator.py       # Extended translation with witness grounding
│   ├── validator.py        # Enhanced validation pipeline
│   └── batch.py            # Batch orchestration across backends
└── cli.py                  # `aegyptus rosetta build-lexicon`, `translate`, `status`
```

### 8.2 Files to Extend

| File | Changes |
|---|---|
| `processing/draft_translation/service.py` | Import and delegate to `rosetta.engine.translator` for witness-grounded mode |
| `processing/draft_translation/lemma_dict.py` | Replace with `rosetta.lexicon` lookup (backward compatible) |
| `processing/draft_translation/prompt.py` | Extend with witness dossier fields |
| `core/models/corpus.py` | Add `ThothLexicon` and `RosettaLemmaIndex` models |
| `schema/versions/003_rosetta.py` | Migration for new tables |
| `cli.py` | Add `rosetta` command group |

### 8.3 Dependencies

No new dependencies beyond what's in the venv. The system uses:
- `sqlalchemy` for DB operations
- `httpx` for LLM API calls (local + Gemini + Anthropic)
- `xml.etree.ElementTree` for any XML processing
- Standard library for everything else

---

## 9. Success Criteria

| Metric | Target |
|---|---|
| Thoth Lexicon entries with English | ≥ 30,000 (of 35,052 total lemmata) |
| English translation coverage | ≥ 95% of sentences with ≥ 3 tokens |
| T1 translation quality (German-grounded) | ≥ 85% rated acceptable by spot-check |
| T3 translation quality (lexicon-only) | ≥ 65% rated acceptable by spot-check |
| Provenance completeness | 100% of ml_draft translations have `_rosetta` metadata |
| Lexicon query latency | < 10ms per token lookup |
| Full corpus translation time | < 48 hours end-to-end |

---

## 10. What This Makes Possible

With ~448K English sentences covering the full temporal and generic range of Egyptian literature:

- **Any text searchable in English.** Find every mention of "heart" across 3,000 years of Egyptian writing — in offering formulas, medical papyri, love poetry, theological treatises.
- **Thematic studies without language barriers.** Trace the concept of *maat* (truth/justice/cosmic order) from the Pyramid Texts through the Book of the Dead to Coptic Christian appropriations.
- **Cross-tradition comparison.** The Shabaka Stone's heart-tongue theology alongside Poimandres' Logos doctrine, both in English, both linked to their source texts.
- **Open-access Egyptian dictionary.** The Thoth Lexicon, grounded in 454K sentence attestations, published as the first comprehensive open-access Egyptian–English–German dictionary with corpus evidence.
- **Foundation for deeper ML.** 448K parallel pairs (Egyptian→English) is a training corpus for specialized translation models, embedding spaces, and semantic search.

The texts of ancient Egypt become readable — not as fragments scattered across German monographs and French excavation reports, but as a unified body of human knowledge, accessible to anyone who reads English, with every translation traceable back to the stone it was carved on.

---

## Appendix A: Naming

The system is called **Rosetta** after the artifact that first made Egyptian readable to the modern world. The lexicon is called the **Thoth Lexicon** after the Egyptian god of writing, wisdom, and the moon — he who invented *medu neter* (hieroglyphs, literally "words of god"), who recorded the weighing of the heart in the Hall of Maat, and who mediated between the divine and human worlds through the power of language.

The name is not metaphorical. Thoth's domain was exactly this: making the hidden knowable through writing. That is what this system does.

## Appendix B: Data Flow Diagram

```
                    ┌──────────────────┐
                    │   AED Lemmata    │
                    │   35,052 entries │
                    └────────┬─────────┘
                             │ seed
                             ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ ORAEC/AES    │───▶│                  │◀───│ Coptic           │
│ 190K tokens  │    │  THOTH LEXICON   │    │ Scriptorium      │
│ DE glosses   │    │  ~33K entries    │    │ 8K lemmas        │
└──────────────┘    │  EN + DE + Coptic│    └──────────────────┘
                    │  + hiero + POS   │
┌──────────────┐    │  + examples      │
│ AED-TEI      │───▶│                  │
│ 98K tokens   │    └────────┬─────────┘
│ DE word gloss│             │ lookup
└──────────────┘             ▼
                    ┌──────────────────┐
┌──────────────┐    │                  │    ┌──────────────────┐
│ 329K EN      │───▶│  WITNESS INDEX   │◀───│ Concordance      │
│ parallel     │    │  per sentence:   │    │ 265K links       │
│ sentences    │    │  - token glosses │    │ text metadata    │
└──────────────┘    │  - DE translation│    └──────────────────┘
                    │  - parallels     │
┌──────────────┐    │  - Coptic cognates│
│ 329K DE      │───▶│  - context       │
│ parallel     │    └────────┬─────────┘
│ sentences    │             │ assemble
└──────────────┘             ▼
                    ┌──────────────────┐
                    │ TRANSLATION      │
                    │ ENGINE           │
                    │                  │
                    │ T1: DE→EN (98K)  │──▶ Gemini Flash
                    │ T2: DE only (4K) │──▶ Claude Haiku
                    │ T3: tokens (12K) │──▶ Local LLM
                    │ T4: translit (5K)│──▶ Local LLM
                    │ T5: fragments    │──▶ flag for review
                    │                  │
                    └────────┬─────────┘
                             │ save
                             ▼
                    ┌──────────────────┐
                    │ sentences.       │
                    │ translation      │
                    │ ->>'en'          │
                    │                  │
                    │ + _rosetta       │
                    │   provenance     │
                    └──────────────────┘
```
