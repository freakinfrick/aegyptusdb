"""Shelfmark normalizer for entity resolution.

Normalizes variant shelfmark and conventional name formats so that
"P. Berlin 3022", "pBerlin 3022", "Papyrus Berlin 3022", and "Berlin 3022"
all resolve to the same normalized form: "berlin 3022".

Rules:
  1. Strip common prefixes: P., p., p, Papyrus, O., o., Ostracon, Ostrakon
  2. Normalize whitespace (collapse multiple spaces, strip leading/trailing)
  3. Lowercase for comparison
  4. Strip periods that aren't part of decimal numbers
"""

import re

# Common prefixes to strip, ordered by length (longest first to avoid partial matches)
_PREFIXES = [
    r"Papyrus\b",
    r"papyrus\b",
    r"Ostracon\b",
    r"ostracon\b",
    r"Ostrakon\b",
    r"ostrakon\b",
    r"Stela\b",
    r"stela\b",
    r"Stele\b",
    r"stele\b",
    r"P\.\s*",
    r"p\.\s*",
    r"O\.\s*",
    r"o\.\s*",
    r"[pP](?=[A-Z])",  # Bare p/P immediately followed by uppercase (e.g., pBerlin, PBerlin)
    r"[oO](?=[A-Z])",  # Bare o/O immediately followed by uppercase (e.g., oCairo, OCairo)
]

# Compiled pattern: match any prefix at start of string
_PREFIX_PATTERN = re.compile(
    r"^\s*(?:" + "|".join(_PREFIXES) + r")\s*",
)


def normalize_shelfmark(raw: str) -> str:
    """Normalize a shelfmark string for comparison.

    >>> normalize_shelfmark("P. Berlin 3022")
    'berlin 3022'
    >>> normalize_shelfmark("Papyrus Berlin 3022")
    'berlin 3022'
    >>> normalize_shelfmark("pBerlin 3022")
    'berlin 3022'
    >>> normalize_shelfmark("O. Cairo 25338")
    'cairo 25338'
    >>> normalize_shelfmark("Ostracon DM 118")
    'dm 118'
    """
    if not raw:
        return ""

    text = raw.strip()

    # Strip known prefixes
    text = _PREFIX_PATTERN.sub("", text)

    # Remove standalone periods (but keep those in numbers like "3.5")
    text = re.sub(r"(?<!\d)\.(?!\d)", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Lowercase
    text = text.lower()

    return text


def normalize_conventional_name(raw: str) -> str:
    """Normalize a conventional text name for fuzzy matching.

    Less aggressive than shelfmark normalization -- preserves more structure
    but lowercases and normalizes whitespace.

    >>> normalize_conventional_name("Tale of Sinuhe")
    'tale of sinuhe'
    >>> normalize_conventional_name("Die Geschichte des Sinuhe")
    'die geschichte des sinuhe'
    """
    if not raw:
        return ""

    text = raw.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.lower()

    return text
