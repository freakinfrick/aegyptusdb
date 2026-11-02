"""AED-TEI corpus importer.

Imports ~13,950 Egyptian texts from TEI XML into:
  - texts: one record per base XML file
  - sentences: from _st.xml (German translations) + _wt.xml (word-level tokens)
  - representation_layers: hieroglyphic from _hiero.xml
  - concordance: TLA base32 IDs
  - aliases: from concordance_name_text_id.csv

Source: data/upstream/aed_tei/files/
License: CC BY-SA 4.0
Idempotent: INSERT ON CONFLICT DO NOTHING.
"""

import csv
import logging
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import (
    Alias,
    Concordance,
    RepresentationLayer,
    Sentence,
    SessionLocal,
    TextRecord,
)
from importers import pg_flush

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

BATCH_SIZE = 500
SENTENCE_BATCH_SIZE = 100  # Smaller for sentences (many JSONB params per row)
DATA_DIR = os.environ.get(
    "AED_TEI_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "aed_tei"),
)

NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# Script type inference from textLang mainLang attribute
SCRIPT_MAP = {
    "Egyp-Egypreg": "hieroglyphic",
    "Egyp-Egypcs": "hieratic",       # cursive script
    "Egyp-Egyph": "hieratic",
    "Egyp-Egyphie": "hieroglyphic",
    "Egyp-Egyplhie": "hieroglyphic",  # late hieroglyphic
    "Egyp-Egyplcs": "hieratic",       # late cursive
    "Egyp-Egypd": "demotic",
    "Egyp-Egypdm": "demotic",
    "Egyp-Egypdem": "demotic",
    "cop": "coptic",
}

# Fallback: infer from text description
SCRIPT_TEXT_MAP = {
    "hieroglyphenschrift": "hieroglyphic",
    "hieroglyphen": "hieroglyphic",
    "hieratisch": "hieratic",
    "kursivhieroglyphisch": "hieroglyphic",
    "demotisch": "demotic",
    "koptisch": "coptic",
}


def infer_script_type(text_lang_el) -> str | None:
    """Infer script type from TEI textLang element."""
    if text_lang_el is None:
        return None

    main_lang = text_lang_el.get("mainLang", "")
    if main_lang in SCRIPT_MAP:
        return SCRIPT_MAP[main_lang]

    # Try text content
    text = (text_lang_el.text or "").strip().lower()
    for keyword, script in SCRIPT_TEXT_MAP.items():
        if keyword in text:
            return script

    # Any Egyptian language marker → default hieroglyphic
    if main_lang.startswith("Egyp"):
        return "hieroglyphic"

    return None


def parse_base_xml(filepath: Path) -> dict | None:
    """Parse base text XML for metadata."""
    try:
        tree = ET.parse(str(filepath))
    except ET.ParseError as e:
        log.debug("Parse error in %s: %s", filepath.name, e)
        return None

    root = tree.getroot()

    # Title
    title_el = root.find(".//tei:titleStmt/tei:title", NS)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    # Script type
    text_lang = root.find(".//tei:textLang", NS)
    script_type = infer_script_type(text_lang)

    # Dates
    date_earliest = None
    date_latest = None
    period_label = None
    for date_el in root.findall(".//tei:origDate/tei:date", NS):
        dtype = date_el.get("type", "")
        if dtype == "earliest":
            nb = date_el.get("notBefore", "")
            if nb:
                try:
                    date_earliest = int(nb)
                except ValueError:
                    pass
            period_label = date_el.text.strip() if date_el.text else period_label
        elif dtype == "latest":
            na = date_el.get("notAfter", "")
            if na:
                try:
                    date_latest = int(na)
                except ValueError:
                    pass

    # Place
    place_el = root.find(".//tei:origPlace", NS)
    findspot = place_el.text.strip() if place_el is not None and place_el.text else None

    # Object type
    objtype_el = root.find(".//tei:objectType", NS)
    text_type = None
    if objtype_el is not None and objtype_el.text:
        # Format: "21 = Objekttyp" or actual type name
        raw = objtype_el.text.strip()
        if "=" in raw:
            text_type = raw.split("=", 1)[1].strip()
        else:
            text_type = raw

    # msName (shelfmark-like)
    msname_el = root.find(".//tei:msName", NS)
    msname = msname_el.text.strip() if msname_el is not None and msname_el.text else None

    return {
        "title": title,
        "script_type": script_type,
        "date_earliest": date_earliest,
        "date_latest": date_latest,
        "period_label": period_label,
        "findspot": findspot,
        "text_type": text_type,
        "msname": msname,
    }


