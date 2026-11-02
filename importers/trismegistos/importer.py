"""Trismegistos TexRelations concordance enricher.

Not a text importer — queries the TM TexRelations API for cross-references
to partner projects (DDBDP, HGV, LDAB, PHI, etc.) and inserts new
concordance links for existing texts.

Source: https://www.trismegistos.org/dataservices/texrelations/
License: CC BY-SA 3.0
Rate limit: 1 req/sec (polite default)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text as sql_text

from core.models import Concordance, SessionLocal
from importers import pg_flush

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

BATCH_SIZE = 500
API_BASE = "https://www.trismegistos.org/dataservices/texrelations"
USER_AGENT = "Aegyptus/1.0 (academic corpus builder)"
SLEEP_SEC = 1.0  # 1 req/sec polite rate
CACHE_DIR = os.environ.get(
    "TM_CACHE_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "tm_texrelations"),
)

# Map TM partner keys to our external_system names
PARTNER_MAP = {
    "DDBDP": "ddbdp",
    "HGV": "hgv",
    "LDAB": "ldab",
    "PHI": "phi",
    "BritishMuseum": "british_museum",
    "CDLI": "cdli",
    "EDCS": "edcs",
    "EDH": "edh",
    "Achemenet": "achemenet",
    "Orient": "orient",
    "SAAO": "saao",
    "Penn_Museum": "penn_museum",
    "Berliner_papyri": "berliner_papyri",
    "Köln_papyri": "koeln_papyri",
    "PapPal": "pappal",
    "ISic": "isic",
    "IRT": "irt",
    "DBMNT": "dbmnt",
    "APIS": "apis",
}


def fetch_texrelations(client: httpx.Client, tm_id: str, cache_dir: Path) -> list[dict]:
    """Fetch cross-references for a TM ID. Returns list of {system, ext_id}."""
    cache_file = cache_dir / f"{tm_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            data = None
    else:
        data = None

    if data is None:
        try:
            resp = client.get(f"{API_BASE}/{tm_id}", timeout=30)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

            with open(cache_file, "w") as fh:
                json.dump(data, fh)

            time.sleep(SLEEP_SEC)
        except Exception as e:
            log.debug("Error fetching TM %s: %s", tm_id, e)
            return []

    # Parse response — list of {partner_name: [ids]} dicts
    links = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                for partner, ids in entry.items():
                    if partner == "TM_ID" or partner == "Message":
                        continue
                    if ids is None:
                        continue
                    system = PARTNER_MAP.get(partner, partner.lower())
                    if isinstance(ids, list):
                        for ext_id in ids:
                            links.append({"system": system, "ext_id": str(ext_id)})
                    elif isinstance(ids, str):
                        links.append({"system": system, "ext_id": ids})
    elif isinstance(data, dict):
        if "Message" in data:
            return []

    return links


def main():
    """Entry point for Trismegistos concordance enrichment."""
    start = time.time()
    log.info("=" * 60)
    log.info("Trismegistos TexRelations Concordance Enrichment")
    log.info("=" * 60)

    cache_dir = Path(CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = SessionLocal()
    try:
        # Get all existing TM concordance entries
        log.info("Loading existing TM concordance entries...")
        tm_entries = session.execute(
            sql_text("""
                SELECT DISTINCT canonical_id, external_id
                FROM concordance
                WHERE external_system IN ('TM', 'trismegistos')
                ORDER BY external_id
            """)
        ).fetchall()
        log.info("Found %d TM concordance entries to enrich", len(tm_entries))

        # Check which are already cached
        cached = sum(1 for _, tm_id in tm_entries if (cache_dir / f"{tm_id}.json").exists())
        log.info("Cached: %d / %d", cached, len(tm_entries))

        # Pre-load existing concordance to avoid dups
        existing_conc = set(
            (row[0], row[1], row[2]) for row in session.execute(
                sql_text("SELECT canonical_id, external_system, external_id FROM concordance")
            ).fetchall()
        )
        log.info("Existing concordance entries: %d", len(existing_conc))

        inserted = 0
        errors = 0
        skipped = 0
        conc_batch = []

        with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
            for idx, (canonical_id, tm_id) in enumerate(tm_entries, 1):
                links = fetch_texrelations(client, tm_id, cache_dir)

                for link in links:
                    key = (canonical_id, link["system"], link["ext_id"])
                    if key in existing_conc:
                        skipped += 1
                        continue

                    conc_batch.append({
                        "canonical_id": canonical_id,
                        "external_system": link["system"],
                        "external_id": link["ext_id"],
                        "relationship": "exact_match",
                    })
                    existing_conc.add(key)

                if len(conc_batch) >= BATCH_SIZE:
                    inserted += pg_flush(session, Concordance.__table__, conc_batch)
                    conc_batch.clear()

                if idx % 500 == 0:
                    elapsed = time.time() - start
                    rate = idx / elapsed if elapsed > 0 else 0
                    eta = (len(tm_entries) - idx) / rate if rate > 0 else 0
                    log.info(
                        "Progress: %d/%d TM IDs | %d new links, %d skipped | %.1f/s, ETA %.0fs",
                        idx, len(tm_entries), inserted, skipped, rate, eta,
                    )

        # Flush remaining
        if conc_batch:
            inserted += pg_flush(session, Concordance.__table__, conc_batch)

        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("Trismegistos enrichment complete.")
        log.info("  TM IDs queried: %d", len(tm_entries))
        log.info("  New links:      %d", inserted)
        log.info("  Skipped (dup):  %d", skipped)
        log.info("  Errors:         %d", errors)
        log.info("  Elapsed:        %.1f seconds", elapsed)
        log.info("=" * 60)

    except Exception:
        log.exception("Fatal error during enrichment")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
