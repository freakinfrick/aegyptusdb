"""Nederhof/hierojax importer.

Imports 120 Unicode hieroglyphic texts from nederhof.github.io/hierojax/texts.
Each HTML file contains hieroglyphic text in Unicode (U+13000-U+1342F block)
within <span class="hierojax"> elements.

Inserts each text as:
  - texts: one canonical record per file (aeg_nederhof_{identifier})
  - representation_layers: hieroglyphic layer with the Unicode content

Idempotent: skips existing records on re-run.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import text as sql_text

from core.models import RepresentationLayer, SessionLocal, TextRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nederhof_importer")

DATA_DIR = os.environ.get(
    "NEDERHOF_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "nederhof_hierojax"),
)


def filename_to_identifier(filename: str) -> str:
    """Convert a filename like 'PBerlin3023.html' to a stable identifier.

    Returns lowercase, e.g. 'pberlin3023'.
    """
    return filename.replace(".html", "").lower()


def classify_text(filename: str, title: str) -> dict:
    """Infer script_type, text_type, and shelfmarks from filename/title."""
    info = {}

    # Script type: all Nederhof texts are hieroglyphic
    info["script_type"] = "hieroglyphic"

    # Determine text type and shelfmarks from prefix patterns
    fname = filename.replace(".html", "")

    if fname.startswith("UrkIV"):
        info["text_type"] = "historical"
        num = fname.replace("UrkIV", "")
        info["shelfmarks"] = [f"Urk. IV {num}"]
    elif fname.startswith("CT"):
        info["text_type"] = "religious"
    elif fname.startswith("P") and re.match(r"P[A-Z]", fname):
        info["text_type"] = "literary"
        # Extract shelfmark from title (e.g., "P. Berlin 3023")
        if title:
            info["shelfmarks"] = [title]
    elif fname.startswith("O") and re.match(r"O[A-Z]", fname):
        info["text_type"] = "administrative"
        if title:
            info["shelfmarks"] = [title]
    elif fname.startswith("Stela"):
        info["text_type"] = "funerary"
        if title:
            info["shelfmarks"] = [title]
    elif fname.startswith("BritishMuseum"):
        info["text_type"] = None
        if title:
            info["shelfmarks"] = [title]

    return info


def parse_hierojax_html(filepath: str) -> dict | None:
    """Parse a Nederhof hierojax HTML file.

    Returns dict with:
      - title: page <title> text
      - lines: list of (line_number, hieroglyphic_text) tuples
      - full_text: concatenated hieroglyphic content
      - source_note: attribution text if found
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Extract attribution from first <p> tag
    source_note = None
    first_p = soup.find("p")
    if first_p:
        source_note = first_p.get_text(strip=True)

    # Extract hieroglyphic spans
    lines = []
    hierojax_spans = soup.find_all("span", class_="hierojax")

    for span in hierojax_spans:
        text = span.get_text(strip=True)
        if not text:
            continue

        # Find the preceding line number span
        prev = span.find_previous_sibling("span")
        line_num = None
        if prev:
            num_text = prev.get_text(strip=True)
            m = re.match(r"\((\d+)\)", num_text)
            if m:
                line_num = int(m.group(1))

        lines.append((line_num, text))

    if not lines:
        return None

    full_text = "\n".join(text for _, text in lines)

    return {
        "title": title,
        "lines": lines,
        "full_text": full_text,
        "source_note": source_note,
    }


def main():
    log.info("Nederhof/hierojax importer starting")
    log.info("Data directory: %s", DATA_DIR)

    if not os.path.isdir(DATA_DIR):
        log.error("Data directory not found: %s", DATA_DIR)
        log.error("Download texts first or set NEDERHOF_DATA_DIR")
        sys.exit(1)

    html_files = sorted(
        f for f in os.listdir(DATA_DIR) if f.endswith(".html")
    )
    log.info("Found %d HTML files to import", len(html_files))

    session = SessionLocal()

    try:
        # Pre-load existing IDs
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_nederhof_%'")
            ).fetchall()
        )
        existing_layers = set(
            (row[0], row[1]) for row in session.execute(
                sql_text(
                    "SELECT canonical_id, source FROM representation_layers "
                    "WHERE source = 'nederhof'"
                )
            ).fetchall()
        )

        stats = {
            "texts_inserted": 0,
            "texts_skipped": 0,
            "layers_inserted": 0,
            "parse_errors": 0,
            "empty_files": 0,
        }

        t_start = time.time()

        for i, fname in enumerate(html_files, start=1):
            identifier = filename_to_identifier(fname)
            canonical_id = f"aeg_nederhof_{identifier}"

            filepath = os.path.join(DATA_DIR, fname)
            parsed = parse_hierojax_html(filepath)

            if parsed is None:
                log.warning("No hieroglyphic content in %s", fname)
                stats["empty_files"] += 1
                continue

            title = parsed["title"]
            classification = classify_text(fname, title)

            # Insert text record
            if canonical_id not in existing_texts:
                text_record = TextRecord(
                    canonical_id=canonical_id,
                    conventional_name=title,
                    script_type=classification.get("script_type"),
                    text_type=classification.get("text_type"),
                    shelfmarks=classification.get("shelfmarks"),
                    extra_metadata={
                        "source": "nederhof_hierojax",
                        "filename": fname,
                        "source_note": parsed.get("source_note"),
                        "line_count": len(parsed["lines"]),
                        "license": "GPL-3.0 (tooling); text provenance needs clarification",
                    },
                )
                session.add(text_record)
                session.flush()
                existing_texts.add(canonical_id)
                stats["texts_inserted"] += 1
            else:
                stats["texts_skipped"] += 1

            # Insert hieroglyphic representation layer
            layer_key = (canonical_id, "nederhof")
            if layer_key not in existing_layers:
                # Store line-by-line with line numbers for positional reference
                lines_data = []
                for line_num, text in parsed["lines"]:
                    entry = {"text": text}
                    if line_num is not None:
                        entry["line"] = line_num
                    lines_data.append(entry)

                layer = RepresentationLayer(
                    canonical_id=canonical_id,
                    layer_type="hieroglyphic",
                    content={
                        "full_text": parsed["full_text"],
                        "lines": lines_data,
                        "encoding": "unicode",
                    },
                    language=None,
                    source="nederhof",
                    source_detail={
                        "url": f"https://nederhof.github.io/hierojax/texts/{fname}",
                        "conversion": "automatic from RES/St Andrews Corpus via HieroJax",
                    },
                    confidence="unreviewed",  # Automatically converted, awaits manual validation
                )
                session.add(layer)
                existing_layers.add(layer_key)
                stats["layers_inserted"] += 1

            if i % 50 == 0:
                session.commit()
                log.info("Progress: %d/%d files", i, len(html_files))

        session.commit()

        elapsed = time.time() - t_start
        log.info(
            "Nederhof import complete in %.1fs: texts=%d (skipped=%d) layers=%d "
            "empty=%d errors=%d",
            elapsed,
            stats["texts_inserted"], stats["texts_skipped"],
            stats["layers_inserted"], stats["empty_files"],
            stats["parse_errors"],
        )

        # Print final counts
        total_texts = session.execute(
            sql_text("SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_nederhof_%'")
        ).scalar()
        total_layers = session.execute(
            sql_text("SELECT count(*) FROM representation_layers WHERE source = 'nederhof'")
        ).scalar()
        log.info("Total Nederhof texts: %d, layers: %d", total_texts, total_layers)

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()
