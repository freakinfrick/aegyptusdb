#!/usr/bin/env python3
"""Quality gate for machine-translated English sentences.

Reads translation output JSON files, filters to 100% English,
saves passing translations to the sentences table.

Usage:
    python scripts/translation_gate.py /tmp/aegyptus_v3/out_*.json
    python scripts/translation_gate.py --dry-run /tmp/aegyptus_v3/out_00.json
"""
import json
import re
import sys
from pathlib import Path

# German characters
_UMLAUTS = re.compile(r'[äöüÄÖÜß]')

# German words (comprehensive)
_GERMAN_WORDS = re.compile(
    r'\b('
    # Articles, pronouns, prepositions, conjunctions
    # Only words that are UNAMBIGUOUSLY German (not valid English)
    r'werden|werde|wurde|und|des|dem|den|sind|wird|nicht'
    r'|eine|eines|einem|einen|einer|sich|für|auch|oder'
    r'|aber|wenn|dass|noch|nur|über|zwischen|neben|hinter'
    r'|soll|seien|hatten|waren|worden|geworden|sollte|könnte'
    r'|dieser|diese|dieses|diesem|diesen|welcher|welche|welches'
    r'|seine|seinem|seinen|seiner|ihre|ihrem|ihren|ihrer'
    # Common verbs and participles
    r'|gemacht|gegeben|gesalbt|getrunken|gewaschen|zerrieben|geseiht'
    r'|gegossen|gebacken|gekocht|geschlagen|geworfen|getötet|genommen'
    r'|gebracht|gefunden|gesehen|gesagt|gestellt|entstanden|eingesalbt'
    r'|zerkleinert|zerstoßen|vermischt|eingegossen|eingeschlossen'
    # Common nouns agents keep leaving in
    r'|Heilmittel|Hautentzündung|Krankheit|Spruch|Rezitieren|Begleiter'
    r'|Honig|Gummi|Salbe|Binde|Schlange|Kraut|Opfer|Wunde|Gefäß'
    r'|Vorsteher|Truppe|Schmerzstoffe|Partikel|Konditionalsatz'
    r'|Morgen|Abend|Stunde|Mittag|Tagesanbruch|Mitternacht'
    r'|Schwert|Auge|Fleisch|Mehl|Harfe|Hund|Steinbock|Zyperngras'
    # 'am', 'an', 'in' omitted — all valid English; caused massive false positives
    # Numbers
    r'|vier|drei|zwei|fünf|sechs|sieben|acht|neun|zehn'
    # Misc
    r'|Tage|lang|Zeit|Mal|sonst|denn|weil|damit|ob|als|wie'
    r'|beim|zum|zur|vom|Dja|Oipe'
    r'|hierauf|hierbei|davon|dabei|darum|darin|darauf|daher'
    r')\b', re.IGNORECASE
)

# German suffixes on words
_GERMAN_SUFFIXES = re.compile(
    r'\b\w+(?:ierung|lichen|liches|licher|ungen|heiten|keiten)\b', re.IGNORECASE
)

# German phonetic patterns — only clear German compounds, not English words with sch
_GERMAN_PHONETIC = re.compile(
    r'\b\w+(?:schaft|schlag|schrift|schlecht|schnitt|schwer|spruch|stein)\w*\b', re.IGNORECASE
)

# German past tense endings (XYZte where XYZ is not common English)
_GERMAN_PAST = re.compile(
    r'\b\w{3,}(?:rte|hte|gte|lte|kte|fte|pte|bte|dte|mte|nte|wte)\b'
)
# Egyptian names that look like German past tense
_EGYPTIAN_NAMES_OK = {
    'harachte', 'sekhemkhet', 'neferirkare', 'amenemhet', 'amenhotep',
    'thutmose', 'hatshepsut', 'akhenaten', 'nefertiti', 'horemheb',
    'merenptah', 'siptah', 'tausret', 'ramessesnakht',
}

_ENGLISH_PAST_OK = {
    'created', 'wanted', 'started', 'granted', 'treated', 'hunted', 'rested',
    'lasted', 'listed', 'posted', 'hosted', 'wasted', 'tasted', 'existed',
    'departed', 'imported', 'exported', 'reported', 'supported', 'exalted',
    'consulted', 'insulted', 'resulted', 'devoted', 'promoted', 'denoted',
    'appointed', 'anointed', 'pointed', 'counted', 'mounted', 'accounted',
    'accepted', 'expected', 'directed', 'protected', 'connected', 'collected',
    'selected', 'erected', 'afflicted', 'inflicted', 'restricted', 'predicted',
    'instructed', 'constructed', 'conducted', 'corrupted', 'disrupted', 'erupted',
    'exhausted', 'detested', 'manifested', 'suggested', 'congested', 'arrested',
    'contested', 'attested', 'invested', 'harvested', 'requested', 'molested',
    'contrasted', 'illustrated', 'decorated', 'separated', 'generated', 'operated',
    'dedicated', 'complicated', 'liberated', 'concentrated', 'penetrated',
    'demonstrated', 'celebrated', 'tolerated', 'dominated', 'nominated', 'estimated',
    'investigated', 'eliminated', 'illuminated', 'terminated', 'fascinated',
    'translated', 'populated', 'situated', 'evaluated', 'cultivated', 'motivated',
}

