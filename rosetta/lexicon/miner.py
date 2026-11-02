"""TokenMiner — extract multilingual glosses from corpus token annotations."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Unicode Egyptian Hieroglyphs block: U+13000–U+1342F
_HIERO_RE = re.compile(r"[\U00013000-\U0001342F]")

# English stopwords for co-occurrence filtering
_EN_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "to", "and", "for", "with", "that", "this", "it", "its",
    "he", "she", "his", "her", "him", "they", "them", "their",
    "on", "at", "by", "from", "as", "or", "not", "but", "if", "so",
    "who", "which", "what", "when", "where", "how", "all", "each",
    "has", "have", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "no", "nor", "i", "my",
    "you", "your", "we", "our", "me", "us",
})

# Simple word tokenizer
_WORD_RE = re.compile(r"[a-zA-Z]+(?:'[a-zA-Z]+)?")


class TokenMiner:
    """Extract multilingual glosses from corpus token annotations."""

    def __init__(self, session: Session):
        self.session = session

    def mine_german_glosses(self, batch_size: int = 1000) -> dict[str, dict[str, int]]:
        """Scan all sentences with tokens. For each token with lemmaID,
        collect cotext_translation (ORAEC/AES) and translation_de (AED-TEI).
        Return {lemma_id: {german_gloss: frequency_count}}.
        """
        result: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        offset = 0

        while True:
            rows = self.session.execute(
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
                tokens = row[0]
                if not isinstance(tokens, list):
                    continue
                for tok in tokens:
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    if not lemma_id:
                        continue
                    lemma_id = str(lemma_id)

                    # ORAEC/AES pattern
                    cotext = tok.get("cotext_translation")
                    if cotext:
                        result[lemma_id][cotext] += 1

                    # AED-TEI pattern
                    trans_de = tok.get("translation_de")
                    if trans_de:
                        result[lemma_id][trans_de] += 1

            offset += batch_size
            logger.debug("mine_german_glosses: processed offset %d", offset)

        logger.info("Mined German glosses for %d lemmas", len(result))
        return dict(result)

    def mine_english_contexts(self, batch_size: int = 1000) -> dict[str, dict[str, float]]:
        """For sentences with EN translation AND token lemmaIDs,
        use co-occurrence to associate lemmaIDs with English terms.

        Return {lemma_id: {english_term: normalized_score}}.
        """
        raw_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        offset = 0

        while True:
            rows = self.session.execute(
                sa_text("""
                    SELECT tokens, translation->>'en' AS en FROM sentences
                    WHERE tokens IS NOT NULL AND translation ? 'en'
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
                if not isinstance(tokens, list) or not en_text:
                    continue

                # Extract lemma IDs from tokens
                lemma_ids = set()
                for tok in tokens:
                    lid = tok.get("lemmaID") or tok.get("lemma_id")
                    if lid:
                        lemma_ids.add(str(lid))

                if not lemma_ids:
                    continue

                # Tokenize English, filter stopwords
                en_words = {
                    w.lower()
                    for w in _WORD_RE.findall(en_text)
                    if w.lower() not in _EN_STOPWORDS and len(w) > 1
                }

                # Credit each lemma with co-occurring English words
                for lid in lemma_ids:
                    for word in en_words:
                        raw_counts[lid][word] += 1

            offset += batch_size
            logger.debug("mine_english_contexts: processed offset %d", offset)

        # Normalize scores per lemma (divide by max)
        result: dict[str, dict[str, float]] = {}
        for lid, word_counts in raw_counts.items():
            if not word_counts:
                continue
            max_count = max(word_counts.values())
            result[lid] = {
                word: count / max_count
                for word, count in word_counts.items()
            }

        logger.info("Mined English contexts for %d lemmas", len(result))
        return result

    def mine_pos_distribution(self, batch_size: int = 1000) -> dict[str, dict[str, int]]:
        """Scan tokens to build POS distribution per lemma.
        Return {lemma_id: {pos_tag: count}}.
        """
        result: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        offset = 0

        while True:
            rows = self.session.execute(
                sa_text("""
                    SELECT tokens FROM sentences
                    WHERE tokens IS NOT NULL
                    ORDER BY id
                    LIMIT :batch OFFSET :offset
                """),
                {"batch": batch_size, "offset": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                tokens = row[0]
                if not isinstance(tokens, list):
                    continue
                for tok in tokens:
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    if not lemma_id:
                        continue
                    pos = tok.get("pos") or tok.get("upos")
                    if pos:
                        result[str(lemma_id)][pos] += 1

            offset += batch_size

        logger.info("Mined POS distribution for %d lemmas", len(result))
        return dict(result)

    def mine_hieroglyphs(self, batch_size: int = 1000) -> dict[str, list[str]]:
        """Extract Unicode hieroglyphic forms from tokens.
        Only collect values containing actual Unicode hieroglyphs (U+13000-U+1342F).
        Return {lemma_id: [unique_hieroglyphic_forms]}.
        """
        result: dict[str, set[str]] = defaultdict(set)
        offset = 0

        while True:
            rows = self.session.execute(
                sa_text("""
                    SELECT tokens FROM sentences
                    WHERE tokens IS NOT NULL
                    ORDER BY id
                    LIMIT :batch OFFSET :offset
                """),
                {"batch": batch_size, "offset": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                tokens = row[0]
                if not isinstance(tokens, list):
                    continue
                for tok in tokens:
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    if not lemma_id:
                        continue

                    for field in ("written_form", "mdc"):
                        val = tok.get(field)
                        if val and _HIERO_RE.search(val):
                            result[str(lemma_id)].add(val)

            offset += batch_size

        # Convert sets to sorted lists
        out = {lid: sorted(forms) for lid, forms in result.items()}
        logger.info("Mined hieroglyphs for %d lemmas", len(out))
        return out
