"""Witness dossier — all available evidence for translating a sentence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

# Type alias for a thoth_lexicon row dict (JSONB fields are arbitrary JSON)
LexRow = dict[str, Any]

logger = logging.getLogger(__name__)


@dataclass
class TokenWitness:
    """Evidence for a single token from the Thoth Lexicon."""

    lemma_id: str
    form: str
    en_gloss: Optional[str] = None
    de_gloss: Optional[str] = None
    pos: Optional[str] = None
    hiero: Optional[str] = None
    coptic_cognate: Optional[str] = None


@dataclass
class ParallelExample:
    """A similar already-translated sentence."""

    sentence_id: int
    canonical_id: str
    transliteration: str
    translation_en: Optional[str] = None
    translation_de: Optional[str] = None
    similarity_score: float = 0.0


@dataclass
class WitnessDossier:
    """All available evidence for translating a single sentence."""

    sentence_id: int
    canonical_id: str
    transliteration: str
    tokens: list[dict[str, str | None]] = field(default_factory=list)
    token_witnesses: list[TokenWitness] = field(default_factory=list)
    german_translation: Optional[str] = None
    german_interlinear: Optional[str] = None
    parallel_examples: list[ParallelExample] = field(default_factory=list)
    period: Optional[str] = None
    text_type: Optional[str] = None
    source: str = ""
    pre_confidence: str = "low"

    @property
    def has_german(self) -> bool:
        return self.german_translation is not None

    @property
    def token_coverage(self) -> float:
        """Fraction of tokens that have en_gloss or de_gloss."""
        if not self.token_witnesses:
            return 0.0
        covered = sum(1 for tw in self.token_witnesses if tw.en_gloss or tw.de_gloss)
        return covered / len(self.token_witnesses)

    def format_token_glosses(self) -> str:
        """Format token witnesses as human-readable gloss lines for LLM prompt."""
        lines = []
        for tw in self.token_witnesses:
            parts = [tw.form]
            if tw.lemma_id:
                parts.append(f"(lemma {tw.lemma_id})")
            glosses = []
            if tw.en_gloss:
                glosses.append(tw.en_gloss)
            if tw.de_gloss:
                glosses.append(f"DE: {tw.de_gloss}")
            if tw.pos:
                glosses.append(f"[{tw.pos}]")
            if tw.coptic_cognate:
                glosses.append(f"Coptic: {tw.coptic_cognate}")
            parts.append(": " + " | ".join(glosses) if glosses else ": [unknown]")
            lines.append("  - " + " ".join(parts))
        return "\n".join(lines)

    def format_parallels(self) -> str:
        """Format parallel examples for LLM prompt."""
        lines = []
        for i, px in enumerate(self.parallel_examples, 1):
            lines.append(
                f'  {i}. "{px.translation_en}" '
                f"({px.canonical_id}, similarity={px.similarity_score:.2f})"
            )
        return "\n".join(lines)



def _best_en_gloss(lex: LexRow) -> Optional[str]:
    """Pick best English gloss. Priority: definition_en > glosses_en > glosses_bridged_en."""
    defn = lex.get("definition_en")
    if defn:
        return str(defn)
    glosses_en = lex.get("glosses_en")
    if glosses_en and isinstance(glosses_en, dict):
        first = next(iter(glosses_en), None)
        if first:
            return str(first)
    glosses_bridged = lex.get("glosses_bridged_en")
    if glosses_bridged and isinstance(glosses_bridged, dict):
        first = next(iter(glosses_bridged), None)
        if first:
            return str(first)
    return None


def _best_de_gloss(lex: LexRow) -> Optional[str]:
    """Pick best German gloss. Priority: definition_de > glosses_de."""
    defn = lex.get("definition_de")
    if defn:
        return str(defn)
    glosses_de = lex.get("glosses_de")
    if glosses_de and isinstance(glosses_de, dict):
        first = next(iter(glosses_de), None)
        if first:
            return str(first)
    return None


def _first_coptic(cognates: list | dict | str | None) -> Optional[str]:
    """Extract first Coptic cognate string from JSONB field."""
    if isinstance(cognates, list) and cognates:
        c = cognates[0]
        return c if isinstance(c, str) else str(c)
    if isinstance(cognates, dict) and cognates:
        return next(iter(cognates), None)
    return None


def _first_hiero(hieroglyphs: list | str | None) -> Optional[str]:
    """Extract first hieroglyph string from JSONB field."""
    if isinstance(hieroglyphs, str):
        return hieroglyphs
    if isinstance(hieroglyphs, list) and hieroglyphs:
        h = hieroglyphs[0]
        return h if isinstance(h, str) else str(h)
    return None



def assemble_dossier(sentence_id: int, session: Session) -> WitnessDossier:
    """Assemble a complete WitnessDossier for a given sentence."""

    from .index import InvertedIndexBuilder

    # 1. Load sentence
    sent_row = session.execute(
        sa_text(
            "SELECT id, canonical_id, transliteration, tokens, translation, source "
            "FROM sentences WHERE id = :sid"
        ),
        {"sid": sentence_id},
    ).fetchone()

    if not sent_row:
        raise ValueError(f"Sentence {sentence_id} not found")

    sid, canonical_id, translit, tokens, translation, source = sent_row
    tokens = tokens or []
    translation = translation or {}

    # 2. Load parent text metadata
    text_row = session.execute(
        sa_text(
            "SELECT period_label, text_type FROM texts WHERE canonical_id = :cid"
        ),
        {"cid": canonical_id},
    ).fetchone()

    period = text_row[0] if text_row else None
    text_type = text_row[1] if text_row else None

    # 3. Collect unique lemma IDs from tokens
    lemma_ids: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        lid = tok.get("lemmaID") or tok.get("lemma_id")
        if lid:
            # Normalize: tokens use bare numeric IDs, lexicon uses 'tla' prefix
            lid = lid if lid.startswith('tla') else f'tla{lid}'
            if lid not in seen:
                lemma_ids.append(lid)
                seen.add(lid)

    # 4. Batch lookup from thoth_lexicon
    lex_map: dict[str, LexRow] = {}
    if lemma_ids:
        lex_rows = session.execute(
            sa_text(
                "SELECT lemma_id, definition_en, definition_de, "
                "glosses_en, glosses_de, glosses_bridged_en, "
                "pos, hieroglyphs, coptic_cognates "
                "FROM thoth_lexicon WHERE lemma_id = ANY(:ids)"
            ),
            {"ids": lemma_ids},
        ).fetchall()

        for lr in lex_rows:
            lex_map[lr[0]] = {
                "definition_en": lr[1],
                "definition_de": lr[2],
                "glosses_en": lr[3],
                "glosses_de": lr[4],
                "glosses_bridged_en": lr[5],
                "pos": lr[6],
                "hieroglyphs": lr[7],
                "coptic_cognates": lr[8],
            }

    # 5. Build TokenWitness list (one per token with a lemma)
    token_witnesses: list[TokenWitness] = []
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        lid = tok.get("lemmaID") or tok.get("lemma_id")
        if not lid:
            continue
        lid = lid if lid.startswith('tla') else f'tla{lid}'
        form = tok.get("written_form") or tok.get("form") or tok.get("translit") or ""
        lex = lex_map.get(lid, {})
        token_witnesses.append(
            TokenWitness(
                lemma_id=lid,
                form=form,
                en_gloss=_best_en_gloss(lex),
                de_gloss=_best_de_gloss(lex),
                pos=lex.get("pos") or tok.get("pos"),
                hiero=_first_hiero(lex.get("hieroglyphs")),
                coptic_cognate=_first_coptic(lex.get("coptic_cognates")),
            )
        )

    # 6. German translation + interlinear
    german_translation = translation.get("de")
    german_interlinear = None
    interlinear_parts = []
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        ct = tok.get("cotext_translation")
        if ct:
            interlinear_parts.append(ct)
    if interlinear_parts:
        german_interlinear = " ".join(interlinear_parts)

    # 7. Parallel examples
    idx = InvertedIndexBuilder(session)
    parallels_raw = idx.find_parallel_sentences(sentence_id, top_k=5)
    parallel_examples = [
        ParallelExample(
            sentence_id=p["sentence_id"],
            canonical_id=p["canonical_id"],
            transliteration=p["transliteration"] or "",
            translation_en=p["translation_en"],
            translation_de=p["translation_de"],
            similarity_score=p["similarity_score"],
        )
        for p in parallels_raw
    ]

    # 8. Estimate pre-confidence
    has_de = german_translation is not None
    dossier = WitnessDossier(
        sentence_id=sid,
        canonical_id=canonical_id,
        transliteration=translit or "",
        tokens=tokens,
        token_witnesses=token_witnesses,
        german_translation=german_translation,
        german_interlinear=german_interlinear,
        parallel_examples=parallel_examples,
        period=period,
        text_type=text_type,
        source=source or "",
    )

    coverage = dossier.token_coverage
    if has_de and coverage > 0.5:
        dossier.pre_confidence = "high"
    elif has_de or coverage > 0.5:
        dossier.pre_confidence = "medium"
    else:
        dossier.pre_confidence = "low"

    return dossier
