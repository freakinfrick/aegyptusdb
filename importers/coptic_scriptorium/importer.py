"""Coptic Scriptorium corpus importer.

Imports ~1,694 CoNLL-U files from 70+ corpus sections into:
  - texts: one record per document (# newdoc id)
  - sentences: with Coptic text, English translation, token-level annotation
  - aliases: document names

Source: data/upstream/coptic_scriptorium/
License: CC BY 4.0 (most sections)
Idempotent: pre-loads existing records, skips duplicates.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path

from sqlalchemy import text as sql_text

from core.models import (
    Alias,
    Concordance,
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
SENTENCE_BATCH_SIZE = 50  # CoNLL-U tokens produce large JSONB
DATA_DIR = os.environ.get(
    "COPTIC_SCRIPTORIUM_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "coptic_scriptorium"),
)


def make_canonical_id(corpus_dir: str, doc_id: str) -> str:
    """Generate canonical ID from corpus dir and document ID."""
    # Clean doc_id: replace colons, spaces with underscores
    slug = re.sub(r"[^a-zA-Z0-9._-]", "_", doc_id)
    return f"aeg_copcorp_{slug}"


def parse_conllu_file(filepath: Path) -> list[dict]:
    """Parse a CoNLL-U file into a list of document dicts.

    Each document dict has:
      doc_id, corpus_dir, sentences: [{sent_id, text, text_en, tokens}]
    """
    corpus_dir = filepath.parent.parent.name  # e.g. AP, bible, shenoute-eagerness

    documents = []
    current_doc = None
    current_sent = None

    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")

            if line.startswith("# newdoc id"):
                # Save previous doc
                if current_doc is not None:
                    if current_sent is not None:
                        current_doc["sentences"].append(current_sent)
                        current_sent = None
                    documents.append(current_doc)

                doc_id = line.split("=", 1)[1].strip() if "=" in line else filepath.stem
                current_doc = {
                    "doc_id": doc_id,
                    "corpus_dir": corpus_dir,
                    "sentences": [],
                }
                continue

            if line.startswith("# sent_id"):
                # Save previous sentence
                if current_sent is not None and current_doc is not None:
                    current_doc["sentences"].append(current_sent)

                sent_id = line.split("=", 1)[1].strip() if "=" in line else ""
                current_sent = {
                    "sent_id": sent_id,
                    "text": "",
                    "text_en": "",
                    "tokens": [],
                }
                continue

            if line.startswith("# text_en") and current_sent is not None:
                current_sent["text_en"] = line.split("=", 1)[1].strip() if "=" in line else ""
                continue

            if line.startswith("# text =") and current_sent is not None:
                current_sent["text"] = line.split("=", 1)[1].strip()
                continue

            if line.startswith("#"):
                continue  # Other comments

            if not line.strip():
                # Blank line = sentence boundary (already handled by # sent_id)
                continue

            # Token line
            if current_sent is None:
                continue

            fields = line.split("\t")
            if len(fields) < 10:
                continue

            token_id = fields[0]
            # Skip multi-word token lines (e.g. "1-2")
            if "-" in token_id:
                continue

            form = fields[1]
            lemma = fields[2]
            upos = fields[3]
            xpos = fields[4]
            feats = fields[5] if fields[5] != "_" else None
            misc = fields[9] if len(fields) > 9 and fields[9] != "_" else None

            token = {"form": form, "lemma": lemma, "pos": upos, "xpos": xpos}
            if feats:
                token["features"] = feats
            if misc:
                # Extract Orig and OrigLang from MISC field
                for part in misc.split("|"):
                    if part.startswith("Orig="):
                        token["orig"] = part[5:]
                    elif part.startswith("OrigLang="):
                        token["orig_lang"] = part[9:]
                    elif part.startswith("Entity="):
                        token["entity"] = part[7:]

            current_sent["tokens"].append(token)

    # Save last document/sentence
    if current_sent is not None and current_doc is not None:
        current_doc["sentences"].append(current_sent)
    if current_doc is not None:
        documents.append(current_doc)

    # If no # newdoc id found, create a single document from the file
    if not documents and current_sent is not None:
        documents.append({
            "doc_id": f"{corpus_dir}:{filepath.stem}",
            "corpus_dir": corpus_dir,
            "sentences": [current_sent] if current_sent else [],
        })

    return documents


def main():
    """Entry point for Coptic Scriptorium import."""
    start = time.time()
    log.info("=" * 60)
    log.info("Coptic Scriptorium Import")
    log.info("=" * 60)

    data_path = Path(DATA_DIR)
    if not data_path.exists():
        log.error("Data directory not found: %s", data_path)
        sys.exit(1)

    # Find all CoNLL-U files
    conllu_files = sorted(data_path.rglob("*.conllu"))
    log.info("Found %d CoNLL-U files", len(conllu_files))

    session = SessionLocal()
    try:
        # Pre-load existing for dedup
        log.info("Loading existing coptic_scriptorium records for dedup...")
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_copcorp_%'")
            ).fetchall()
        )
        existing_sentences = set(
            row[0] for row in session.execute(
                sql_text("SELECT source_id FROM sentences WHERE source = 'coptic_scriptorium'")
            ).fetchall()
        )
        log.info("Existing: %d texts, %d sentences", len(existing_texts), len(existing_sentences))

        texts_inserted = 0
        sentences_inserted = 0
        aliases_inserted = 0
        parse_errors = 0
        total_docs = 0

        text_batch = []
        sent_batch = []
        alias_batch = []

        for file_idx, conllu_file in enumerate(conllu_files, 1):
            try:
                documents = parse_conllu_file(conllu_file)
            except Exception as e:
                log.debug("Error parsing %s: %s", conllu_file.name, e)
                parse_errors += 1
                continue

            for doc in documents:
                canonical_id = make_canonical_id(doc["corpus_dir"], doc["doc_id"])
                total_docs += 1

                if canonical_id not in existing_texts:
                    text_batch.append({
                        "canonical_id": canonical_id,
                        "conventional_name": doc["doc_id"],
                        "script_type": "coptic",
                        "completeness": "unknown",
                        "metadata": {
                            "dialect": "sahidic",
                            "corpus_section": doc["corpus_dir"],
                            "source_project": "coptic_scriptorium",
                        },
                        "source_corpus": ["coptic_scriptorium"],
                    })
                    existing_texts.add(canonical_id)

                    # Alias
                    normalized = re.sub(r"\s+", " ", doc["doc_id"].strip().lower())
                    alias_batch.append({
                        "canonical_id": canonical_id,
                        "alias_text": doc["doc_id"],
                        "alias_normalized": normalized,
                        "alias_type": "conventional_name",
                        "confidence": "auto",
                    })

                for seq, sent in enumerate(doc["sentences"], 1):
                    source_id = sent["sent_id"] or f"{doc['doc_id']}-{seq}"
                    if source_id in existing_sentences:
                        continue

                    translation = {}
                    if sent["text_en"]:
                        translation["en"] = sent["text_en"]

                    sent_batch.append({
                        "canonical_id": canonical_id,
                        "sequence_num": seq,
                        "transliteration": sent["text"] if sent["text"] else None,
                        "translation": translation if translation else None,
                        "tokens": sent["tokens"] if sent["tokens"] else None,
                        "source": "coptic_scriptorium",
                        "source_id": source_id,
                        "confidence": "verified",
                    })
                    existing_sentences.add(source_id)

                # Flush texts before dependents
                if len(text_batch) >= BATCH_SIZE or len(sent_batch) >= SENTENCE_BATCH_SIZE:
                    if text_batch:
                        texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
                        text_batch.clear()
                    if alias_batch:
                        aliases_inserted += pg_flush(session, Alias.__table__, alias_batch)
                        alias_batch.clear()
                if len(sent_batch) >= SENTENCE_BATCH_SIZE:
                    sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)
                    sent_batch.clear()

            if file_idx % 200 == 0:
                log.info(
                    "Progress: %d/%d files, %d docs | %d texts, %d sentences inserted",
                    file_idx, len(conllu_files), total_docs,
                    texts_inserted, sentences_inserted,
                )

        # Flush remaining
        if text_batch:
            texts_inserted += pg_flush(session, TextRecord.__table__, text_batch, ["canonical_id"])
        if alias_batch:
            aliases_inserted += pg_flush(session, Alias.__table__, alias_batch)
        if sent_batch:
            sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)

        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("Coptic Scriptorium import complete.")
        log.info("  Documents:   %d found", total_docs)
        log.info("  Texts:       %d inserted", texts_inserted)
        log.info("  Sentences:   %d inserted", sentences_inserted)
        log.info("  Aliases:     %d inserted", aliases_inserted)
        log.info("  Parse errors:%d files skipped", parse_errors)
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