def parse_sentences_xml(filepath: Path) -> list[dict]:
    """Parse _st.xml for German sentence translations."""
    try:
        tree = ET.parse(str(filepath))
    except ET.ParseError:
        return []

    root = tree.getroot()
    sentences = []
    for idx, s_el in enumerate(root.findall(".//tei:s", NS), 1):
        lang = s_el.get("{http://www.w3.org/XML/1998/namespace}lang", "")
        corresp = s_el.get("corresp", "")
        text = "".join(s_el.itertext()).strip()
        sentences.append({
            "seq": idx,
            "corresp": corresp,
            "lang": lang,
            "text": text,
        })
    return sentences


def parse_words_xml(filepath: Path) -> dict[str, list[dict]]:
    """Parse _wt.xml for word-level translations. Returns {corresp: [tokens]}."""
    try:
        tree = ET.parse(str(filepath))
    except ET.ParseError:
        return {}

    root = tree.getroot()
    result = {}
    for s_el in root.findall(".//tei:s", NS):
        corresp = s_el.get("corresp", "")
        tokens = []
        for w_el in s_el.findall("tei:w", NS):
            w_corresp = w_el.get("corresp", "")
            w_text = (w_el.text or "").strip()
            lemma = w_el.get("lemma", "")
            pos = w_el.get("type", "")
            tokens.append({
                "corresp": w_corresp,
                "translation_de": w_text,
                "lemma_ref": lemma,
                "pos": pos,
            })
        if corresp:
            result[corresp] = tokens
    return result


def parse_hiero_xml(filepath: Path) -> dict[str, list[str]]:
    """Parse _hiero.xml for hieroglyphic content. Returns {corresp: [hieroglyphs]}."""
    try:
        tree = ET.parse(str(filepath))
    except ET.ParseError:
        return {}

    root = tree.getroot()
    result = {}
    for s_el in root.findall(".//tei:s", NS):
        corresp = s_el.get("corresp", "")
        glyphs = []
        for w_el in s_el.findall("tei:w", NS):
            w_text = "".join(w_el.itertext()).strip()
            if w_text:
                glyphs.append(w_text)
        if corresp and glyphs:
            result[corresp] = glyphs
    return result


def discover_texts(files_dir: Path) -> dict[str, dict[str, Path]]:
    """Walk files directory and group by base text ID.

    Returns {text_id: {base: Path, st: Path, wt: Path, hiero: Path}}
    """
    groups = defaultdict(dict)
    for f in files_dir.iterdir():
        if not f.name.endswith(".xml"):
            continue
        name = f.stem
        if name in ("dictionary", "thesaurus"):
            continue

        if name.endswith("_st"):
            base_id = name[:-3]
            groups[base_id]["st"] = f
        elif name.endswith("_wt"):
            base_id = name[:-3]
            groups[base_id]["wt"] = f
        elif name.endswith("_hiero"):
            base_id = name[:-6]
            groups[base_id]["hiero"] = f
        else:
            groups[name]["base"] = f

    return dict(groups)


