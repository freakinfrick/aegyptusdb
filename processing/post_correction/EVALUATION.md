# TranslitModels Evaluation

**Date:** 2026-04-02
**Repo:** github.com/MaReTEgyptologists/TranslitModels (CC BY 4.0)
**Cloned to:** `data/upstream/translit_models/`

## What TranslitModels Provides

TranslitModels is a collection of **statistical word models** mapping Manuel de Codage (MdC) hieroglyphic sign sequences to their possible transliterations, with frequency data. Created by Heidi Jauhiainen at the University of Helsinki, funded by the Kone Foundation.

### Models (JSON)

| Model | Entries | Total Interpretations | Entries with >1 interp | Source Corpus |
|-------|---------|----------------------|------------------------|--------------|
| AESModel.json (13.3 MB) | 43,416 | 46,811 | 2,338 (5.4%) | AES corpus (Schweitzer) |
| RamsesTrainingSetModel.json (9.8 MB) | 48,914 | 55,049 | 4,114 (8.4%) | RAMSES corpus (Rosmorduc) |
| AES+RamsesTrainingSetModel.json (22.1 MB) | 84,558 | 97,777 | 8,555 (10.1%) | Combined |

The combined model is recommended for production use.

### Model Structure

Each entry maps an MdC encoding (hieroglyphic sign sequence) to one or more transliteration interpretations:

```json
{
    "encoding": "V30",
    "interpretations": [
        {"transliteration": "nb", "freq": 5309, "relFreq": 86.7},
        {"transliteration": "nb.t", "freq": 501, "relFreq": 8.2},
        {"transliteration": "nb.w", "freq": 231, "relFreq": 3.8}
    ]
}
```

The AES entries additionally carry `originalsLemmasInAes` linking to TLA lemma IDs.

### Java Tools (JARs)

The JARs are **model building tools**, not inference engines:

| JAR | Purpose |
|-----|---------|
| MaReTEAesVocabularyMaker.jar | Extract word lists from AES data |
| CleanRamsesTexts.jar | Clean/normalize RAMSES corpus data |
| MaReTELexiconMaker.jar | Build word pair lexicons |
| MaReTENeedlemanWunsch.jar | Align MdC with transliteration (Needleman-Wunsch) |
| MaReTEModelMaker.jar | Combine word lists into JSON models |

**Key insight:** No JVM is needed for using the models -- they are plain JSON loaded directly in Python. The JVM is only needed to build/retrain models.

## Capabilities Assessment

### What it does well

1. **High-frequency word identification**: Common words like `nb` (V30, 5309 occurrences), `sw` (N5, 5479), `nswt-by.ty` (M23 X1 L2 X1, 197) are resolved with high confidence.
2. **Ambiguity quantification**: The frequency data reveals genuine linguistic ambiguity. A1 can be `=i` (pronoun suffix), `=y`, `i` (pronoun), etc. -- the model captures this distribution.
3. **Lemma linking**: AES entries connect to TLA lemma IDs, enabling downstream lexicographic lookup.
4. **Coverage**: 84,558 unique MdC encodings cover the vast majority of attested hieroglyphic word forms.

### What it cannot do

1. **Context-dependent disambiguation**: The model provides word-level frequency distributions but not sentence-level context. It cannot distinguish `Hr` as a preposition from `Hr` as a noun based on syntactic context.
2. **Character-level OCR correction**: The model maps whole MdC sequences to transliterations. It does not handle character-level OCR errors (misrecognized individual signs).
3. **Transliteration-to-transliteration correction**: The model maps MdC->transliteration, not garbled-transliteration->correct-transliteration. It is most useful when the hieroglyphic encoding is known and the transliteration needs to be validated or generated.

### Validation Results

Tested against well-known sign-transliteration pairs:

| MdC | Expected | Model Best | Match | Notes |
|-----|----------|-----------|-------|-------|
| M17 | j | i | No | AES convention uses `i` not `j` -- convention difference, not error |
| D21 | r | r | Yes | 97.1% relative frequency |
| N35 | n | n | Yes | 83.3% relative frequency |
| R4 | Htp | Htp | Yes | 60.3% (also `Htp-Di`, `Htp.w` variants) |
| R8 | nTr | nTr | Yes | Dominant at 617 occurrences |
| V30 | nb | nb | Yes | Dominant at 5309 occurrences |
| N5 | ra | sw | No | N5 reads `sw` (day/time) more often than `ra` (sun god) in running text |
| M23 X1 L2 X1 | nswt-bjty | nswt-by.ty | Close | Orthographic convention difference |

The "mismatches" reflect genuine transliteration convention differences between traditions (AES/RAMSES vs Manuel de Codage standard), not model errors.

## Integration into Aegyptus

### Current Implementation

The models are loaded as a Python-native `TranslitModel` class in `processing/post_correction/translit_models.py`. No JVM required for lookup.

**Used for:**
- Validating transliterations extracted from OCR
- Suggesting corrections when MdC encoding is known
- Confidence scoring for OCR output

**Not used for** (by design):
- Replacing the rule-based correction stage
- Auto-correcting transliteration text without MdC context

### JVM Wrapper

A subprocess wrapper for `MaReTENeedlemanWunsch.jar` is available at `processing/post_correction/jvm_wrapper.py`. This is needed only if we want to:
- Align new parallel corpora for model expansion
- Retrain models with expanded data

**JVM status on this system:** Java 11 (OpenJDK 11.0.30) is available. The wrapper is operational.

## Retraining Assessment

**Can the models be retrained on expanded corpus data?** Yes, with caveats.

The training pipeline requires:
1. Parallel MdC-encoded hieroglyphic text and corresponding transliteration
2. Running the JAR pipeline: clean -> lexicon -> align -> model

**Our corpus has:**
- 304,617 sentences with transliteration data (from AES, TLA HF, RAMSES imports)
- 19,207 papyri.info records (mostly metadata, limited transliteration)

**Practical assessment:**
- The existing AES+RAMSES combined model already uses the same source corpora we have imported
- Additional transliterations from TLA HF (55,026 Earlier Egyptian + 12,361 Late Egyptian) could expand coverage
- However, this requires the parallel MdC encoding alongside the transliteration, which the TLA HF data provides via the `hieroglyphs` field
- **Recommendation:** Retraining is feasible and could increase coverage by ~30-40%, but should wait until the corpus stabilizes (post-Phase 2 imports)

## License

CC BY 4.0 International -- compatible with the corpus license. Attribution to Jauhiainen & Jauhiainen (2023) required.
