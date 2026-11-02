"""AED Lemma Dictionary importer.

Parses dictionary.xml from the AED-TEI corpus and imports ~35K Egyptian
lemma entries into the lemmata table.

Source: data/upstream/aed_tei/files/dictionary.xml
License: CC BY-SA 4.0
"""

import logging
import os
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import Lemma, SessionLocal

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

BATCH_SIZE = 500
DATA_DIR = os.environ.get(
    "AED_TEI_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "aed_tei"),
)

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def parse_dictionary(dict_path: str) -> list[dict]:
    """Parse dictionary.xml and return list of lemma dicts."""
    log.info("Parsing dictionary: %s", dict_path)
    tree = ET.parse(dict_path)
    root = tree.getroot()

    lemmata = []
    for entry in root.findall(".//tei:entry", NS):
        xml_id = entry.get("{http://www.w3.org/XML/1998/namespace}id", "")
        if not xml_id:
            continue

        # Strip 'tla' prefix for clean ID
        lemma_id = xml_id

        # Form (transliteration headword)
        orth_el = entry.find("tei:form/tei:orth", NS)
        form = orth_el.text.strip() if orth_el is not None and orth_el.text else ""
        if not form:
            continue

        # Part of speech
        pos_el = entry.find("tei:gramGrp/tei:term", NS)
        pos = pos_el.text.strip() if pos_el is not None and pos_el.text else None

        # Translations (German + English)
        translation = {}
        for cit in entry.findall("tei:sense/tei:cit[@type='translation']", NS):
            lang = cit.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            quote = cit.find("tei:quote", NS)
            if quote is not None and quote.text:
                translation[lang] = quote.text.strip()

        # Bibliography
        bibl_el = entry.find("tei:sense/tei:cit/tei:bibl", NS)
        bibl = bibl_el.text.strip() if bibl_el is not None and bibl_el.text else None

        # Cross-references (root reference)
        root_ref = None
        xr_el = entry.find("tei:xr[@type='root']/tei:ref", NS)
        if xr_el is not None:
            root_ref = xr_el.get("target", "")

        extra = {}
        if bibl:
            extra["bibliography"] = bibl
        if root_ref:
            extra["root_ref"] = root_ref

        lemmata.append({
            "id": lemma_id,
            "form": form,
            "translation": translation if translation else None,
            "pos": pos,
            "language": "egyptian",
            "source": "aed",
            "frequency_rank": None,
            "extra": extra if extra else None,
        })

    log.info("Parsed %d lemma entries", len(lemmata))
    return lemmata


def import_lemmata(session, lemmata: list[dict]) -> int:
    """Bulk insert lemmata into the database."""
    inserted = 0
    for i in range(0, len(lemmata), BATCH_SIZE):
        batch = lemmata[i : i + BATCH_SIZE]
        stmt = pg_insert(Lemma.__table__).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        result = session.execute(stmt)
        inserted += result.rowcount
        session.commit()

        if (i // BATCH_SIZE) % 10 == 0:
            log.info("Progress: %d / %d lemmata processed, %d inserted", i + len(batch), len(lemmata), inserted)

    return inserted


def main():
    """Entry point for AED dictionary import."""
    start = time.time()
    log.info("=" * 60)
    log.info("AED Lemma Dictionary Import")
    log.info("=" * 60)

    dict_path = Path(DATA_DIR) / "files" / "dictionary.xml"
    if not dict_path.exists():
        log.error("Dictionary not found: %s", dict_path)
        log.error("Clone the AED-TEI repo first: git clone https://github.com/simondschweitzer/aed-tei.git data/upstream/aed_tei")
        sys.exit(1)

    lemmata = parse_dictionary(str(dict_path))

    session = SessionLocal()
    try:
        inserted = import_lemmata(session, lemmata)
        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("AED dictionary import complete.")
        log.info("  Parsed:   %d entries", len(lemmata))
        log.info("  Inserted: %d entries", inserted)
        log.info("  Elapsed:  %.1f seconds", elapsed)
        log.info("=" * 60)
    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
