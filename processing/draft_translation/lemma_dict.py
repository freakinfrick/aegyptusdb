"""Build a lemma dictionary from corpus data for translation prompts.

Extracts lemma meanings from existing sentence tokens (AES and ORAEC data
carry cotext_translation fields) and from TLA HF glossing data.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from core.models import SessionLocal

logger = logging.getLogger(__name__)


class LemmaDictionary:
    """Maps AED lemma IDs to known meanings extracted from corpus tokens."""

    def __init__(self) -> None:
        self._entries: dict[str, LemmaEntry] = {}

    @property
    def size(self) -> int:
        return len(self._entries)

    def get(self, lemma_id: str) -> Optional[LemmaEntry]:
        return self._entries.get(str(lemma_id))

    def lookup_meaning(self, lemma_id: str) -> Optional[str]:
        """Return the best single-line meaning for a lemma ID."""
        entry = self.get(str(lemma_id))
        if entry is None:
            return None
        return entry.best_meaning()

    @classmethod
    def build_from_corpus(cls, session: Optional[Session] = None, limit: int = 50000) -> LemmaDictionary:
        """Build dictionary by scanning sentence tokens in the corpus.

        Extracts meanings from:
        - AES/ORAEC tokens: cotext_translation field (German, but usable)
        - TLA HF tokens: glossing field
        - All sources: lemma_form field for transliteration form
        """
        own_session = session is None
        if own_session:
            session = SessionLocal()

        try:
            return cls._scan_tokens(session, limit)
        finally:
            if own_session:
                session.close()

    @classmethod
    def _scan_tokens(cls, session: Session, limit: int) -> LemmaDictionary:
        d = cls()
        counts: dict[str, int] = defaultdict(int)

        # Query tokens JSONB from sentences that have token data
        # We process in batches to avoid loading everything into memory
        batch_size = 1000
        offset = 0
        total_processed = 0

        while total_processed < limit:
            rows = session.execute(
                sa_text("""
                    SELECT tokens, source FROM sentences
                    WHERE tokens IS NOT NULL
                    ORDER BY id
                    LIMIT :batch OFFSET :offset
                """),
                {"batch": batch_size, "offset": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                tokens = row[0]  # JSONB -> Python list
                source = row[1]
                if not isinstance(tokens, list):
                    continue
                for tok in tokens:
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    if not lemma_id:
                        continue

                    lemma_id = str(lemma_id)
                    counts[lemma_id] += 1

                    if lemma_id not in d._entries:
                        d._entries[lemma_id] = LemmaEntry(lemma_id=lemma_id)

                    entry = d._entries[lemma_id]

                    # Extract lemma form (transliteration)
                    lemma_form = tok.get("lemma_form")
                    if lemma_form and not entry.lemma_form:
                        entry.lemma_form = lemma_form

                    # Extract POS
                    pos = tok.get("pos") or tok.get("upos")
                    if pos and not entry.pos:
                        entry.pos = pos

                    # Extract meaning from cotext_translation (AES/ORAEC - German)
                    cotext = tok.get("cotext_translation")
                    if cotext and cotext not in entry.meanings_de:
                        entry.meanings_de.add(cotext)

                    # Extract glossing (TLA HF)
                    glossing = tok.get("glossing")
                    if glossing and glossing not in entry.glossings:
                        entry.glossings.add(glossing)

            offset += batch_size
            total_processed += len(rows)

        logger.info("Built lemma dictionary: %d entries from %d sentence batches", d.size, total_processed)
        return d


class LemmaEntry:
    """A single lemma with accumulated meanings from corpus data."""

    def __init__(self, lemma_id: str) -> None:
        self.lemma_id = lemma_id
        self.lemma_form: Optional[str] = None
        self.pos: Optional[str] = None
        self.meanings_de: set[str] = set()
        self.glossings: set[str] = set()

    def best_meaning(self) -> str:
        """Return a compact meaning string combining available info."""
        parts = []
        if self.lemma_form:
            parts.append(self.lemma_form)

        # Prefer German meanings (most abundant in corpus)
        if self.meanings_de:
            # Take the shortest non-bracket meaning as primary
            clean = [m for m in self.meanings_de if not m.startswith("[")]
            if clean:
                parts.append(min(clean, key=len))
            elif self.meanings_de:
                parts.append(next(iter(self.meanings_de)))

        if self.glossings:
            parts.append(f"({next(iter(self.glossings))})")

        if self.pos:
            parts.append(f"[{self.pos}]")

        return " | ".join(parts) if parts else self.lemma_id
