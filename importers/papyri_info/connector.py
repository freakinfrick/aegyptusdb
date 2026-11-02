"""Papyri.info / IDP Data Connector.

Clones the papyri/idp.data GitHub repo (shallow), scans for Egyptian-language
texts (hieratic, demotic, Coptic), parses EpiDoc XML, and imports matching
records into the central store.

Access path: https://github.com/papyri/idp.data (CC BY 3.0)
Expected yield: modest -- this is primarily a Greek papyri database.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.models import Alias, Concordance, RepresentationLayer, SessionLocal, TextRecord
from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark

logger = logging.getLogger(__name__)

# EpiDoc XML namespace
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# Default clone location
DEFAULT_CLONE_DIR = os.environ.get(
    "IDP_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "idp.data"),
)

# Keywords that indicate Egyptian-language content
EGYPTIAN_MARKERS = [
    "hieratic", "demotic", "coptic", "egyptian",
    "hieratisch", "demotisch", "koptisch",  # German
    "hiératique", "démotique", "copte",  # French
    "nag hammadi", "coptic museum",  # Nag Hammadi inventory patterns
]

# TM IDs to force-include regardless of marker matching.
# Covers Nag Hammadi codices and Hermetic papyri missed by keyword scan.
FORCE_INCLUDE_TM_IDS = {
    # Nag Hammadi codices (I–XIII)
    "107741", "107742", "107743", "107744", "107745",
    "107746", "107747", "107748", "107749", "107750",
    "107751", "107752", "107753",
    # Hermetic papyri
    "63986",   # Poimandres hymn
    "66868",   # Hermetic text
    "64247",   # Christian Hermetic + Jannes/Jambres
    "108000", "87192", "108146",  # Additional DCLP NH/Hermetic
}

# Script type mapping
SCRIPT_MAP = {
    "hieratic": "hieratic",
    "hieratisch": "hieratic",
    "hiératique": "hieratic",
    "demotic": "demotic",
    "demotisch": "demotic",
    "démotique": "demotic",
    "coptic": "coptic",
    "koptisch": "coptic",
    "copte": "coptic",
    "egyptian": "hieratic",  # Default assumption for generic "egyptian"
}

BATCH_SIZE = 100


@dataclass
class PapyriRecord:
    """Parsed record from EpiDoc XML."""

    filename: str
    collection: str  # DDbDP, DCLP, HGV, APIS
    title: str = ""
    tm_id: str = ""
    script_type: str = ""
    language: str = ""
    text_content: str = ""
    date_earliest: int | None = None
    date_latest: int | None = None
    provenance: str = ""
    material: str = ""
    idno: str = ""
    extra_metadata: dict = field(default_factory=dict)


@dataclass
class ConnectorStats:
    """Import statistics."""

    xml_files_scanned: int = 0
    egyptian_candidates: int = 0
    records_imported: int = 0
    records_skipped: int = 0
    errors: int = 0
    by_collection: dict = field(default_factory=dict)
    by_script: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "xml_files_scanned": self.xml_files_scanned,
            "egyptian_candidates": self.egyptian_candidates,
            "records_imported": self.records_imported,
            "records_skipped": self.records_skipped,
            "errors": self.errors,
            "by_collection": self.by_collection,
            "by_script": self.by_script,
        }


def clone_idp_data(clone_dir: str = DEFAULT_CLONE_DIR) -> str:
    """Shallow-clone the idp.data GitHub repo.

    Returns the path to the cloned directory.
    """
    clone_path = Path(clone_dir)

    if clone_path.exists() and (clone_path / ".git").exists():
        logger.info("idp.data already cloned at %s, pulling latest...", clone_dir)
        subprocess.run(
            ["git", "pull", "--depth=1"],
            cwd=str(clone_path),
            capture_output=True,
            timeout=300,
        )
        return str(clone_path)

    clone_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Shallow-cloning idp.data to %s (this may take a few minutes)...", clone_dir)
    result = subprocess.run(
        [
            "git", "clone", "--depth=1",
            "https://github.com/papyri/idp.data.git",
            str(clone_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr}")

    logger.info("Clone complete: %s", clone_dir)
    return str(clone_path)


def scan_for_egyptian_texts(clone_dir: str = DEFAULT_CLONE_DIR) -> list[Path]:
    """Scan the idp.data repo for XML files containing Egyptian-language markers.

    Searches across DDbDP, DCLP, HGV, and APIS collections.
    """
    clone_path = Path(clone_dir)
    if not clone_path.exists():
        raise FileNotFoundError(f"idp.data not found at {clone_dir}. Run clone_idp_data() first.")

    # Collections to scan
    collections = ["DDB_EpiDoc_XML", "DCLP", "HGV_meta_EpiDoc", "APIS"]
    candidates = []

    for collection in collections:
        collection_path = clone_path / collection
        if not collection_path.exists():
            logger.warning("Collection directory not found: %s", collection_path)
            continue

        # Use grep for fast filtering before XML parsing
        try:
            result = subprocess.run(
                [
                    "grep", "-rli",
                    "--include=*.xml",
                    "-E",
                    "|".join(EGYPTIAN_MARKERS),
                    str(collection_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        candidates.append(Path(line.strip()))
        except subprocess.TimeoutExpired:
            logger.warning("grep timed out scanning %s", collection)
        except Exception as e:
            logger.error("Error scanning %s: %s", collection, e)

    logger.info("Found %d XML files with Egyptian markers", len(candidates))

    # Force-include files for known TM IDs (Nag Hammadi, Hermetic)
    candidate_set = {p.resolve() for p in candidates}
    dclp_path = clone_path / "DCLP"
    if dclp_path.exists():
        for tm_id in FORCE_INCLUDE_TM_IDS:
            # DCLP files are stored in subdirectories by TM ID prefix
            for xml_path in dclp_path.rglob(f"{tm_id}.xml"):
                resolved = xml_path.resolve()
                if resolved not in candidate_set:
                    candidates.append(xml_path)
                    candidate_set.add(resolved)
                    logger.info("Force-included TM %s: %s", tm_id, xml_path)
        logger.info("Total candidates after force-include: %d", len(candidates))

    return candidates


def parse_epidoc_xml(filepath: Path) -> PapyriRecord | None:
    """Parse a single EpiDoc XML file and extract Egyptian-language content."""
    try:
        tree = ET.parse(str(filepath))
        root = tree.getroot()
    except ET.ParseError as e:
        logger.debug("XML parse error in %s: %s", filepath, e)
        return None

    # Determine collection from path
    parts = filepath.parts
    collection = "unknown"
    for coll in ["DDB_EpiDoc_XML", "DCLP", "HGV_meta_EpiDoc", "APIS"]:
        if coll in parts:
            collection = coll
            break

    record = PapyriRecord(filename=str(filepath), collection=collection)

    # Extract title
    title_el = root.find(".//tei:title", NS)
    if title_el is not None and title_el.text:
        record.title = title_el.text.strip()

    # Extract Trismegistos ID
    for idno in root.findall(".//tei:idno", NS):
        idno_type = idno.get("type", "").lower()
        text = (idno.text or "").strip()
        if "tm" in idno_type or "trismegistos" in idno_type:
            # Extract numeric ID
            tm_match = re.search(r"(\d+)", text)
            if tm_match:
                record.tm_id = tm_match.group(1)
        if "ddb" in idno_type or "dclp" in idno_type:
            record.idno = text

    # Also check for TM refs in the body
    if not record.tm_id:
        for ref in root.findall(".//{http://www.tei-c.org/ns/1.0}ref"):
            target = ref.get("target", "")
            if "trismegistos" in target.lower():
                tm_match = re.search(r"(\d+)", target)
                if tm_match:
                    record.tm_id = tm_match.group(1)
                    break

    # Determine script type and language
    full_text = ET.tostring(root, encoding="unicode", method="text").lower()
    for marker, script in SCRIPT_MAP.items():
        if marker in full_text:
            record.script_type = script
            break

    # Extract language from profileDesc
    for lang_el in root.findall(".//tei:langUsage/tei:language", NS):
        ident = lang_el.get("ident", "")
        if ident in ("cop", "egy", "egx"):
            record.language = ident
            break

    # Extract dates
    for date_el in root.findall(".//tei:origDate", NS):
        when = date_el.get("when")
        not_before = date_el.get("notBefore-custom") or date_el.get("notBefore")
        not_after = date_el.get("notAfter-custom") or date_el.get("notAfter")

        if when:
            try:
                record.date_earliest = int(when)
                record.date_latest = int(when)
            except ValueError:
                pass
        if not_before:
            try:
                record.date_earliest = int(not_before)
            except ValueError:
                pass
        if not_after:
            try:
                record.date_latest = int(not_after)
            except ValueError:
                pass
        if record.date_earliest or record.date_latest:
            break

    # Extract provenance
    for orig_place in root.findall(".//tei:origPlace", NS):
        text = orig_place.text or ""
        if text.strip():
            record.provenance = text.strip()
            break

    # Extract text content (the actual transcription)
    text_parts = []
    for div_el in root.findall(".//tei:div[@type='edition']", NS):
        text_parts.append(_extract_text_recursive(div_el))
    for div_el in root.findall(".//tei:div[@type='translation']", NS):
        text_parts.append(_extract_text_recursive(div_el))
    if not text_parts:
        # Try body text
        body = root.find(".//tei:body", NS)
        if body is not None:
            text_parts.append(_extract_text_recursive(body))

    record.text_content = "\n\n".join(t for t in text_parts if t.strip())

    # Verify this is actually Egyptian-related
    if not record.script_type and not record.language:
        # Force-include known TM IDs (Nag Hammadi, Hermetic)
        if record.tm_id in FORCE_INCLUDE_TM_IDS:
            record.script_type = record.script_type or "coptic"
        else:
            # Double-check markers
            has_egyptian = any(m in full_text for m in EGYPTIAN_MARKERS)
            if not has_egyptian:
                return None

    record.extra_metadata = {
        "collection": collection,
        "idno": record.idno,
        "has_text": bool(record.text_content.strip()),
    }

    return record


def _extract_text_recursive(element: ET.Element) -> str:
    """Recursively extract text from an EpiDoc XML element."""
    parts = []
    if element.text:
        parts.append(element.text.strip())
    for child in element:
        # Skip apparatus and editorial markup tags
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("note", "app", "rdg"):
            continue
        parts.append(_extract_text_recursive(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


def import_records(records: list[PapyriRecord], session: Session) -> ConnectorStats:
    """Import parsed papyri records into the central store."""
    stats = ConnectorStats()

    for record in records:
        try:
            canonical_id = _generate_canonical_id(record)

            # Check if already imported (idempotent)
            exists = session.execute(
                sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
                {"cid": canonical_id},
            ).fetchone()

            if exists:
                stats.records_skipped += 1
                continue

            # Create text record
            text_record = TextRecord(
                canonical_id=canonical_id,
                conventional_name=record.title or None,
                script_type=record.script_type or None,
                date_earliest=record.date_earliest,
                date_latest=record.date_latest,
                findspot=record.provenance or None,
                text_type="papyrus",
                completeness="unknown",
                extra_metadata={
                    "source": "papyri.info",
                    "collection": record.collection,
                    "idno": record.idno,
                    "license": "CC BY 3.0",
                },
            )
            session.add(text_record)
            session.flush()

            # Add representation layer if there's text content
            if record.text_content.strip():
                layer = RepresentationLayer(
                    canonical_id=canonical_id,
                    layer_type="transcription",
                    content={"text": record.text_content},
                    language=record.language or record.script_type,
                    source="papyri.info",
                    source_detail={
                        "collection": record.collection,
                        "filename": record.filename,
                        "license": "CC BY 3.0",
                    },
                    confidence="verified",
                )
                session.add(layer)

            # Add TM concordance
            if record.tm_id:
                stmt = pg_insert(Concordance).values(
                    canonical_id=canonical_id,
                    external_system="TM",
                    external_id=record.tm_id,
                    relationship="exact_match",
                ).on_conflict_do_nothing(constraint="uq_concordance_system_ext_canonical")
                session.execute(stmt)

            # Add aliases
            if record.title:
                normalized = normalize_conventional_name(record.title)
                if normalized:
                    stmt = pg_insert(Alias).values(
                        canonical_id=canonical_id,
                        alias_text=record.title,
                        alias_normalized=normalized,
                        alias_type="conventional_name",
                        confidence="auto",
                    ).on_conflict_do_nothing(constraint="uq_aliases_text_canonical")
                    session.execute(stmt)

            stats.records_imported += 1

            # Track by collection and script
            coll = record.collection
            stats.by_collection[coll] = stats.by_collection.get(coll, 0) + 1
            script = record.script_type or "unclassified"
            stats.by_script[script] = stats.by_script.get(script, 0) + 1

            if stats.records_imported % BATCH_SIZE == 0:
                session.commit()
                logger.info("Imported %d records...", stats.records_imported)

        except Exception as e:
            logger.error("Error importing %s: %s", record.filename, e)
            stats.errors += 1

    session.commit()
    return stats


def _generate_canonical_id(record: PapyriRecord) -> str:
    """Generate a deterministic canonical_id for a papyri.info record."""
    if record.tm_id:
        return f"aeg_papyri_tm{record.tm_id}"
    if record.idno:
        # Clean up the idno for use as ID
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", record.idno).strip("_")
        return f"aeg_papyri_{clean}"
    # Fallback: hash of filename
    import hashlib
    h = hashlib.sha256(record.filename.encode()).hexdigest()[:12]
    return f"aeg_papyri_{h}"


def run_full_import(clone_dir: str = DEFAULT_CLONE_DIR) -> ConnectorStats:
    """Run the complete papyri.info import pipeline.

    1. Clone/update idp.data repo
    2. Scan for Egyptian-language texts
    3. Parse EpiDoc XML
    4. Import into central store
    """
    logger.info("=== Papyri.info Import Pipeline ===")

    # Step 1: Clone/update
    actual_dir = clone_idp_data(clone_dir)

    # Step 2: Scan for Egyptian texts
    candidates = scan_for_egyptian_texts(actual_dir)

    stats = ConnectorStats()
    stats.xml_files_scanned = len(candidates)

    if not candidates:
        logger.warning("No Egyptian-language XML files found")
        return stats

    # Step 3: Parse
    parsed_records = []
    for filepath in candidates:
        record = parse_epidoc_xml(filepath)
        if record is not None:
            parsed_records.append(record)

    stats.egyptian_candidates = len(parsed_records)
    logger.info("Parsed %d Egyptian-language records from %d XML files",
                len(parsed_records), len(candidates))

    if not parsed_records:
        return stats

    # Step 4: Import
    session = SessionLocal()
    try:
        import_stats = import_records(parsed_records, session)
        # Merge stats
        stats.records_imported = import_stats.records_imported
        stats.records_skipped = import_stats.records_skipped
        stats.errors = import_stats.errors
        stats.by_collection = import_stats.by_collection
        stats.by_script = import_stats.by_script
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("=== Import Complete ===")
    logger.info("  XML files scanned: %d", stats.xml_files_scanned)
    logger.info("  Egyptian candidates: %d", stats.egyptian_candidates)
    logger.info("  Records imported: %d", stats.records_imported)
    logger.info("  Records skipped: %d", stats.records_skipped)
    logger.info("  Errors: %d", stats.errors)
    logger.info("  By collection: %s", stats.by_collection)
    logger.info("  By script: %s", stats.by_script)

    return stats
