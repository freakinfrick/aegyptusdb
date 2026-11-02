"""RAMSES corpus importer.

Imports the Ramses Transliteration Corpus from Zenodo (DOI: 10.5281/zenodo.4954597).
The corpus contains paired source (Gardiner glyph codes) and target (transliteration)
files, organized as line-based sentence pairs.

Data splits: train (66,693), test (2,729), val (1,841) = 71,263 sentence pairs total.

Inserts as:
  - texts: one record per unique text group (batched by source, not per-sentence)
  - sentences: one per line pair with source MdC and target transliteration
  - representation_layers: summary transliteration layer per text record

LICENSE NOTE:
  The README and cc-by-nc-sa.png in the archive clearly state CC BY-NC-SA 4.0.
  The Zenodo record metadata says CC BY 4.0. This is a license inconsistency.
  We follow the more restrictive license (CC BY-NC-SA 4.0) as stated by the
  authors in their own README. All records are tagged accordingly.

Idempotent: skips existing records on re-run.
"""

import logging
import os
import sys
import time
from pathlib import Path

from sqlalchemy import text as sql_text

from core.models import RepresentationLayer, Sentence, SessionLocal, TextRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ramses_importer")

DATA_DIR = os.environ.get(
    "RAMSES_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "ramses" / "ramses-trl" / "data"),
)

BATCH_SIZE = 1000

# Splits to import and their file pairs
SPLITS = [
    ("train", "src-train.txt", "tgt-train.txt"),
    ("test", "src-test.txt", "tgt-test.txt"),
    ("val", "src-val.txt", "tgt-val.txt"),
]

LICENSE_DOC = """
RAMSES Transliteration Corpus License Documentation
====================================================

Source: Zenodo DOI 10.5281/zenodo.4954597
Authors: Universite de Liege/Projet Ramses & Serge Rosmorduc

LICENSE INCONSISTENCY:
- The README.md in the archive and the included cc-by-nc-sa.png image
  clearly state: CC BY-NC-SA 4.0 (Creative Commons Attribution-NonCommercial-ShareAlike)
- The Zenodo record metadata field says: CC BY 4.0 (Creative Commons Attribution)

RESOLUTION:
We follow the more restrictive license (CC BY-NC-SA 4.0) as stated by the
authors in their own README. The Zenodo metadata appears to be an error or
oversight during upload.

IMPLICATIONS:
- Non-commercial use only
- Attribution required: "the Ramses transliteration corpus V. 2019-09-01,
  University of Liege/Projet Ramses"
- Derivative works must use the same license (ShareAlike)

CITATION:
Serge Rosmorduc (2020), "Automated Transliteration of Late Egyptian Using
Neural Networks: An Experiment in 'Deep Learning'", Lingua Aegyptia 28 (233-257).
DOI: https://doi.org/10.37011/lingaeg.28.07
"""


def load_file_lines(filepath: str) -> list[str]:
    """Load lines from a file, stripping trailing whitespace."""
    with open(filepath, encoding="utf-8") as f:
        return [line.rstrip("\n").rstrip() for line in f]


def transliteration_from_target(tgt_line: str) -> str:
    """Convert space-separated transliteration chars back to readable form.

    Target format: 'h r w _ p n' where _ = word separator
    Output: 'hrw pn'
    """
    chars = tgt_line.split()
    words = []
    current_word = []
    for ch in chars:
        if ch == "_":
            if current_word:
                words.append("".join(current_word))
                current_word = []
        else:
            current_word.append(ch)
    if current_word:
        words.append("".join(current_word))
    return " ".join(words)


