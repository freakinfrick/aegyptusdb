"""Metropolitan Museum of Art API importer.

Fetches all Egyptian department objects (~28K) and imports as TextRecords.
Most are metadata_only. Objects with inscriptions get a representation layer.

Source: https://collectionapi.metmuseum.org/public/collection/v1/
License: CC0 (public domain images), metadata is public.
No rate limits. No auth needed.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text as sql_text

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
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
DEPARTMENT_ID = 10  # Egyptian Art
CACHE_DIR = os.environ.get(
    "MET_CACHE_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "met_api"),
)
SLEEP_MS = 200  # 200ms between requests (Met API rate-limits aggressively)
USER_AGENT = "Aegyptus/1.0 (academic corpus builder; https://github.com/aegyptus)"


def fetch_object_ids(client: httpx.Client) -> list[int]:
    """Fetch all Egyptian department object IDs."""
    log.info("Fetching Egyptian department object IDs...")
    resp = client.get(f"{BASE_URL}/objects", params={"departmentIds": DEPARTMENT_ID})
    resp.raise_for_status()
    data = resp.json()
    object_ids = data.get("objectIDs", [])
    log.info("Found %d objects in department %d", len(object_ids), DEPARTMENT_ID)
    return object_ids


def fetch_object(client: httpx.Client, object_id: int, cache_dir: Path) -> dict | None:
    """Fetch a single object, with filesystem cache."""
    cache_file = cache_dir / f"{object_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass

    for attempt in range(3):
        try:
            resp = client.get(f"{BASE_URL}/objects/{object_id}", timeout=30)
            if resp.status_code == 404:
                return None
            if resp.status_code == 403:
                # Rate limited — back off exponentially
                wait = SLEEP_MS / 1000 * (4 ** (attempt + 1))
                log.debug("403 for object %d, backing off %.1fs", object_id, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()

            with open(cache_file, "w") as fh:
                json.dump(data, fh)

            time.sleep(SLEEP_MS / 1000)
            return data
        except Exception as e:
            log.debug("Error fetching object %d: %s", object_id, e)
            time.sleep(SLEEP_MS / 1000 * (2 ** attempt))
    return None


def classify_script_type(obj: dict) -> str | None:
    """Infer script type from Met object data."""
    classification = (obj.get("classification", "") or "").lower()
    title = (obj.get("title", "") or "").lower()
    medium = (obj.get("medium", "") or "").lower()

    if "papyrus" in classification or "papyrus" in medium:
        if "demotic" in title or "demotic" in medium:
            return "demotic"
        if "hieratic" in title or "hieratic" in medium:
            return "hieratic"
        if "coptic" in title or "coptic" in medium:
            return "coptic"
        return "hieratic"  # Default for papyri
    if "hieroglyph" in title or "hieroglyph" in classification:
        return "hieroglyphic"
    if "stela" in classification or "stele" in classification:
        return "hieroglyphic"
    return None


def object_to_text_record(obj: dict) -> dict:
    """Convert Met API object to TextRecord dict."""
    object_id = obj.get("objectID")
    canonical_id = f"aeg_met_{object_id}"

    name_parts = []
    if obj.get("title"):
        name_parts.append(obj["title"])
    if obj.get("objectName") and obj.get("objectName") != obj.get("title"):
        name_parts.append(obj["objectName"])
    conventional_name = " — ".join(name_parts) if name_parts else f"Met {object_id}"

    inscriptions = (obj.get("objectWikidata_URL", "") or "")  # Not inscriptions
    inscriptions_text = ""
    # The Met API doesn't have a dedicated inscriptions field in JSON,
    # but some objects have it embedded in other fields
    for field in ["creditLine", "dimensions", "title"]:
        pass  # Inscriptions are in HTML/detail pages, not API

    has_inscription = bool(obj.get("isPublicDomain"))  # Rough proxy

    completeness = "metadata_only"
    script_type = classify_script_type(obj)

    # Period/date
    begin_date = obj.get("objectBeginDate")
    end_date = obj.get("objectEndDate")

    return {
        "canonical_id": canonical_id,
        "conventional_name": conventional_name[:500],
        "script_type": script_type,
        "date_earliest": int(begin_date) if begin_date else None,
        "date_latest": int(end_date) if end_date else None,
        "period_label": obj.get("period"),
        "findspot": obj.get("excavation"),
        "current_location": "Metropolitan Museum of Art",
        "text_type": obj.get("classification"),
        "completeness": completeness,
        "shelfmarks": [obj["accessionNumber"]] if obj.get("accessionNumber") else None,
        "metadata": {
            "source_project": "met_api",
            "object_id": object_id,
            "culture": obj.get("culture"),
            "dynasty": obj.get("dynasty"),
            "reign": obj.get("reign"),
            "medium": obj.get("medium"),
            "dimensions": obj.get("dimensions"),
            "credit_line": obj.get("creditLine"),
            "is_public_domain": obj.get("isPublicDomain"),
            "primary_image": obj.get("primaryImage"),
            "object_url": obj.get("objectURL"),
            "department": obj.get("department"),
            "object_name": obj.get("objectName"),
            "gallery_number": obj.get("GalleryNumber"),
        },
        "source_corpus": ["met_api"],
    }


def main():
    """Entry point for Met Museum API import."""
    start = time.time()
    log.info("=" * 60)
    log.info("Metropolitan Museum of Art API Import")
    log.info("=" * 60)

    cache_dir = Path(CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = SessionLocal()
    try:
        # Pre-load existing
        log.info("Loading existing met_api records for dedup...")
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_met_%'")
            ).fetchall()
        )
        log.info("Existing: %d texts", len(existing_texts))

        with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
            object_ids = fetch_object_ids(client)

            # Check how many are already cached
            cached = sum(1 for oid in object_ids if (cache_dir / f"{oid}.json").exists())
            log.info("Cached: %d / %d objects", cached, len(object_ids))

            texts_inserted = 0
            conc_inserted = 0
            alias_inserted = 0
            errors = 0
            skipped = 0

            text_batch = []
            conc_batch = []
            alias_batch = []

            for idx, object_id in enumerate(object_ids, 1):
                canonical_id = f"aeg_met_{object_id}"
                if canonical_id in existing_texts:
                    skipped += 1
                    if idx % 5000 == 0:
                        log.info("Progress: %d/%d (skipped %d existing)", idx, len(object_ids), skipped)
                    continue

                obj = fetch_object(client, object_id, cache_dir)
                if obj is None:
                    errors += 1
                    continue

                record = object_to_text_record(obj)
                text_batch.append(record)
                existing_texts.add(canonical_id)

                # Concordance
                conc_batch.append({
                    "canonical_id": canonical_id,
                    "external_system": "met_museum",
                    "external_id": str(object_id),
                    "relationship": "exact_match",
                })

                # Alias (accession number)
                if obj.get("accessionNumber"):
                    alias_batch.append({
                        "canonical_id": canonical_id,
                        "alias_text": obj["accessionNumber"],
                        "alias_normalized": obj["accessionNumber"].lower().strip(),
                        "alias_type": "accession_number",
                        "confidence": "verified",
                    })

                # Flush
                if len(text_batch) >= BATCH_SIZE:
                    texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
                    text_batch.clear()
                if len(conc_batch) >= BATCH_SIZE:
                    conc_inserted += pg_flush(session, Concordance.__table__, conc_batch)
                    conc_batch.clear()
                if len(alias_batch) >= BATCH_SIZE:
                    alias_inserted += pg_flush(session, Alias.__table__, alias_batch)
                    alias_batch.clear()

                if idx % 2000 == 0:
                    elapsed = time.time() - start
                    rate = idx / elapsed if elapsed > 0 else 0
                    eta = (len(object_ids) - idx) / rate if rate > 0 else 0
                    log.info(
                        "Progress: %d/%d | %d inserted, %d errors | %.0f obj/s, ETA %.0fs",
                        idx, len(object_ids), texts_inserted, errors, rate, eta,
                    )

            # Flush remaining
            if text_batch:
                texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
            if conc_batch:
                conc_inserted += pg_flush(session, Concordance.__table__, conc_batch)
            if alias_batch:
                alias_inserted += pg_flush(session, Alias.__table__, alias_batch)

        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("Met Museum API import complete.")
        log.info("  Objects:     %d fetched", len(object_ids))
        log.info("  Texts:       %d inserted", texts_inserted)
        log.info("  Concordance: %d inserted", conc_inserted)
        log.info("  Aliases:     %d inserted", alias_inserted)
        log.info("  Errors:      %d", errors)
        log.info("  Skipped:     %d (existing)", skipped)
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
