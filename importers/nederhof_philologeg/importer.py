"""Nederhof PhilologEg corpus importer.

Extracts 94 Egyptian texts from the PhilologEg JAR (corpus embedded
directly — no separate download). Imports into:
  - texts: one record per text
  - sentences: transliteration + English translation pairs
  - representation_layers: hieroglyphic (RES → Unicode converted in-house)
  - aliases: text names + manuscript names
  - concordance: nederhof external_system

The JAR contains Nederhof's St Andrews Corpus: Middle Kingdom literary
texts (Sinuhe, Shipwrecked Sailor, Eloquent Peasant, Ptahhotep, Westcar,
Ebers, Merneptah Stela, Hymn to the Sun, Tuthmosis III annals, etc.)
with sentence-level English translations and hieroglyphic encodings.

PhilologEg is the direct spiritual predecessor of Aegyptus: same goal
(unified corpus of Egyptian texts), smaller scope (94 canonical texts
vs 77K+), desktop Java app rather than a database. This importer
inherits its work.

Source: PhilologEg-0.5.14.jar (corpus/texts/, corpus/resources/)
Corpus by: Mark-Jan Nederhof, University of St Andrews
License: Academic use. Contact author for redistribution.
Idempotent: pre-load dedup, INSERT ON CONFLICT DO NOTHING.
"""

import html
import logging
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

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

BATCH_SIZE = 200
JAR_PATH = os.environ.get(
    "PHILOLOGEG_JAR",
    str(Path(__file__).resolve().parents[2] / "data" / "upstream" / "PhilologEg-0.5.14.jar"),
)
# Also check Downloads if not in data/upstream
JAR_FALLBACK = str(Path.home() / "Downloads" / "PhilologEg-0.5.14.jar")


# ── RES → Unicode converter ──────────────────────────────────────────

def load_sign_map(zf: zipfile.ZipFile) -> dict[str, str]:
    """Load Gardiner sign → Unicode codepoint map from signunicode.xml."""
    xml = zf.read("data/fonts/signunicode.xml").decode("utf-8", errors="replace")
    root = ET.fromstring(xml)
    sign_map = {}
    for sign in root.findall("sign"):
        sign_id = sign.get("id", "")
        code = sign.get("code", "")
        if sign_id and code:
            try:
                sign_map[sign_id] = chr(int(code, 16))
            except ValueError:
                pass
    log.info("Loaded %d sign→Unicode mappings", len(sign_map))
    return sign_map


def res_to_unicode(res_string: str, sign_map: dict[str, str]) -> str:
    """Convert a RES-encoded hieroglyphic segment to Unicode characters.

    RES format: sign codes separated by structural operators
    (-, :, *, [hrl], etc.). We extract Gardiner sign codes and map them.
    """
    if not res_string:
        return ""

    # Strip layout directives: [hrl], [hlr], [vrl], etc.
    s = re.sub(r'\[.*?\]', ' ', res_string)
    # Strip color directives: ![red], ![black]
    s = re.sub(r'!\[.*?\]', '', s)
    # Strip position directives: <pos...>
    s = re.sub(r'<pos[^>]*>', '', s)
    # Strip insert directives: insert[b](D,d) → extract the sign IDs inside
    s = re.sub(r'insert\[.\]\(([^)]+)\)', lambda m: ' '.join(m.group(1).split(',')), s)
    # Strip coord directives: <coord id="N"/>
    s = re.sub(r'<coord[^/]*/>', '', s)
    # Strip mirror/rotate/scale qualifiers on signs: A1[mirror] → A1
    s = re.sub(r'\[mirror\]|\[rotate\]|\[scale=[^\]]*\]|\[.*?\]', '', s)
    # Structural operators that separate signs
    s = re.sub(r'[-:*+!^#&@{}()\[\]|\\/<>]', ' ', s)
    # Extract tokens
    tokens = s.split()
    glyphs = []
    for tok in tokens:
        tok = tok.strip()
        if tok in sign_map:
            glyphs.append(sign_map[tok])
        elif re.match(r'^[A-Z][a-z]?\d+[a-z]?$', tok):
            # Looks like a Gardiner code not in map — skip silently
            pass
    return "".join(glyphs)


# ── Tr.txt parser ────────────────────────────────────────────────────

