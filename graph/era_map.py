"""Era map — collapses the corpus's 137 free-form period_labels onto 7
canonical chronological levels (L1-L7) plus L0 (Sanctum, hand-authored).

The labels mix German and English, dynasty numbers, pharaoh names, broad
periods, and ranges. We bucket them by first-match regex so a single
source of truth covers them all. Unmapped labels fall to L_UNKNOWN and are
reported by `diagnose()`.

Ordering of rules matters — broader rules come last.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    id: int
    key: str
    name_en: str
    name_de: str
    date_range: str  # approx BCE
    blurb: str


LEVELS: list[Level] = [
    Level(0, "sanctum", "The Sanctum", "Das Sanktum",
          "—", "Nine golden tablets. The articles. Entry point."),
    Level(1, "old_kingdom", "The Old Kingdom", "Altes Reich",
          "c. 2686–2181 BCE",
          "Pyramid Texts, royal mortuary cult, earliest monumental literature."),
    Level(2, "first_intermediate", "The First Intermediate", "Erste Zwischenzeit",
          "c. 2181–2055 BCE",
          "Fragmentation. Coffin Texts emerge. Private tomb autobiography."),
    Level(3, "middle_kingdom", "The Middle Kingdom", "Mittleres Reich",
          "c. 2055–1650 BCE",
          "Classical language. Sinuhe. Loyalistic and wisdom literature."),
    Level(4, "second_intermediate", "The Second Intermediate", "Zweite Zwischenzeit",
          "c. 1650–1550 BCE",
          "Hyksos rule in the north. Theban counter-kingdoms."),
    Level(5, "new_kingdom", "The New Kingdom", "Neues Reich",
          "c. 1550–1069 BCE",
          "Empire. Book of the Dead. Akhenaten. Ramesside monumental texts."),
    Level(6, "late_period", "The Late Period", "Spätzeit",
          "c. 1069–332 BCE",
          "Third Intermediate into Saite–Persian. Archaism. Demotic rises."),
    Level(7, "greco_roman", "The Greco-Roman", "Griechisch-Römische Zeit",
          "c. 332 BCE–395 CE",
          "Ptolemies, Rome. Demotic and Greek. Coptic begins."),
]


LEVEL_BY_ID: dict[int, Level] = {l.id: l for l in LEVELS}


# Rule order: more specific first. Each rule is (pattern, level_id).
# Regex is case-insensitive, matches anywhere in the label.
_RULES: list[tuple[re.Pattern, int]] = [
    # ── L7 Greco-Roman ──────────────────────────────────────────────────
    (re.compile(r"ptolema|makedon|ptolemäer|greek|hellenist", re.I), 7),
    (re.compile(r"\brome?\b|roman|römisch", re.I), 7),
    (re.compile(r"\b(3|4)\.?\s*jhdt\.?\s*v\.?\s*chr", re.I), 7),
    (re.compile(r"\b(3rd|4th)\s+cent", re.I), 7),
    (re.compile(r"coptic", re.I), 7),

    # ── L6 Late Period / Third Intermediate ─────────────────────────────
    (re.compile(r"saite|spätzeit|late\s+period|dritte\s+zwischenzeit|"
                r"third\s+intermediate|kushite|nubian", re.I), 6),
    (re.compile(r"^(21|22|23|24|25|26|27|28|29|30)\.?\s*dyn", re.I), 6),
    (re.compile(r"\b(21st|22nd|23rd|24th|25th|26th|27th|28th|29th|30th)\s+dynasty", re.I), 6),
    (re.compile(r"taharqa|pije|piye|scheschonq|shoshenq|siamun|"
                r"psammetich|psamtek|apries|necho|amasis", re.I), 6),
    (re.compile(r"\b(1|2)\.?\s*hälfte\s*6\.?\s*jhdt\.?\s*v\.?\s*chr", re.I), 6),

    # ── L5 New Kingdom ──────────────────────────────────────────────────
    (re.compile(r"new\s+kingdom|neues\s+reich|amarna|ramesside|ramessid", re.I), 5),
    (re.compile(r"^(18|19|20)\.?\s*dyn", re.I), 5),
    (re.compile(r"\b(18th|19th|20th)\s+dynasty", re.I), 5),
    (re.compile(r"ahmose|amenophis|amenhotep|hatschepsut|hatshepsut|"
                r"thutmosis|thutmose|tutanchamun|tutankhamun|haremhab|horemheb|"
                r"echnaton|akhenaten|ramses|ramesses|merenptah|sethos|seti|"
                r"amenmesse|siptah|tausret", re.I), 5),

    # ── L4 Second Intermediate ──────────────────────────────────────────
    (re.compile(r"second\s+intermediate|zweite\s+zwischenzeit|hyksos", re.I), 4),
    (re.compile(r"^(13|14|15|16|17)[\s\./]", re.I), 4),

    # ── L3 Middle Kingdom ───────────────────────────────────────────────
    (re.compile(r"middle\s+kingdom|mittleres\s+reich|"
                r"late\s+middle\s+kingdom", re.I), 3),
    (re.compile(r"^(11|12)\.?\s*dyn", re.I), 3),
    (re.compile(r"amenemhet|amenemhat|sesostris|senwosret|"
                r"sebekhotep|sobekhotep|mentuhotep", re.I), 3),
    # "11. Dyn., 2. Hälfte" → L3 (after unification rule matches above)

    # ── L2 First Intermediate ───────────────────────────────────────────
    (re.compile(r"first\s+intermediate|erste\s+zwischenzeit|"
                r"herakleopol", re.I), 2),
    (re.compile(r"^(7|8|9|10)\.?\s*dyn", re.I), 2),
    (re.compile(r"9\./10\.\s*dyn", re.I), 2),
    (re.compile(r"6\.?\s*dyn\.?\s*nach\s*pepi", re.I), 2),
    (re.compile(r"late\s+old\s+kingdom.*first\s+intermediate", re.I), 2),
    (re.compile(r"intef\s*(ii|iii|wahanch|nachtnebtepnefer)", re.I), 2),

    # ── L1 Old Kingdom ──────────────────────────────────────────────────
    (re.compile(r"old\s+kingdom|altes\s+reich|early\s+dynastic|"
                r"frühdynastisch|archaic", re.I), 1),
    (re.compile(r"^(1|2|3|4|5|6)\.?\s*dyn", re.I), 1),
    (re.compile(r"djoser|netjeri[\s-]?chet|snofru|cheops|khufu|djedefre|"
                r"chefren|khafre|mykerinos|menkaure|userkaf|sahure|"
                r"neferirkare|niuserre|menkauhor|djedkare|unas|teti|"
                r"pepi|merenre|schepseskaf|userkare|nebka|sanacht", re.I), 1),
]


def map_label(label: str) -> int:
    """Return level id 1-7 for a period_label, or 0 if unmappable.

    0 is not "Sanctum" here — it's the sentinel for "no chronological bucket
    known." The Sanctum (L0) is hand-authored and does not contain corpus
    texts. Unmapped labels should be audited.
    """
    if not label:
        return 0
    s = label.strip()
    for rx, lvl in _RULES:
        if rx.search(s):
            return lvl
    return 0


def labels_for_level(all_labels: list[str], level_id: int) -> list[str]:
    """Return the subset of `all_labels` that map to `level_id`."""
    return [l for l in all_labels if map_label(l) == level_id]


def diagnose(all_labels: list[str]) -> dict[int, list[str]]:
    """Bucket every label; id 0 holds unmapped."""
    out: dict[int, list[str]] = {i: [] for i in range(8)}
    for l in all_labels:
        out[map_label(l)].append(l)
    return out


if __name__ == "__main__":
    # Self-audit: run against live DB, print buckets + unmapped warnings.
    import sys
    from inference.tools._db import get_conn, put_conn

    c = get_conn()
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT period_label, COUNT(*) FROM texts "
            "WHERE period_label IS NOT NULL AND period_label <> '' "
            "GROUP BY period_label"
        )
        rows = cur.fetchall()
    finally:
        put_conn(c)

    by_level: dict[int, list[tuple[str, int]]] = {i: [] for i in range(8)}
    for label, n in rows:
        by_level[map_label(label)].append((label, n))

    for lvl in range(1, 8):
        entries = sorted(by_level[lvl], key=lambda x: -x[1])
        total = sum(n for _, n in entries)
        L = LEVEL_BY_ID[lvl]
        print(f"L{lvl} {L.name_en}: {total} texts across {len(entries)} labels")
        for label, n in entries[:5]:
            print(f"    {n:>6}  {label}")
        if len(entries) > 5:
            print(f"    … +{len(entries) - 5} more")
        print()

    unmapped = sorted(by_level[0], key=lambda x: -x[1])
    if unmapped:
        print(f"UNMAPPED ({sum(n for _, n in unmapped)} texts):")
        for label, n in unmapped:
            print(f"    {n:>6}  {label!r}")
        sys.exit(1)
    else:
        print("All labels mapped.")
