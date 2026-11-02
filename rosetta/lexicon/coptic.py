"""CopticLinker — link Egyptian lemmas to Coptic cognates from corpus data."""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CopticLinker:
    """Link Egyptian lemmas to Coptic cognates from Coptic Scriptorium data."""

    def __init__(self, session: Session):
        self.session = session

    def find_cognates(self, batch_size: int = 1000) -> dict[str, list[dict[str, str | None]]]:
        """Query Coptic Scriptorium sentences for cognate data.

        1. Find sentences where source = 'coptic_scriptorium' with tokens
        2. Extract Coptic lemma forms from tokens
        3. For sentences with EN translations, record the meaning
        4. Build cognate entries: {form, lemma, meaning_en, source}
        5. Group by Egyptian lemma_id where possible (form-based matching)

        Return {lemma_id_or_form: [cognate_entries]}.
        """
        # Step 1: Gather Coptic token data with meanings
        coptic_entries: dict[str, list[dict[str, str | None]]] = defaultdict(list)
        offset = 0

        while True:
            rows = self.session.execute(
                sa_text("""
                    SELECT tokens, translation->>'en' AS en FROM sentences
                    WHERE source = 'coptic_scriptorium'
                      AND tokens IS NOT NULL
                    ORDER BY id
                    LIMIT :batch OFFSET :offset
                """),
                {"batch": batch_size, "offset": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                tokens = row[0]
                en_text = row[1]
                if not isinstance(tokens, list):
                    continue

                for tok in tokens:
                    lemma = tok.get("lemma")
                    form = tok.get("form") or tok.get("written_form")
                    if not lemma and not form:
                        continue

                    key = lemma or form
                    entry = {
                        "form": form,
                        "lemma": lemma,
                        "source": "coptic_scriptorium",
                    }
                    if en_text:
                        entry["meaning_en"] = en_text

                    # Deduplicate by form+lemma combo
                    existing_keys = {
                        (e.get("form"), e.get("lemma"))
                        for e in coptic_entries[key]
                    }
                    if (form, lemma) not in existing_keys:
                        coptic_entries[key].append(entry)

            offset += batch_size

        # Step 2: Try to match Coptic forms to Egyptian lemma_ids
        # Build Egyptian form->lemma_id map from lemmata table
        egypt_form_map = self._build_form_map()

        result: dict[str, list[dict[str, str | None]]] = {}
        matched = 0
        for coptic_key, entries in coptic_entries.items():
            # Try form-based matching against Egyptian lemmata
            lemma_id = egypt_form_map.get(coptic_key)
            target_key = lemma_id if lemma_id else coptic_key
            if lemma_id:
                matched += 1
            if target_key not in result:
                result[target_key] = []
            result[target_key].extend(entries)

        logger.info(
            "Found %d Coptic cognate groups (%d matched to Egyptian lemmas)",
            len(result), matched,
        )
        return result

    def _build_form_map(self) -> dict[str, str]:
        """Build mapping from lemma form -> lemma id from lemmata table.
        Used for fuzzy form-based matching between Coptic and Egyptian."""
        rows = self.session.execute(
            sa_text("SELECT id, form FROM lemmata WHERE form IS NOT NULL")
        ).fetchall()
        form_map: dict[str, str] = {}
        for row in rows:
            form_map[row[1]] = row[0]
        return form_map