def parse_tr_txt(content: str) -> tuple[dict, list[dict]]:
    """Parse a PhilologEg Tr.txt resource file.

    Returns (meta, sentences) where meta has creator/name/language/scheme fields
    and each sentence dict has {seq, transliteration, translation_en, line_ref}.
    """
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Parse header key=value lines
    meta = {}
    body_start = 0
    for i, line in enumerate(lines):
        if "=" in line and i < 30:
            k, _, v = line.partition("=")
            meta[k.strip()] = v.strip()
        if line.strip() == "###":
            body_start = i + 1
            # Second ### is end of bibliography
            if i > 5:
                break

    # Skip bibliography block (up to second ###)
    second_hash = None
    for i in range(body_start, len(lines)):
        if lines[i].strip() == "###":
            second_hash = i
            break
    if second_hash is not None:
        body_start = second_hash + 1

    # Parse alternating transliteration/translation pairs separated by ;
    body_lines = lines[body_start:]
    sentences = []
    seq = 0
    i = 0
    while i < len(body_lines):
        # Skip blank lines
        if not body_lines[i].strip():
            i += 1
            continue

        # Collect transliteration (everything up to lone ';')
        translit_parts = []
        line_refs = []
        while i < len(body_lines) and body_lines[i].strip() != ";":
            raw = body_lines[i].strip()
            if not raw:
                i += 1
                continue
            # Extract line references like <1>, <3>, etc.
            refs = re.findall(r'<(\d+[a-z]?)>', raw)
            line_refs.extend(refs)
            # Remove line refs and clean HTML entities
            clean = re.sub(r'<\d+[a-z]?>', '', raw).strip()
            clean = html.unescape(clean)
            if clean:
                translit_parts.append(clean)
            i += 1

        if i >= len(body_lines):
            break

        # Skip the ';'
        i += 1

        # Collect translation (everything up to next transliteration block)
        # Translation ends at blank line or next token that looks like translit
        trans_parts = []
        while i < len(body_lines) and body_lines[i].strip() != ";":
            raw = body_lines[i].strip()
            if not raw:
                i += 1
                # Blank line can mean end of translation segment
                if trans_parts:
                    break
                continue
            clean = html.unescape(raw)
            # Strip simple HTML tags
            clean = re.sub(r'<[^>]+>', '', clean).strip()
            if clean:
                trans_parts.append(clean)
            i += 1

        # Skip ';' if we landed on one (some files have ';' after translation)
        if i < len(body_lines) and body_lines[i].strip() == ";":
            i += 1

        translit = " ".join(translit_parts).strip()
        translation = " ".join(trans_parts).strip()

        if translit or translation:
            seq += 1
            sentences.append({
                "seq": seq,
                "transliteration": translit if translit else None,
                "translation_en": translation if translation else None,
                "line_refs": line_refs if line_refs else None,
            })

    return meta, sentences


# ── Hi.xml parser ────────────────────────────────────────────────────

