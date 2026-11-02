"""CLI entry point for the papyri.info connector.

Usage:
    PYTHONPATH=. python3 -m importers.papyri_info [command]

Commands:
    clone   - Clone/update the idp.data repo (shallow)
    scan    - Scan for Egyptian-language XML files
    import  - Parse and import Egyptian texts into DB
    full    - Run the complete pipeline (clone + scan + import)
    stats   - Show import statistics
"""

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("papyri_info")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    from importers.papyri_info.connector import (
        DEFAULT_CLONE_DIR,
        clone_idp_data,
        run_full_import,
        scan_for_egyptian_texts,
    )

    if cmd == "clone":
        path = clone_idp_data()
        log.info("Cloned to: %s", path)

    elif cmd == "scan":
        candidates = scan_for_egyptian_texts()
        log.info("Found %d Egyptian-language XML files", len(candidates))
        for c in candidates[:20]:
            log.info("  %s", c)
        if len(candidates) > 20:
            log.info("  ... and %d more", len(candidates) - 20)

    elif cmd in ("import", "full"):
        stats = run_full_import()
        print(json.dumps(stats.summary(), indent=2))

    elif cmd == "stats":
        from sqlalchemy import text as sql_text
        from core.models import SessionLocal
        session = SessionLocal()
        count = session.execute(
            sql_text("SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_papyri_%'")
        ).scalar()
        layers = session.execute(
            sql_text(
                "SELECT count(*) FROM representation_layers "
                "WHERE source = 'papyri.info'"
            )
        ).scalar()
        concordance = session.execute(
            sql_text(
                "SELECT count(*) FROM concordance c "
                "JOIN texts t ON c.canonical_id = t.canonical_id "
                "WHERE t.canonical_id LIKE 'aeg_papyri_%'"
            )
        ).scalar()
        log.info("Papyri.info records: %d texts, %d layers, %d concordance entries",
                 count, layers, concordance)
        session.close()

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
