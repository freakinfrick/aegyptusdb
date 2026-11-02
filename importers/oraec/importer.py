"""ORAEC bulk importer.

Imports 13,026 individual JSON files from oraec/corpus_raw_data into:
  - texts: one record per JSON file
  - sentences: nested sentence data from each JSON
  - representation_layers: transliteration, hieroglyphic, translation, lemmatization
  - concordance: cross-reference IDs (TLA, Trismegistos, Wikidata, Karnak)

Also imports mapping CSV/TSV files into the concordance table.

Idempotent: uses INSERT ON CONFLICT DO NOTHING / check-before-insert.
"""

import csv
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models import (
    Concordance,
    RepresentationLayer,
    Sentence,
    SessionLocal,
    TextRecord,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("oraec_importer")

DATA_DIR = os.environ.get(
    "ORAEC_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "oraec_corpus_raw_data"),
)

BATCH_SIZE = 500


def extract_oraec_number(filename: str) -> str | None:
    """Extract the numeric part from a filename like 'oraec1234.json'."""
    m = re.match(r"oraec(\d+)\.json$", filename)
    return m.group(1) if m else None


def extract_tla_id_from_credits(credits: dict) -> str | None:
    """Extract the 26-char TLA base32 ID from credits.source URLs."""
    for url in credits.get("source", []):
        m = re.search(r"/files/([A-Z0-9]{26})\.xml", url)
        if m:
            return m.group(1)
    return None


def build_text_record(oraec_num: str, inner: dict) -> dict:
    """Build a dict suitable for inserting into the texts table."""
    canonical_id = f"aeg_oraec_{oraec_num}"

    # Extract structured fields
    title = inner.get("title", "")
    date_info = inner.get("date", [])
    origplace_info = inner.get("origplace", [])
    objecttype_info = inner.get("objecttype", [])
    location_info = inner.get("location", [])
    idno = inner.get("idno", [])
    bibliography = inner.get("bibliography", "")
    condition = inner.get("condition")
    material = inner.get("material")
    credits = inner.get("credits", {})

    # Determine findspot from origplace
    findspot = origplace_info[0]["origplace"] if origplace_info else None
    current_location = location_info[0]["location"] if location_info else None

    # Shelfmarks from idno (deduplicated)
    shelfmarks = list(dict.fromkeys(idno)) if idno else None

    # Build metadata JSONB with everything that doesn't have a dedicated column
    metadata = {
        "oraec_id": f"oraec{oraec_num}",
        "bibliography": bibliography,
        "credits": credits,
    }
    if date_info:
        metadata["date"] = date_info
    if origplace_info:
        metadata["origplace"] = origplace_info
    if objecttype_info:
        metadata["objecttype"] = objecttype_info
    if location_info:
        metadata["location"] = location_info
    if condition:
        metadata["condition"] = condition
    if material:
        metadata["material"] = material

    # Period label from date
    period_label = date_info[0]["date"] if date_info else None

    # Text type from objecttype
    text_type = objecttype_info[0]["objecttype"] if objecttype_info else None

    return {
        "canonical_id": canonical_id,
        "conventional_name": title or None,
        "script_type": None,  # ORAEC doesn't explicitly classify script type
        "date_earliest": None,
        "date_latest": None,
        "period_label": period_label,
        "findspot": findspot,
        "current_location": current_location,
        "text_type": text_type,
        "completeness": None,
        "shelfmarks": shelfmarks,
        "extra_metadata": metadata,
    }


def build_sentences(canonical_id: str, oraec_num: str, sentences_data: list) -> list[dict]:
    """Build sentence dicts from ORAEC nested sentence data."""
    result = []
    for seq, sent in enumerate(sentences_data, start=1):
        tokens_raw = sent.get("token", [])
        translation_text = sent.get("translation")

        # Build token-level JSONB
        tokens = []
        for tok in tokens_raw:
            token_obj = {}
            for key in ("written_form", "lemma_form", "lemmaID", "pos", "hiero",
                        "cotext_translation", "lineCount", "token",
                        "verbalClass", "inflection", "voice", "status",
                        "numerus", "genus", "morphology", "number",
                        "adjective", "adverb", "epitheton", "name",
                        "particle", "pronoun"):
                if key in tok:
                    token_obj[key] = tok[key]
            tokens.append(token_obj)

        # Translation as JSONB keyed by language
        # ORAEC translations are typically German
        translation = None
        if translation_text:
            translation = {"de": translation_text}

        # Source ID from token IDs: e.g. "oraec1-1-1" -> sentence "oraec1-1"
        source_id = None
        if tokens_raw:
            first_token_id = tokens_raw[0].get("token", "")
            # Token format: oraecN-S-T where S is sentence num, T is token num
            parts = first_token_id.rsplit("-", 1)
            if len(parts) == 2:
                source_id = parts[0]  # e.g. "oraec1-1"

        result.append({
            "canonical_id": canonical_id,
            "sequence_num": seq,
            "transliteration": _build_transliteration(tokens_raw),
            "translation": translation,
            "tokens": tokens if tokens else None,
            "source": "oraec",
            "source_id": source_id,
            "source_detail": {"oraec_num": oraec_num},
            "confidence": "verified",
        })
    return result


def _build_transliteration(tokens: list[dict]) -> str | None:
    """Concatenate written_form fields into a sentence-level transliteration."""
    forms = [t.get("written_form", "") for t in tokens if t.get("written_form")]
    return " ".join(forms) if forms else None


def build_representation_layers(canonical_id: str, oraec_num: str, inner: dict) -> list[dict]:
    """Build representation layer entries for available data."""
    layers = []
    sentences = inner.get("sentences", [])
    if not sentences:
        return layers

    # Collect all transliterations
    transliterations = []
    hieroglyphics = []
    translations = []
    lemmatizations = []

    for sent in sentences:
        tokens = sent.get("token", [])

        # Transliteration: concatenated written_forms
        forms = [t.get("written_form", "") for t in tokens if t.get("written_form")]
        if forms:
            transliterations.append(" ".join(forms))

        # Hieroglyphic: concatenated hiero fields
        hieros = [t["hiero"] for t in tokens if t.get("hiero")]
        if hieros:
            hieroglyphics.append(" ".join(hieros))

        # Translation
        if sent.get("translation"):
            translations.append(sent["translation"])

        # Lemmatization: tokens with lemma data
        lemma_tokens = []
        for t in tokens:
            if t.get("lemmaID"):
                lemma_tokens.append({
                    "written_form": t.get("written_form"),
                    "lemma_form": t.get("lemma_form"),
                    "lemma_id": t.get("lemmaID"),
                    "pos": t.get("pos"),
                    "hiero": t.get("hiero"),
                })
        if lemma_tokens:
            lemmatizations.append(lemma_tokens)

    source_detail = {"oraec_id": f"oraec{oraec_num}"}

    if transliterations:
        layers.append({
            "canonical_id": canonical_id,
            "layer_type": "transliteration",
            "content": {"sentences": transliterations},
            "language": None,
            "source": "oraec",
            "source_detail": source_detail,
            "confidence": "verified",
        })

    if hieroglyphics:
        layers.append({
            "canonical_id": canonical_id,
            "layer_type": "hieroglyphic",
            "content": {"sentences": hieroglyphics},
            "language": None,
            "source": "oraec",
            "source_detail": source_detail,
            "confidence": "verified",
        })

    if translations:
        layers.append({
            "canonical_id": canonical_id,
            "layer_type": "translation",
            "content": {"sentences": translations},
            "language": "de",
            "source": "oraec",
            "source_detail": source_detail,
            "confidence": "verified",
        })

    if lemmatizations:
        layers.append({
            "canonical_id": canonical_id,
            "layer_type": "lemmatization",
            "content": {"sentences": lemmatizations},
            "language": None,
            "source": "oraec",
            "source_detail": source_detail,
            "confidence": "verified",
        })

    return layers


def build_concordance_from_json(canonical_id: str, oraec_num: str, inner: dict) -> list[dict]:
    """Extract cross-reference IDs from ORAEC JSON for concordance table."""
    entries = []

    # Self-reference: oraec ID
    entries.append({
        "canonical_id": canonical_id,
        "external_system": "oraec",
        "external_id": f"oraec{oraec_num}",
        "relationship": "exact_match",
    })

    # TLA base32 text ID from credits
    credits = inner.get("credits", {})
    tla_id = extract_tla_id_from_credits(credits)
    if tla_id:
        entries.append({
            "canonical_id": canonical_id,
            "external_system": "tla",
            "external_id": tla_id,
            "relationship": "exact_match",
        })

    # TLA IDs from date, origplace, objecttype, location fields
    # These are entity IDs (not text IDs) -- store with relationship type
    for field_name in ("date", "origplace", "objecttype", "location"):
        items = inner.get(field_name, [])
        for item in items:
            entity_id = item.get("id")
            if entity_id and re.match(r"^[A-Z0-9]{26}$", entity_id):
                entries.append({
                    "canonical_id": canonical_id,
                    "external_system": f"tla_entity_{field_name}",
                    "external_id": entity_id,
                    "relationship": "exact_match",
                })

    return entries


def import_json_files(session, data_dir: str) -> dict:
    """Import all ORAEC JSON files into texts, sentences, representation_layers, concordance."""
    json_files = sorted(
        [f for f in os.listdir(data_dir) if re.match(r"oraec\d+\.json$", f)],
        key=lambda x: int(re.search(r"\d+", x).group()),
    )
    log.info("Found %d ORAEC JSON files to import", len(json_files))

    stats = {
        "texts_inserted": 0,
        "texts_skipped": 0,
        "sentences_inserted": 0,
        "layers_inserted": 0,
        "concordance_inserted": 0,
        "errors": 0,
    }

    # Pre-load existing canonical IDs to check for idempotency
    existing_ids = set(
        row[0] for row in session.execute(
            sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_oraec_%'")
        ).fetchall()
    )
    log.info("Found %d existing ORAEC text records", len(existing_ids))

    # Pre-load existing concordance entries for dedup
    existing_concordance = set(
        (row[0], row[1], row[2]) for row in session.execute(
            sql_text("SELECT external_system, external_id, canonical_id FROM concordance")
        ).fetchall()
    )

    # Pre-load existing layer fingerprints for dedup
    existing_layers = set(
        (row[0], row[1], row[2]) for row in session.execute(
            sql_text("SELECT canonical_id, layer_type, source FROM representation_layers WHERE source = 'oraec'")
        ).fetchall()
    )

    # Pre-load existing sentences for dedup using (canonical_id, sequence_num) composite key
    existing_sentences = set(
        (row[0], row[1]) for row in session.execute(
            sql_text("SELECT canonical_id, sequence_num FROM sentences WHERE source = 'oraec'")
        ).fetchall()
    )

    t_start = time.time()

    for i, fname in enumerate(json_files, start=1):
        oraec_num = extract_oraec_number(fname)
        if not oraec_num:
            log.warning("Skipping file with unexpected name: %s", fname)
            stats["errors"] += 1
            continue

        canonical_id = f"aeg_oraec_{oraec_num}"

        try:
            fpath = os.path.join(data_dir, fname)
            with open(fpath) as fh:
                data = json.load(fh)

            # The JSON has a single top-level key matching the oraec ID
            oraec_key = f"oraec{oraec_num}"
            inner = data.get(oraec_key)
            if inner is None:
                # Fallback: try first key
                inner = next(iter(data.values()))

            # Insert text record
            if canonical_id not in existing_ids:
                text_dict = build_text_record(oraec_num, inner)
                text_record = TextRecord(**text_dict)
                session.add(text_record)
                session.flush()
                existing_ids.add(canonical_id)
                stats["texts_inserted"] += 1
            else:
                stats["texts_skipped"] += 1

            # Insert sentences
            sentences_data = inner.get("sentences", [])
            if sentences_data:
                sent_dicts = build_sentences(canonical_id, oraec_num, sentences_data)
                for sd in sent_dicts:
                    sent_key = (sd["canonical_id"], sd["sequence_num"])
                    if sent_key in existing_sentences:
                        continue
                    sentence = Sentence(**sd)
                    session.add(sentence)
                    existing_sentences.add(sent_key)
                    stats["sentences_inserted"] += 1

            # Insert representation layers
            layer_dicts = build_representation_layers(canonical_id, oraec_num, inner)
            for ld in layer_dicts:
                layer_key = (ld["canonical_id"], ld["layer_type"], ld["source"])
                if layer_key not in existing_layers:
                    layer = RepresentationLayer(**ld)
                    session.add(layer)
                    existing_layers.add(layer_key)
                    stats["layers_inserted"] += 1

            # Insert concordance entries
            conc_dicts = build_concordance_from_json(canonical_id, oraec_num, inner)
            for cd in conc_dicts:
                conc_key = (cd["external_system"], cd["external_id"], cd["canonical_id"])
                if conc_key not in existing_concordance:
                    conc = Concordance(**cd)
                    session.add(conc)
                    existing_concordance.add(conc_key)
                    stats["concordance_inserted"] += 1

            # Batch commit
            if i % BATCH_SIZE == 0:
                session.commit()

        except Exception:
            log.exception("Error processing %s", fname)
            session.rollback()
            stats["errors"] += 1
            continue

        if i % 1000 == 0:
            elapsed = time.time() - t_start
            rate = i / elapsed
            log.info(
                "Progress: %d/%d files (%.0f/s) | texts=%d sentences=%d layers=%d concordance=%d errors=%d",
                i, len(json_files), rate,
                stats["texts_inserted"], stats["sentences_inserted"],
                stats["layers_inserted"], stats["concordance_inserted"],
                stats["errors"],
            )

    # Final commit
    session.commit()

    elapsed = time.time() - t_start
    log.info(
        "JSON import complete in %.1fs: texts=%d (skipped=%d) sentences=%d layers=%d concordance=%d errors=%d",
        elapsed,
        stats["texts_inserted"], stats["texts_skipped"],
        stats["sentences_inserted"], stats["layers_inserted"],
        stats["concordance_inserted"], stats["errors"],
    )
    return stats


def import_trismegistos_mapping(session, data_dir: str) -> int:
    """Import mapping_oraec_trismegistos.csv into concordance."""
    fpath = os.path.join(data_dir, "mapping_oraec_trismegistos.csv")
    if not os.path.exists(fpath):
        log.warning("Trismegistos mapping file not found: %s", fpath)
        return 0

    count = 0
    with open(fpath) as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        for row in reader:
            if len(row) < 2:
                continue
            oraec_id_raw, tm_id = row[0].strip(), row[1].strip()
            if not oraec_id_raw.startswith("oraec") or not tm_id:
                continue
            oraec_num = oraec_id_raw.replace("oraec", "")
            canonical_id = f"aeg_oraec_{oraec_num}"

            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system="trismegistos",
                external_id=tm_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(
                constraint="uq_concordance_system_ext_canonical"
            )
            result = session.execute(stmt)
            if result.rowcount:
                count += 1

    session.commit()
    log.info("Trismegistos mapping: %d entries imported", count)
    return count


def import_karnak_mapping(session, data_dir: str) -> int:
    """Import mapping_oraec_karnak.tsv into concordance."""
    fpath = os.path.join(data_dir, "mapping_oraec_karnak.tsv")
    if not os.path.exists(fpath):
        log.warning("Karnak mapping file not found: %s", fpath)
        return 0

    count = 0
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            oraec_id_raw, karnak_url = parts[0].strip(), parts[1].strip()
            if not oraec_id_raw.startswith("oraec"):
                continue
            oraec_num = oraec_id_raw.replace("oraec", "")
            canonical_id = f"aeg_oraec_{oraec_num}"

            # Extract karnak ID from URL
            karnak_match = re.search(r"/karnak/(\d+)$", karnak_url)
            karnak_id = karnak_match.group(1) if karnak_match else karnak_url

            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system="karnak",
                external_id=karnak_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(
                constraint="uq_concordance_system_ext_canonical"
            )
            result = session.execute(stmt)
            if result.rowcount:
                count += 1

    session.commit()
    log.info("Karnak mapping: %d entries imported", count)
    return count


def import_wikidata_mapping(session, data_dir: str) -> int:
    """Import mapping_oraec_wikidata.tsv into concordance.

    This file maps TLA base32 IDs (and some person names) to Wikidata Q-IDs.
    We link via TLA ID -> canonical_id lookup.
    """
    fpath = os.path.join(data_dir, "mapping_oraec_wikidata.tsv")
    if not os.path.exists(fpath):
        log.warning("Wikidata mapping file not found: %s", fpath)
        return 0

    # Build a TLA -> canonical_id lookup from existing concordance
    # Check both direct TLA text IDs and TLA entity IDs (date, origplace, etc.)
    tla_to_canonical = {}
    rows = session.execute(
        sql_text("SELECT canonical_id, external_id FROM concordance WHERE external_system LIKE 'tla%'")
    ).fetchall()
    for row in rows:
        # First match wins (tla text IDs take priority since they're loaded first)
        if row[1] not in tla_to_canonical:
            tla_to_canonical[row[1]] = row[0]

    count = 0
    skipped_no_match = 0
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            entity_id, wikidata_id = parts[0].strip(), parts[1].strip()

            # Skip person name entries (they don't have a text canonical_id)
            if not re.match(r"^[A-Z0-9]{20,30}$", entity_id):
                continue

            canonical_id = tla_to_canonical.get(entity_id)
            if not canonical_id:
                skipped_no_match += 1
                continue

            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system="wikidata",
                external_id=wikidata_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(
                constraint="uq_concordance_system_ext_canonical"
            )
            result = session.execute(stmt)
            if result.rowcount:
                count += 1

    session.commit()
    log.info("Wikidata mapping: %d entries imported (%d skipped, no TLA match)", count, skipped_no_match)
    return count


def import_hierarchical_path(session, data_dir: str) -> int:
    """Import oraec_hierarchical_path.tsv to enrich concordance with TLA text IDs.

    This file maps every oraec ID to its TLA hierarchical path, with TLA IDs
    embedded in URLs. The last /text/ URL contains the TLA text ID.
    This supplements the TLA IDs extracted from credits.source in the JSON files.
    """
    fpath = os.path.join(data_dir, "oraec_hierarchical_path.tsv")
    if not os.path.exists(fpath):
        log.info("Hierarchical path file not found (optional): %s", fpath)
        return 0

    count = 0
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            oraec_id_raw = parts[0].strip()
            if not oraec_id_raw.startswith("oraec"):
                continue
            oraec_num = oraec_id_raw.replace("oraec", "")
            canonical_id = f"aeg_oraec_{oraec_num}"

            # Extract the TLA text ID (from /text/ URLs, not /object/ URLs)
            html_part = parts[-1] if len(parts) > 2 else parts[1]
            tla_text_ids = re.findall(
                r'thesaurus-linguae-aegyptiae\.de/text/([A-Z0-9]{26})', html_part
            )
            if not tla_text_ids:
                continue

            # Use the last text ID (deepest in hierarchy = the actual text)
            tla_id = tla_text_ids[-1]

            stmt = pg_insert(Concordance).values(
                canonical_id=canonical_id,
                external_system="tla",
                external_id=tla_id,
                relationship="exact_match",
            ).on_conflict_do_nothing(
                constraint="uq_concordance_system_ext_canonical"
            )
            result = session.execute(stmt)
            if result.rowcount:
                count += 1

    session.commit()
    log.info("Hierarchical path: %d new TLA entries imported", count)
    return count


def import_lemmata_mappings(session, data_dir: str) -> dict:
    """Import lemmata mapping files.

    These map AED lemma IDs (not text IDs) to external systems.
    Since the concordance table requires a canonical_id FK to texts,
    and lemma IDs don't correspond to texts, we store these as
    concordance entries with a special convention:
    - external_system: 'karnak_lemma' or 'vega_lemma'
    - We skip them since they cannot satisfy the FK constraint.
    Instead, we log the counts for documentation purposes.
    """
    results = {}

    for fname, system_name in [
        ("mapping_oraec_lemmata_karnak.tsv", "karnak_lemma"),
        ("mapping_oraec_lemmata_vega.tsv", "vega_lemma"),
    ]:
        fpath = os.path.join(data_dir, fname)
        if not os.path.exists(fpath):
            log.warning("Lemmata mapping file not found: %s", fpath)
            results[system_name] = 0
            continue

        with open(fpath) as f:
            line_count = sum(1 for line in f if line.strip())

        results[system_name] = line_count
        log.info(
            "Lemmata mapping %s: %d entries found (lemma-level, not imported to concordance -- "
            "no canonical_id FK available for lemma IDs)",
            fname, line_count,
        )

    return results


def print_summary(session):
    """Print final table counts."""
    log.info("=" * 60)
    log.info("FINAL TABLE COUNTS")
    log.info("=" * 60)

    for table, label in [
        ("texts", "texts"),
        ("sentences", "sentences"),
        ("representation_layers", "representation_layers"),
        ("concordance", "concordance"),
    ]:
        count = session.execute(sql_text(f"SELECT count(*) FROM {table}")).scalar()
        log.info("  %-30s %d", label, count)

    # Concordance breakdown by system
    rows = session.execute(
        sql_text("SELECT external_system, count(*) FROM concordance GROUP BY external_system ORDER BY count(*) DESC")
    ).fetchall()
    log.info("  Concordance breakdown:")
    for system, cnt in rows:
        log.info("    %-26s %d", system, cnt)


def main():
    log.info("ORAEC Bulk Importer starting")
    log.info("Data directory: %s", DATA_DIR)

    if not os.path.isdir(DATA_DIR):
        log.error("Data directory not found: %s", DATA_DIR)
        log.error("Run: git clone https://github.com/oraec/corpus_raw_data.git %s", DATA_DIR)
        sys.exit(1)

    session = SessionLocal()

    try:
        # Phase 1: Import JSON files (texts, sentences, layers, concordance from JSON)
        log.info("=" * 60)
        log.info("Phase 1: Importing ORAEC JSON files")
        log.info("=" * 60)
        json_stats = import_json_files(session, DATA_DIR)

        # Phase 2: Import mapping files
        log.info("=" * 60)
        log.info("Phase 2: Importing mapping files")
        log.info("=" * 60)

        import_trismegistos_mapping(session, DATA_DIR)
        import_karnak_mapping(session, DATA_DIR)

        # Import hierarchical path (enriches TLA concordance)
        import_hierarchical_path(session, DATA_DIR)

        # Wikidata mapping (depends on TLA concordance being loaded first)
        import_wikidata_mapping(session, DATA_DIR)

        # Lemmata mappings (informational only)
        import_lemmata_mappings(session, DATA_DIR)

        # Final summary
        print_summary(session)

        log.info("ORAEC import complete.")

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