def parse_hi_xml(content: str, sign_map: dict[str, str]) -> list[str]:
    """Parse a PhilologEg Hi.xml file and return list of Unicode glyph strings per segment."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    glyphs_per_segment = []
    for segment in root.findall(".//segment"):
        texthi = segment.find("texthi")
        if texthi is not None:
            raw = "".join(texthi.itertext()).strip()
            unicode_str = res_to_unicode(raw, sign_map)
            if unicode_str:
                glyphs_per_segment.append(unicode_str)

    return glyphs_per_segment


# ── Text manifest parser ─────────────────────────────────────────────

def parse_text_xml(content: str) -> dict:
    """Parse a corpus/texts/*.xml manifest to extract metadata and resource links."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {}

    meta = {
        "description": root.get("description", ""),
        "name": None,
        "language": None,
        "collections": [],
        "tr_resources": [],   # *Tr.txt paths
        "hi_resources": [],   # *Hi.xml paths
    }

    primary = root.find("primary")
    if primary is not None:
        meta["name"] = primary.get("name", "")
        meta["language"] = primary.get("language", "")

    for coll in root.findall("collection"):
        meta["collections"].append({
            "kind": coll.get("kind", ""),
            "collect": coll.get("collect", ""),
            "section": coll.get("section", ""),
        })

    for res in root.findall("resource"):
        loc = res.get("location", "")
        # Normalise relative path: ../resources/X → corpus/resources/X
        norm = re.sub(r'^\.\./', 'corpus/', loc)
        if norm.endswith("Hi.xml"):
            meta["hi_resources"].append(norm)
        elif norm.endswith("Tr.txt"):
            meta["tr_resources"].append(norm)

    return meta


# ── Script type inference ────────────────────────────────────────────

def infer_script(description: str, name: str) -> str | None:
    """Infer script type from PhilologEg text description field."""
    desc = (description or "").lower()
    name_l = (name or "").lower()
    if "hiero" in desc:
        return "hieroglyphic"
    if "hieratic" in name_l or "hieratic" in desc:
        return "hieratic"
    if "demotic" in desc:
        return "demotic"
    # Default for classical literary texts: hieroglyphic
    return "hieroglyphic"


# ── Main ─────────────────────────────────────────────────────────────

def main():
    start = time.time()
    log.info("=" * 60)
    log.info("Nederhof PhilologEg Corpus Import")
    log.info("=" * 60)

    # Find JAR
    jar_path = JAR_PATH
    if not Path(jar_path).exists():
        jar_path = JAR_FALLBACK
    if not Path(jar_path).exists():
        log.error("PhilologEg JAR not found. Set PHILOLOGEG_JAR env var or place at:")
        log.error("  %s", JAR_PATH)
        log.error("  %s", JAR_FALLBACK)
        sys.exit(1)
    log.info("JAR: %s", jar_path)

    session = SessionLocal()
    try:
        # Pre-load existing for dedup
        log.info("Loading existing nederhof_philologeg records for dedup...")
        existing_texts = set(
            row[0] for row in session.execute(
                sql_text("SELECT canonical_id FROM texts WHERE canonical_id LIKE 'aeg_nederhof_philologeg_%'")
            ).fetchall()
        )
        existing_sentences = set(
            row[0] for row in session.execute(
                sql_text("SELECT source_id FROM sentences WHERE source = 'nederhof_philologeg'")
            ).fetchall()
        )
        log.info("Existing: %d texts, %d sentences", len(existing_texts), len(existing_sentences))

        with zipfile.ZipFile(jar_path) as zf:
            all_names = set(zf.namelist())
            sign_map = load_sign_map(zf)

            # Read corpus manifest
            corpus_xml = zf.read("corpus/corpus.xml").decode("utf-8", errors="replace")
            corpus_root = ET.fromstring(corpus_xml)
            text_entries = [
                e.get("location", "") for e in corpus_root.findall("text")
            ]
            # Normalise: texts/Foo.xml → corpus/texts/Foo.xml
            text_entries = [f"corpus/{e}" for e in text_entries if e]
            log.info("Corpus manifest: %d texts", len(text_entries))

            texts_inserted = 0
            sentences_inserted = 0
            layers_inserted = 0
            aliases_inserted = 0
            conc_inserted = 0

            text_batch, sent_batch, layer_batch, alias_batch, conc_batch = [], [], [], [], []

            for text_loc in text_entries:
                if text_loc not in all_names:
                    log.debug("Missing: %s", text_loc)
                    continue

                raw_meta = zf.read(text_loc).decode("utf-8", errors="replace")
                meta = parse_text_xml(raw_meta)
                if not meta.get("name"):
                    continue

                slug = Path(text_loc).stem  # e.g. "Shipwrecked"
                canonical_id = f"aeg_nederhof_philologeg_{slug}"

                # Infer script type
                script_type = infer_script(meta["description"], meta["name"])

                if canonical_id not in existing_texts:
                    # Build bibliography note
                    biblio = "; ".join(
                        f"{c['collect']} {c['section']}".strip()
                        for c in meta["collections"] if c.get("collect")
                    )
                    text_batch.append({
                        "canonical_id": canonical_id,
                        "conventional_name": meta["name"],
                        "script_type": script_type,
                        "completeness": "complete",
                        "metadata": {
                            "source_project": "nederhof_philologeg",
                            "philologeg_slug": slug,
                            "description": meta["description"],
                            "bibliography": biblio or None,
                            "philologeg_version": "0.5.14",
                            "curator": "Mark-Jan Nederhof, University of St Andrews",
                        },
                        "source_corpus": ["nederhof_philologeg"],
                    })
                    existing_texts.add(canonical_id)

                    alias_batch.append({
                        "canonical_id": canonical_id,
                        "alias_text": meta["name"],
                        "alias_normalized": meta["name"].strip().lower(),
                        "alias_type": "conventional_name",
                        "confidence": "verified",
                    })
                    alias_batch.append({
                        "canonical_id": canonical_id,
                        "alias_text": slug,
                        "alias_normalized": slug.lower(),
                        "alias_type": "philologeg_slug",
                        "confidence": "verified",
                    })
                    conc_batch.append({
                        "canonical_id": canonical_id,
                        "external_system": "nederhof_philologeg",
                        "external_id": slug,
                        "relationship": "exact_match",
                    })

                # Parse English translations from Tr.txt resources
                # Use the first Tr.txt (canonical version)
                all_sentences = []
                for tr_path in meta["tr_resources"][:1]:  # primary translation only
                    if tr_path not in all_names:
                        continue
                    tr_raw = zf.read(tr_path).decode("utf-8", errors="replace")
                    tr_meta, sents = parse_tr_txt(tr_raw)
                    for s in sents:
                        source_id = f"{canonical_id}-{s['seq']}"
                        if source_id in existing_sentences:
                            continue
                        all_sentences.append({
                            "canonical_id": canonical_id,
                            "sequence_num": s["seq"],
                            "transliteration": s["transliteration"],
                            "translation": {"en": s["translation_en"]} if s["translation_en"] else None,
                            "source": "nederhof_philologeg",
                            "source_id": source_id,
                            "source_detail": {
                                "line_refs": s["line_refs"],
                                "tr_resource": tr_path,
                                "translator": tr_meta.get("name"),
                                "version": tr_meta.get("version"),
                            } if s["line_refs"] else None,
                            "confidence": "verified",
                        })
                        existing_sentences.add(source_id)

                sent_batch.extend(all_sentences)

                # Parse hieroglyphic layers from Hi.xml resources
                for hi_path in meta["hi_resources"]:
                    if hi_path not in all_names:
                        continue
                    hi_raw = zf.read(hi_path).decode("utf-8", errors="replace")
                    glyph_segments = parse_hi_xml(hi_raw, sign_map)
                    if glyph_segments:
                        layer_batch.append({
                            "canonical_id": canonical_id,
                            "layer_type": "hieroglyphic",
                            "content": {
                                "segments": glyph_segments,
                                "full_text": "".join(glyph_segments),
                                "hi_resource": hi_path,
                                "encoding": "unicode_egyptian",
                            },
                            "language": "egy",
                            "source": "nederhof_philologeg",
                            "source_detail": {"hi_path": hi_path},
                            "confidence": "verified",
                        })

                # Flush when batches fill — texts always first (FK)
                if text_batch:
                    texts_inserted += pg_flush(session, TextRecord.__table__, text_batch,
                                             conflict_cols=["canonical_id"])
                    text_batch.clear()
                if alias_batch:
                    aliases_inserted += pg_flush(session, Alias.__table__, alias_batch)
                    alias_batch.clear()
                if conc_batch:
                    conc_inserted += pg_flush(session, Concordance.__table__, conc_batch)
                    conc_batch.clear()
                if len(sent_batch) >= BATCH_SIZE:
                    sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)
                    sent_batch.clear()
                if len(layer_batch) >= BATCH_SIZE:
                    layers_inserted += pg_flush(session, RepresentationLayer.__table__, layer_batch)
                    layer_batch.clear()

        # Flush remaining
        if text_batch:
            texts_inserted += pg_flush(session, TextRecord.__table__, text_batch,
                                     conflict_cols=["canonical_id"])
        if alias_batch:
            aliases_inserted += pg_flush(session, Alias.__table__, alias_batch)
        if conc_batch:
            conc_inserted += pg_flush(session, Concordance.__table__, conc_batch)
        if sent_batch:
            sentences_inserted += pg_flush(session, Sentence.__table__, sent_batch)
        if layer_batch:
            layers_inserted += pg_flush(session, RepresentationLayer.__table__, layer_batch)

        elapsed = time.time() - start
        log.info("=" * 60)
        log.info("Nederhof PhilologEg import complete.")
        log.info("  Texts:       %d inserted", texts_inserted)
        log.info("  Sentences:   %d inserted", sentences_inserted)
        log.info("  Hiero layers:%d inserted", layers_inserted)
        log.info("  Aliases:     %d inserted", aliases_inserted)
        log.info("  Concordance: %d inserted", conc_inserted)
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