# Top English function words — if 5+ word sentence has NONE, it's not prose
_ENGLISH_STRUCTURE = {
    'the', 'a', 'an', 'of', 'in', 'to', 'for', 'with', 'by', 'on', 'at',
    'from', 'is', 'are', 'was', 'were', 'has', 'have', 'had', 'shall', 'will',
    'may', 'can', 'who', 'which', 'that', 'this', 'his', 'her', 'its', 'their',
    'your', 'my', 'he', 'she', 'it', 'they', 'you', 'i', 'we', 'not', 'no',
    'be', 'do', 'if', 'and', 'but', 'or', 'so', 'as', 'into', 'upon', 'against',
    'before', 'after', 'over', 'under', 'through', 'about', 'between',
}


def check_translation(text: str) -> tuple[bool, str]:
    """Returns (passes, reason)."""
    if not text or len(text.strip()) < 8:
        return False, "too_short"

    if _UMLAUTS.search(text):
        return False, "umlauts"

    if _GERMAN_WORDS.search(text):
        return False, "german_word"

    if _GERMAN_SUFFIXES.search(text):
        return False, "german_suffix"

    if _GERMAN_PHONETIC.search(text):
        return False, "german_phonetic"

    # Check German past tense
    for m in _GERMAN_PAST.finditer(text):
        word = m.group().lower()
        if word not in _ENGLISH_PAST_OK and word not in _EGYPTIAN_NAMES_OK:
            return False, f"german_past:{word}"

    # Prose structure check — only for longer sentences
    words = text.split()
    if len(words) >= 8:
        lower_set = {w.lower().rstrip('.,;:!?"\'') for w in words}
        if not (lower_set & _ENGLISH_STRUCTURE):
            return False, "no_structure"

    # Fragment check — allow 2-word phrases (Egyptian fragments are often short)
    if len(words) < 2:
        return False, "fragment"

    # Content check — mostly brackets/punctuation
    stripped = re.sub(r'[\[\]().,;:!?\-\s…⸢⸣〈〉$\"\']+', '', text)
    if len(stripped) < 8:
        return False, "no_content"

    return True, "pass"


def main():
    dry_run = "--dry-run" in sys.argv
    files = [f for f in sys.argv[1:] if not f.startswith("--")]

    if not files:
        print("Usage: python scripts/translation_gate.py [--dry-run] <out_files...>")
        sys.exit(1)

    # Lazy imports for DB
    if not dry_run:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from core.models import SessionLocal, Sentence
        from sqlalchemy.orm.attributes import flag_modified
        session = SessionLocal()

    total = 0
    passed = 0
    failed = 0
    reasons = {}
    saved = 0

    for fpath in sorted(files):
        if not Path(fpath).exists():
            continue
        data = json.loads(Path(fpath).read_text())
        file_pass = 0
        file_total = len(data)

        for entry in data:
            total += 1
            tr = entry.get("translation", "").strip()
            ok, reason = check_translation(tr)

            if ok:
                passed += 1
                file_pass += 1
                if not dry_run:
                    sent = session.get(Sentence, entry["id"])
                    if sent:
                        current = dict(sent.translation) if sent.translation else {}
                        if "en" not in current:
                            current["en"] = tr
                            sent.translation = current
                            flag_modified(sent, "translation")
                            saved += 1
            else:
                failed += 1
                reasons[reason] = reasons.get(reason, 0) + 1

        pct = 100 * file_pass // file_total if file_total else 0
        print(f"  {Path(fpath).name}: {file_pass}/{file_total} ({pct}%)")

    if not dry_run and saved:
        session.commit()
        session.close()

    print(f"\n{'DRY RUN — ' if dry_run else ''}Total: {total} | Pass: {passed} | Fail: {failed} | Saved: {saved}")
    if reasons:
        print("Rejection reasons:")
        for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {r}: {c}")

    sys.exit(0 if passed > 0 else 2)


if __name__ == "__main__":
    main()