def main():
    log.info("RAMSES corpus importer starting")
    log.info("Data directory: %s", DATA_DIR)

    if not os.path.isdir(DATA_DIR):
        log.error("Data directory not found: %s", DATA_DIR)
        log.error("Download from Zenodo: https://zenodo.org/records/4954597")
        sys.exit(1)

    # Write license documentation
    license_path = Path(DATA_DIR).parent / "LICENSE_NOTES.txt"
    license_path.write_text(LICENSE_DOC)
    log.info("License documentation written to %s", license_path)

    session = SessionLocal()

    try:
        # Pre-load existing IDs
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_ramses_%'")
            ).fetchall()
        )
        existing_sentences = set(
            (row[0], row[1]) for row in session.execute(
                sql_text(
                    "SELECT canonical_id, source_id FROM sentences WHERE source = 'ramses'"
                )
            ).fetchall()
        )

        stats = {
            "texts_inserted": 0,
            "texts_skipped": 0,
            "sentences_inserted": 0,
            "sentences_skipped": 0,
            "layers_inserted": 0,
        }

        t_start = time.time()

        for split_name, src_file, tgt_file in SPLITS:
            src_path = os.path.join(DATA_DIR, src_file)
            tgt_path = os.path.join(DATA_DIR, tgt_file)

            if not os.path.exists(src_path) or not os.path.exists(tgt_path):
                log.warning("Missing files for split %s: %s / %s", split_name, src_file, tgt_file)
                continue

            src_lines = load_file_lines(src_path)
            tgt_lines = load_file_lines(tgt_path)

            if len(src_lines) != len(tgt_lines):
                log.error(
                    "Line count mismatch in %s: src=%d tgt=%d",
                    split_name, len(src_lines), len(tgt_lines),
                )
                continue

            log.info("Processing split %s: %d sentence pairs", split_name, len(src_lines))

            # Create one text record per split
            canonical_id = f"aeg_ramses_{split_name}"

            if canonical_id not in existing_texts:
                text_record = TextRecord(
                    canonical_id=canonical_id,
                    conventional_name=f"RAMSES Corpus ({split_name} split)",
                    script_type="hieratic",  # RAMSES covers Late Egyptian, mostly hieratic
                    text_type=None,
                    extra_metadata={
                        "source": "ramses",
                        "split": split_name,
                        "sentence_count": len(src_lines),
                        "zenodo_doi": "10.5281/zenodo.4954597",
                        "corpus_version": "2019-09-01",
                        "license": "CC BY-NC-SA 4.0",
                        "license_note": (
                            "README states CC BY-NC-SA 4.0; Zenodo metadata says CC BY 4.0. "
                            "Following the more restrictive author-stated license."
                        ),
                        "attribution": (
                            "the Ramses transliteration corpus V. 2019-09-01, "
                            "University of Liege/Projet Ramses"
                        ),
                    },
                )
                session.add(text_record)
                session.flush()
                existing_texts.add(canonical_id)
                stats["texts_inserted"] += 1
            else:
                stats["texts_skipped"] += 1

            # Insert sentences
            for seq, (src_line, tgt_line) in enumerate(zip(src_lines, tgt_lines), start=1):
                if not src_line.strip() and not tgt_line.strip():
                    continue

                source_id = f"ramses_{split_name}_{seq}"
                sent_key = (canonical_id, source_id)

                if sent_key in existing_sentences:
                    stats["sentences_skipped"] += 1
                    continue

                transliteration = transliteration_from_target(tgt_line)

                sentence = Sentence(
                    canonical_id=canonical_id,
                    sequence_num=seq,
                    transliteration=transliteration,
                    translation=None,
                    tokens=[{
                        "gardiner_codes": src_line.strip(),
                        "transliteration_raw": tgt_line.strip(),
                    }],
                    source="ramses",
                    source_id=source_id,
                    source_detail={
                        "split": split_name,
                        "src_file": src_file,
                        "tgt_file": tgt_file,
                    },
                    confidence="verified",
                )
                session.add(sentence)
                existing_sentences.add(sent_key)
                stats["sentences_inserted"] += 1

                if stats["sentences_inserted"] % BATCH_SIZE == 0:
                    session.commit()
                    if stats["sentences_inserted"] % 10000 == 0:
                        log.info(
                            "  %s: %d/%d sentences inserted",
                            split_name, stats["sentences_inserted"], len(src_lines),
                        )

            session.commit()

            # Insert a transliteration representation layer per split
            existing_layers = set(
                (row[0], row[1]) for row in session.execute(
                    sql_text(
                        "SELECT canonical_id, source FROM representation_layers "
                        "WHERE source = 'ramses' AND canonical_id = :cid"
                    ),
                    {"cid": canonical_id},
                ).fetchall()
            )

            if (canonical_id, "ramses") not in existing_layers:
                # Store summary stats rather than repeating all sentences
                layer = RepresentationLayer(
                    canonical_id=canonical_id,
                    layer_type="transliteration",
                    content={
                        "format": "mdc_to_transliteration_pairs",
                        "sentence_count": len(src_lines),
                        "encoding": "gardiner_codes -> space_separated_transliteration",
                        "note": "Individual sentences stored in sentences table",
                    },
                    language=None,
                    source="ramses",
                    source_detail={
                        "zenodo_doi": "10.5281/zenodo.4954597",
                        "split": split_name,
                        "license": "CC BY-NC-SA 4.0",
                    },
                    confidence="verified",
                )
                session.add(layer)
                stats["layers_inserted"] += 1

            session.commit()
            log.info("Split %s complete", split_name)

        elapsed = time.time() - t_start
        log.info(
            "RAMSES import complete in %.1fs: texts=%d (skipped=%d) "
            "sentences=%d (skipped=%d) layers=%d",
            elapsed,
            stats["texts_inserted"], stats["texts_skipped"],
            stats["sentences_inserted"], stats["sentences_skipped"],
            stats["layers_inserted"],
        )

        # Final counts
        total_texts = session.execute(
            sql_text("SELECT count(*) FROM texts WHERE canonical_id LIKE 'aeg_ramses_%'")
        ).scalar()
        total_sents = session.execute(
            sql_text("SELECT count(*) FROM sentences WHERE source = 'ramses'")
        ).scalar()
        log.info("Total RAMSES texts: %d, sentences: %d", total_texts, total_sents)

    except Exception:
        log.exception("Fatal error during import")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()