def import_aliases(session, csv_path: Path) -> int:
    """Import aliases from concordance_name_text_id.csv."""
    if not csv_path.exists():
        log.warning("Concordance CSV not found: %s", csv_path)
        return 0

    log.info("Importing aliases from %s", csv_path)
    aliases = []
    with open(csv_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            name, text_id = parts
            canonical_id = f"aeg_aedtei_{text_id}"
            # Normalize: lowercase, strip whitespace
            normalized = re.sub(r"\s+", " ", name.strip().lower())
            aliases.append({
                "canonical_id": canonical_id,
                "alias_text": name.strip(),
                "alias_normalized": normalized,
                "alias_type": "conventional_name",
                "confidence": "auto",
            })

    # Filter to only aliases whose texts exist
    existing_ids = set(
        row[0] for row in session.execute(
            sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_aedtei_%'")
        ).fetchall()
    )
    valid_aliases = [a for a in aliases if a["canonical_id"] in existing_ids]
    log.info("Aliases: %d total, %d with valid parent texts", len(aliases), len(valid_aliases))

    inserted = 0
    for i in range(0, len(valid_aliases), BATCH_SIZE):
        batch = valid_aliases[i : i + BATCH_SIZE]
        stmt = pg_insert(Alias.__table__).values(batch)
        stmt = stmt.on_conflict_do_nothing()
        result = session.execute(stmt)
        inserted += result.rowcount
        session.commit()

    log.info("Aliases: %d inserted", inserted)
    return inserted


def main():
    """Entry point for AED-TEI import."""
    start = time.time()
    log.info("=" * 60)
    log.info("AED-TEI Corpus Import")
    log.info("=" * 60)

    files_dir = Path(DATA_DIR) / "files"
    if not files_dir.exists():
        log.error("Files directory not found: %s", files_dir)
        sys.exit(1)

    # Discover all texts
    log.info("Discovering texts in %s ...", files_dir)
    text_groups = discover_texts(files_dir)
    log.info("Found %d text groups", len(text_groups))

    session = SessionLocal()
    try:
        # Pre-load existing data for dedup
        log.info("Loading existing aed_tei records for dedup...")
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_aedtei_%'")
            ).fetchall()
        )
        existing_sentences = set(
            row[0] for row in session.execute(
                sql_text("SELECT source_id FROM sentences WHERE source = 'aed_tei'")
            ).fetchall()
        )
        existing_layers = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM representation_layers WHERE source = 'aed_tei'")
            ).fetchall()
        )
        log.info("Existing: %d texts, %d sentences, %d layers",
                 len(existing_texts), len(existing_sentences), len(existing_layers))

        texts_inserted = 0
        sentences_inserted = 0
        concordance_inserted = 0
        layers_inserted = 0
        parse_errors = 0
        skipped_existing = 0

        text_batch = []
        sent_batch = []
        conc_batch = []
        layer_batch = []

        for idx, (text_id, paths) in enumerate(sorted(text_groups.items()), 1):
            canonical_id = f"aeg_aedtei_{text_id}"

            # Parse base metadata
            if "base" not in paths:
                parse_errors += 1
                continue

            meta = parse_base_xml(paths["base"])
            if meta is None:
                parse_errors += 1
                continue

            # TextRecord
            text_batch.append({
                "canonical_id": canonical_id,
                "conventional_name": meta["title"],
                "script_type": meta["script_type"],
                "date_earliest": meta["date_earliest"],
                "date_latest": meta["date_latest"],
                "period_label": meta["period_label"],
                "findspot": meta["findspot"],
                "text_type": meta["text_type"],
                "completeness": "unknown",
                "shelfmarks": [meta["msname"]] if meta["msname"] else None,
                "metadata": {"source_project": "aed_tei", "tla_id": text_id},
                "source_corpus": ["aed_tei"],
            })

            # Concordance
            conc_batch.append({
                "canonical_id": canonical_id,
                "external_system": "tla",
                "external_id": text_id,
                "relationship": "exact_match",
            })
            conc_batch.append({
                "canonical_id": canonical_id,
                "external_system": "aed_tei",
                "external_id": text_id,
                "relationship": "exact_match",
            })

            # Sentences from _st.xml
            sentences = []
            if "st" in paths:
                sentences = parse_sentences_xml(paths["st"])

            # Word-level tokens from _wt.xml
            word_map = {}
            if "wt" in paths:
                word_map = parse_words_xml(paths["wt"])

            # Hieroglyphic data from _hiero.xml
            hiero_map = {}
            if "hiero" in paths:
                hiero_map = parse_hiero_xml(paths["hiero"])

            for sent in sentences:
                source_id = f"{text_id}-{sent['seq']}"
                if source_id in existing_sentences:
                    continue

                translation = {}
                if sent["lang"] == "de" and sent["text"]:
                    translation["de"] = sent["text"]

                tokens = None
                if sent["corresp"] in word_map:
                    tokens = word_map[sent["corresp"]]

                sent_batch.append({
                    "canonical_id": canonical_id,
                    "sequence_num": sent["seq"],
                    "transliteration": None,
                    "translation": translation if translation else None,
                    "tokens": tokens,
                    "source": "aed_tei",
                    "source_id": source_id,
                    "source_detail": {"corresp": sent["corresp"]} if sent["corresp"] else None,
                    "confidence": "verified",
                })

            # Hieroglyphic representation layer
            if hiero_map and canonical_id not in existing_layers:
                all_glyphs = []
                for corresp, glyphs in hiero_map.items():
                    all_glyphs.extend(glyphs)

                if all_glyphs:
                    layer_batch.append({
                        "canonical_id": canonical_id,
                        "layer_type": "hieroglyphic",
                        "content": {"hieroglyphs": all_glyphs, "sentences": dict(hiero_map)},
                        "language": "egy",
                        "source": "aed_tei",
                        "confidence": "verified",
                    })

            # Flush batches — texts MUST flush before everything else (FK parent)
            needs_text_flush = (
                len(text_batch) >= BATCH_SIZE
                or len(sent_batch) >= SENTENCE_BATCH_SIZE
                or len(conc_batch) >= BATCH_SIZE
                or len(layer_batch) >= BATCH_SIZE
            )
            if needs_text_flush and text_batch:
                texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
                text_batch.clear()
            if len(conc_batch) >= BATCH_SIZE:
                concordance_inserted += pg_flush(session, Concordance.__table__, conc_batch)
                conc_batch.clear()
            if len(sent_batch) >= SENTENCE_BATCH_SIZE:
                sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)
                sent_batch.clear()
            if len(layer_batch) >= BATCH_SIZE:
                layers_inserted += pg_flush(session, RepresentationLayer.__table__, layer_batch)
                layer_batch.clear()

            if idx % 2000 == 0:
                log.info(
                    "Progress: %d/%d texts | %d texts, %d sentences, %d concordance, %d layers inserted",
                    idx, len(text_groups), texts_inserted, sentences_inserted,
                    concordance_inserted, layers_inserted,
                )

        # Flush remaining — texts first (FK parent)
        if text_batch:
            texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
        if conc_batch:
            concordance_inserted += pg_flush(session, Concordance.__table__, conc_batch)
        if sent_batch:
            sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)
        if layer_batch:
            layers_inserted += pg_flush(session, RepresentationLayer.__table__, layer_batch)

        # Import aliases from CSV
        csv_path = Path(DATA_DIR) / "concordance_name_text_id.csv"
        aliases_inserted = import_aliases(session, csv_path)

        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("AED-TEI import complete.")
        log.info("  Texts:       %d inserted", texts_inserted)
        log.info("  Sentences:   %d inserted", sentences_inserted)
        log.info("  Concordance: %d inserted", concordance_inserted)
        log.info("  Hiero layers:%d inserted", layers_inserted)
        log.info("  Aliases:     %d inserted", aliases_inserted)
        log.info("  Parse errors:%d skipped", parse_errors)
        log.info("  Elapsed:     %.1f seconds", elapsed)
        log.info("=" * 60)

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
