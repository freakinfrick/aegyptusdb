"""Aegyptus CLI -- unified command-line interface for the Egyptian text corpus.

Single entry point for all corpus operations. Designed for AI agent consumption:
  - JSON to stdout by default (--pretty for human-readable)
  - Stderr for logs, stdout for data
  - No interactive prompts -- everything via flags
  - Exit codes: 0 success, 1 error, 2 partial/no-results

Install: pip install -e .
Usage:   aegyptus <command> [options]
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

import click

# ---------------------------------------------------------------------------
# Globals and helpers
# ---------------------------------------------------------------------------

DB_URL = os.environ.get("DB_URL", "postgresql://aegyptus:dev@localhost:5434/aegyptus")

# Route all log output to stderr so stdout stays clean JSON
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("aegyptus")


def _get_session():
    """Lazy import and create a DB session."""
    from core.models import SessionLocal
    return SessionLocal()


def _output(data, pretty=False):
    """Write JSON to stdout. If pretty, use indentation."""
    if pretty:
        click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    else:
        click.echo(json.dumps(data, default=str, ensure_ascii=False))


def _serialize_text(row) -> dict:
    """Serialize a TextRecord ORM instance to a plain dict."""
    return {
        "canonical_id": row.canonical_id,
        "conventional_name": row.conventional_name,
        "script_type": row.script_type,
        "date_earliest": row.date_earliest,
        "date_latest": row.date_latest,
        "period_label": row.period_label,
        "findspot": row.findspot,
        "current_location": row.current_location,
        "text_type": row.text_type,
        "completeness": row.completeness,
        "shelfmarks": row.shelfmarks,
        "source_corpus": list(row.source_corpus) if row.source_corpus else [],
        "metadata": row.extra_metadata,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_sentence(row) -> dict:
    """Serialize a Sentence ORM instance to a plain dict."""
    return {
        "id": row.id,
        "canonical_id": row.canonical_id,
        "sequence_num": row.sequence_num,
        "transliteration": row.transliteration,
        "translation": row.translation,
        "tokens": row.tokens,
        "source": row.source,
        "source_id": row.source_id,
        "source_detail": row.source_detail,
        "confidence": row.confidence,
        "created_at": row.created_at,
    }


def _serialize_layer(row) -> dict:
    """Serialize a RepresentationLayer ORM instance to a plain dict."""
    return {
        "id": row.id,
        "canonical_id": row.canonical_id,
        "layer_type": row.layer_type,
        "content": row.content,
        "language": row.language,
        "source": row.source,
        "source_detail": row.source_detail,
        "confidence": row.confidence,
        "created_at": row.created_at,
    }


def _serialize_concordance(row) -> dict:
    """Serialize a Concordance ORM instance to a plain dict."""
    return {
        "id": row.id,
        "canonical_id": row.canonical_id,
        "external_system": row.external_system,
        "external_id": row.external_id,
        "relationship": row.relationship,
    }


def _serialize_alias(row) -> dict:
    """Serialize an Alias ORM instance to a plain dict."""
    return {
        "id": row.id,
        "canonical_id": row.canonical_id,
        "alias_text": row.alias_text,
        "alias_normalized": row.alias_normalized,
        "alias_type": row.alias_type,
        "confidence": row.confidence,
    }


def _serialize_gap(row) -> dict:
    """Serialize a Gap ORM instance to a plain dict."""
    return {
        "id": row.id,
        "canonical_id": row.canonical_id,
        "external_system": row.external_system,
        "external_id": row.external_id,
        "gap_type": row.gap_type,
        "priority": row.priority,
        "recommended_action": row.recommended_action,
        "status": row.status,
        "assigned_to": row.assigned_to,
        "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group(
    help="""Aegyptus -- unified CLI for the open corpus of ancient Egyptian texts.

All commands output JSON to stdout. Logs go to stderr.
Use --pretty on any command for indented, human-readable output.

Exit codes: 0 = success, 1 = error, 2 = no results / partial.

EXAMPLES:

  aegyptus status
  aegyptus search -q sinuhe --limit 5 --pretty
  aegyptus show --text aeg_oraec_320
  aegyptus resolve --system tla --id VJNVFJJMOBARXFXZJHBWVGUXZQ
  aegyptus import --status
  aegyptus translate --limit 1 --no-save
  aegyptus gaps --limit 10 --pretty
"""
)
@click.version_option("0.1.0", prog_name="aegyptus")
def cli():
    pass


# ---------------------------------------------------------------------------
# aegyptus status
# ---------------------------------------------------------------------------

@cli.command(
    help="""Corpus statistics.

Returns a JSON object with row counts for all tables, plus breakdowns by
source, script type, layer type, confidence, and sentence source.

OUTPUT FORMAT (JSON object):
  {
    "texts": <int>,
    "sentences": <int>,
    "representation_layers": <int>,
    "concordance": <int>,
    "aliases": <int>,
    "gaps": <int>,
    "corpus_versions": <int>,
    "crawl_queue": <int>,
    "breakdowns": {
      "texts_by_source": {"oraec": N, ...},
      "texts_by_script_type": {"hieroglyphic": N, ...},
      "texts_by_text_type": {...},
      "layers_by_type": {"transliteration": N, ...},
      "layers_by_confidence": {"verified": N, ...},
      "sentences_by_source": {"oraec": N, ...},
      "sentences_by_confidence": {"verified": N, ...},
      "concordance_by_system": {"tla": N, ...}
    }
  }

EXIT CODES:
  0  Success
  1  Database connection error

EXAMPLES:
  aegyptus status
  aegyptus status --pretty
"""
)
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output with indentation.")
def status(pretty):
    from sqlalchemy import text as sa_text
    session = _get_session()
    try:
        result = {}

        # Table counts
        for table in ("texts", "sentences", "representation_layers", "concordance",
                       "aliases", "gaps", "corpus_versions", "crawl_queue"):
            try:
                result[table] = session.execute(sa_text(f"SELECT count(*) FROM {table}")).scalar() or 0
            except Exception:
                result[table] = 0
                session.rollback()

        # Breakdowns
        breakdowns = {}

        rows = session.execute(sa_text(
            "SELECT split_part(canonical_id, '_', 2) AS src, count(*) "
            "FROM texts GROUP BY src ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["texts_by_source"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT script_type, count(*) FROM texts WHERE script_type IS NOT NULL "
            "GROUP BY script_type ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["texts_by_script_type"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT text_type, count(*) FROM texts WHERE text_type IS NOT NULL "
            "GROUP BY text_type ORDER BY count(*) DESC LIMIT 20"
        )).fetchall()
        breakdowns["texts_by_text_type"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT layer_type, count(*) FROM representation_layers "
            "GROUP BY layer_type ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["layers_by_type"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT confidence, count(*) FROM representation_layers "
            "GROUP BY confidence ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["layers_by_confidence"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT source, count(*) FROM sentences GROUP BY source ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["sentences_by_source"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT confidence, count(*) FROM sentences GROUP BY confidence ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["sentences_by_confidence"] = {r[0]: r[1] for r in rows}

        rows = session.execute(sa_text(
            "SELECT external_system, count(*) FROM concordance "
            "GROUP BY external_system ORDER BY count(*) DESC"
        )).fetchall()
        breakdowns["concordance_by_system"] = {r[0]: r[1] for r in rows}

        result["breakdowns"] = breakdowns
        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus search
# ---------------------------------------------------------------------------

@cli.command(
    help="""Find texts by any criteria. Returns a JSON array of matching records.

Filters are combined with AND logic. At least one filter should be specified,
or you get the first --limit records ordered by canonical_id.

FILTER OPTIONS:
  -q/--query        Search conventional_name (case-insensitive LIKE)
  --script-type     Filter by script type
  --text-type       Filter by text type (e.g., "Grab", "Tempel")
  --period          Filter by period label (substring match)
  --date-from       Earliest date (integer, negative = BCE)
  --date-to         Latest date (integer, negative = BCE)
  --source          Filter by source_corpus array membership (texts can belong to
                    multiple: oraec|aes|tla_hf|aed_tei|nederhof_philologeg|coptic_scriptorium|met_api|ramses|manual|ad_hoc)
  --has-layer       Only texts that have this layer type
  --has-translation Only texts with translation in this language code
  --orphan          If set, only texts with zero concordance links

PAGINATION:
  --limit           Max results (default: 50)
  --offset          Skip first N results (default: 0)

OUTPUT CONTROL:
  --fields          Comma-separated field list (default: canonical_id,conventional_name,script_type)
  --count           Return only the match count as {"count": N}
  --pretty          Pretty-print JSON

VALID --script-type VALUES:
  hieroglyphic, hieratic, demotic, coptic, greek, multiple

VALID --has-layer VALUES:
  hieroglyphic, transliteration, translation, lemmatization

VALID --source VALUES:
  oraec, aes, tla_hf, aed_tei, nederhof_philologeg, coptic_scriptorium,
  met_api, ramses, manual, ad_hoc

OUTPUT FORMAT (JSON array unless --count):
  [
    {"canonical_id": "aeg_oraec_320", "conventional_name": "...", "script_type": "..."},
    ...
  ]

EXIT CODES:
  0  Results found
  1  Error
  2  No results matching filters

EXAMPLES:
  aegyptus search -q sinuhe --limit 3
  aegyptus search --source oraec --has-layer translation --limit 10
  aegyptus search --script-type hieratic --count
  aegyptus search --orphan --limit 20 --pretty
  aegyptus search --period "New Kingdom" --fields canonical_id,conventional_name,period_label
  aegyptus search -q "berlin" --has-translation en
"""
)
@click.option("-q", "--query", default=None, help="Search conventional_name (case-insensitive substring).")
@click.option("--script-type", default=None,
              type=click.Choice(["hieroglyphic", "hieratic", "demotic", "coptic", "greek", "multiple"], case_sensitive=False),
              help="Filter by script type.")
@click.option("--text-type", default=None, help="Filter by text type (substring match).")
@click.option("--period", default=None, help="Filter by period label (substring match).")
@click.option("--date-from", default=None, type=int, help="Earliest date (integer, negative = BCE).")
@click.option("--date-to", default=None, type=int, help="Latest date (integer, negative = BCE).")
@click.option("--source", default=None,
              help="Filter by source_corpus array membership "
                   "(oraec|aes|tla_hf|aed_tei|nederhof_philologeg|"
                   "coptic_scriptorium|met_api|ramses|manual|ad_hoc).")
@click.option("--has-layer", default=None,
              type=click.Choice(["hieroglyphic", "transliteration", "translation", "lemmatization"], case_sensitive=False),
              help="Only texts that have this representation layer type.")
@click.option("--has-translation", default=None, help="Only texts with translation in this language code (e.g., en, de, fr).")
@click.option("--orphan", is_flag=True, help="Only texts with zero concordance links.")
@click.option("--limit", default=50, type=int, show_default=True, help="Max results to return.")
@click.option("--offset", default=0, type=int, show_default=True, help="Skip first N results.")
@click.option("--fields", default="canonical_id,conventional_name,script_type",
              show_default=True, help="Comma-separated list of fields to include in output.")
@click.option("--count", is_flag=True, help="Return only the match count as {\"count\": N}.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def search(query, script_type, text_type, period, date_from, date_to, source,
           has_layer, has_translation, orphan, limit, offset, fields, count, pretty):
    from sqlalchemy import text as sa_text
    session = _get_session()
    try:
        clauses = []
        params = {}

        if query:
            clauses.append("t.conventional_name ILIKE :q")
            params["q"] = f"%{query}%"
        if script_type:
            clauses.append("t.script_type = :script_type")
            params["script_type"] = script_type
        if text_type:
            clauses.append("t.text_type ILIKE :text_type")
            params["text_type"] = f"%{text_type}%"
        if period:
            clauses.append("t.period_label ILIKE :period")
            params["period"] = f"%{period}%"
        if date_from is not None:
            clauses.append("t.date_earliest >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            clauses.append("t.date_latest <= :date_to")
            params["date_to"] = date_to
        if source:
            clauses.append(":source_name = ANY(t.source_corpus)")
            params["source_name"] = source
        if has_layer:
            clauses.append(
                "EXISTS (SELECT 1 FROM representation_layers rl "
                "WHERE rl.canonical_id = t.canonical_id AND rl.layer_type = :layer_type)"
            )
            params["layer_type"] = has_layer
        if has_translation:
            clauses.append(
                "EXISTS (SELECT 1 FROM representation_layers rl "
                "WHERE rl.canonical_id = t.canonical_id "
                "AND rl.layer_type = 'translation' AND rl.language = :trans_lang)"
            )
            params["trans_lang"] = has_translation
        if orphan:
            clauses.append(
                "NOT EXISTS (SELECT 1 FROM concordance c WHERE c.canonical_id = t.canonical_id)"
            )

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        if count:
            sql = f"SELECT count(*) FROM texts t{where}"
            n = session.execute(sa_text(sql), params).scalar() or 0
            _output({"count": n}, pretty)
            if n == 0:
                sys.exit(2)
            return

        sql = f"SELECT t.* FROM texts t{where} ORDER BY t.canonical_id LIMIT :lim OFFSET :off"
        params["lim"] = limit
        params["off"] = offset
        rows = session.execute(sa_text(sql), params).fetchall()

        if not rows:
            _output([], pretty)
            sys.exit(2)

        # Get column names from the result
        from core.models import TextRecord
        field_list = [f.strip() for f in fields.split(",")]
        all_field_map = {
            "canonical_id": 0, "conventional_name": 1, "script_type": 2,
            "date_earliest": 3, "date_latest": 4, "period_label": 5,
            "findspot": 6, "current_location": 7, "text_type": 8,
            "completeness": 9, "shelfmarks": 10, "metadata": 11,
            "created_at": 12, "updated_at": 13,
        }

        results = []
        for row in rows:
            record = {}
            for f in field_list:
                f = f.strip()
                if f in all_field_map:
                    record[f] = row[all_field_map[f]]
                elif f == "extra_metadata":
                    record["metadata"] = row[all_field_map["metadata"]]
            results.append(record)

        _output(results, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus grep
# ---------------------------------------------------------------------------

@cli.command(
    help="""Regex search across transliterations, translations, and text names.

Searches the corpus using PostgreSQL regex (~* for case-insensitive). Targets
one column at a time via --field. Returns matching records with the matched
content highlighted in context.

FIELDS (--field):
  transliteration   Search sentence transliterations (default)
  translation       Search sentence translation text (all languages in JSONB)
  name              Search texts.conventional_name
  token             Search within sentence tokens JSONB (written_form field)

REGEX SYNTAX:
  PostgreSQL POSIX regex. Case-insensitive by default.
  .      Any character
  .*     Zero or more of anything
  ^      Start of string
  $      End of string
  [abc]  Character class
  \\b     Word boundary (double-escape in shell)

OUTPUT FORMAT (JSON array):
  transliteration/translation/token fields return sentence objects:
    [{"sentence_id": 1, "canonical_id": "...", "transliteration": "...", "match": "..."}]
  name field returns text objects:
    [{"canonical_id": "...", "conventional_name": "...", "script_type": "..."}]

EXIT CODES:
  0  Matches found
  1  Error (invalid regex, DB error)
  2  No matches

EXAMPLES:
  aegyptus grep "nswt-bj,tj"
  aegyptus grep "ḥtp-ḏj-nswt" --limit 20 --pretty
  aegyptus grep --field translation "offering formula"
  aegyptus grep --field name "papyrus.*berlin"
  aegyptus grep --field token "ꜥnḫ" --source oraec
  aegyptus grep "^jw" --limit 5 --pretty
""",
)
@click.argument("pattern")
@click.option(
    "--field",
    type=click.Choice(["transliteration", "translation", "name", "token"]),
    default="transliteration",
    help="Which field to search. [default: transliteration]",
)
@click.option("--source", type=str, default=None, help="Filter by source (oraec, aes, tla_hf, etc.).")
@click.option("--script-type", type=str, default=None, help="Filter by script type.")
@click.option("--limit", type=int, default=50, help="Max results. [default: 50]")
@click.option("--offset", type=int, default=0, help="Skip first N results. [default: 0]")
@click.option("--context/--no-context", default=True, help="Include surrounding text in output. [default: true]")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def grep(pattern, field, source, script_type, limit, offset, context, pretty):
    """Regex search across transliterations, translations, and text names."""
    from sqlalchemy import text as sa_text

    session = _get_session()
    try:
        if field == "name":
            query = """
                SELECT canonical_id, conventional_name, script_type, text_type, period_label
                FROM texts
                WHERE conventional_name ~* :pattern
            """
            params = {"pattern": pattern, "limit": limit, "offset": offset}
            if script_type:
                query += " AND script_type = :script_type"
                params["script_type"] = script_type
            query += " ORDER BY canonical_id LIMIT :limit OFFSET :offset"

            rows = session.execute(sa_text(query), params).fetchall()
            results = [
                {"canonical_id": r[0], "conventional_name": r[1], "script_type": r[2],
                 "text_type": r[3], "period_label": r[4]}
                for r in rows
            ]

        elif field == "translation":
            query = """
                SELECT s.id, s.canonical_id, s.transliteration, s.translation, s.source
                FROM sentences s
                WHERE s.translation::text ~* :pattern
            """
            params = {"pattern": pattern, "limit": limit, "offset": offset}
            if source:
                query += " AND s.source = :source"
                params["source"] = source
            query += " ORDER BY s.id LIMIT :limit OFFSET :offset"

            rows = session.execute(sa_text(query), params).fetchall()
            results = []
            for r in rows:
                obj = {"sentence_id": r[0], "canonical_id": r[1], "source": r[4]}
                if context:
                    obj["transliteration"] = r[2]
                    obj["translation"] = r[3]
                results.append(obj)

        elif field == "token":
            query = """
                SELECT s.id, s.canonical_id, s.transliteration, s.source
                FROM sentences s
                WHERE s.tokens::text ~* :pattern
            """
            params = {"pattern": pattern, "limit": limit, "offset": offset}
            if source:
                query += " AND s.source = :source"
                params["source"] = source
            query += " ORDER BY s.id LIMIT :limit OFFSET :offset"

            rows = session.execute(sa_text(query), params).fetchall()
            results = [
                {"sentence_id": r[0], "canonical_id": r[1], "transliteration": r[2], "source": r[3]}
                for r in rows
            ]

        else:  # transliteration (default)
            query = """
                SELECT s.id, s.canonical_id, s.transliteration, s.source, s.confidence
                FROM sentences s
                WHERE s.transliteration ~* :pattern
            """
            params = {"pattern": pattern, "limit": limit, "offset": offset}
            if source:
                query += " AND s.source = :source"
                params["source"] = source
            query += " ORDER BY s.id LIMIT :limit OFFSET :offset"

            rows = session.execute(sa_text(query), params).fetchall()
            results = [
                {"sentence_id": r[0], "canonical_id": r[1], "transliteration": r[2],
                 "source": r[3], "confidence": r[4]}
                for r in rows
            ]

        if not results:
            _output([], pretty)
            sys.exit(2)

        _output(results, pretty)

    except Exception as e:
        err_str = str(e)
        if "invalid regular expression" in err_str:
            _output({"error": f"Invalid regex: {pattern}", "detail": err_str}, pretty)
        else:
            _output({"error": err_str}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus show
# ---------------------------------------------------------------------------

@cli.command(
    help="""Full detail on one text or sentence.

Provide exactly one of --text or --sentence to select what to display.

For --text: returns the complete text record with all sentences, representation
layers, concordance links, and aliases.

For --sentence: returns a single sentence record with its tokens and translations.

OUTPUT FORMAT for --text (JSON object):
  {
    "text": { <all text fields> },
    "sentences": [ { <sentence fields> }, ... ],
    "layers": [ { <layer fields> }, ... ],
    "concordance": [ { <concordance fields> }, ... ],
    "aliases": [ { <alias fields> }, ... ]
  }

OUTPUT FORMAT for --sentence (JSON object):
  { "id": N, "canonical_id": "...", "transliteration": "...", ... }

EXIT CODES:
  0  Record found
  1  Error
  2  Record not found

EXAMPLES:
  aegyptus show --text aeg_oraec_320
  aegyptus show --text aeg_tla_hf_100 --pretty
  aegyptus show --sentence 42
"""
)
@click.option("--text", "text_id", default=None, help="Canonical ID of the text to show.")
@click.option("--sentence", "sentence_id", default=None, type=int, help="Sentence ID (integer primary key).")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def show(text_id, sentence_id, pretty):
    from sqlalchemy import text as sa_text
    from core.models import TextRecord, Sentence, RepresentationLayer, Concordance, Alias
    session = _get_session()
    try:
        if not text_id and sentence_id is None:
            _output({"error": "Provide exactly one of --text <canonical_id> or --sentence <id>."}, pretty)
            sys.exit(1)

        if text_id and sentence_id is not None:
            _output({"error": "Provide exactly one of --text or --sentence, not both."}, pretty)
            sys.exit(1)

        if sentence_id is not None:
            sent = session.query(Sentence).filter(Sentence.id == sentence_id).first()
            if not sent:
                _output({"error": f"Sentence {sentence_id} not found."}, pretty)
                sys.exit(2)
            _output(_serialize_sentence(sent), pretty)
            return

        # Text detail
        text_rec = session.query(TextRecord).filter(TextRecord.canonical_id == text_id).first()
        if not text_rec:
            _output({"error": f"Text '{text_id}' not found."}, pretty)
            sys.exit(2)

        sentences = (session.query(Sentence)
                     .filter(Sentence.canonical_id == text_id)
                     .order_by(Sentence.sequence_num)
                     .all())
        layers = (session.query(RepresentationLayer)
                  .filter(RepresentationLayer.canonical_id == text_id)
                  .all())
        concordance = (session.query(Concordance)
                       .filter(Concordance.canonical_id == text_id)
                       .all())
        aliases = (session.query(Alias)
                   .filter(Alias.canonical_id == text_id)
                   .all())

        result = {
            "text": _serialize_text(text_rec),
            "sentences": [_serialize_sentence(s) for s in sentences],
            "layers": [_serialize_layer(l) for l in layers],
            "concordance": [_serialize_concordance(c) for c in concordance],
            "aliases": [_serialize_alias(a) for a in aliases],
        }
        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus resolve
# ---------------------------------------------------------------------------

@cli.command(
    help="""Cross-reference lookup. Input any external ID, get canonical record(s).

Use --system and --id to look up by external identifier system, or use
--shelfmark to resolve a museum/collection shelfmark via the normalizer.

VALID --system VALUES:
  tla, trismegistos, oraec, aes, ramses, wikidata, karnak, papyri_info

OUTPUT FORMAT (JSON object):
  {
    "matches": [
      {
        "canonical_id": "aeg_oraec_320",
        "external_system": "tla",
        "external_id": "VJNVFJJMOBARXFXZJHBWVGUXZQ",
        "relationship": "exact_match"
      }
    ]
  }

  For --shelfmark:
  {
    "query": "P. Berlin 3022",
    "normalized": "berlin 3022",
    "matches": [ { <alias fields> } ]
  }

EXIT CODES:
  0  Match found
  1  Error
  2  No match

EXAMPLES:
  aegyptus resolve --system tla --id VJNVFJJMOBARXFXZJHBWVGUXZQ
  aegyptus resolve --system trismegistos --id 62185
  aegyptus resolve --system oraec --id oraec320
  aegyptus resolve --shelfmark "P. Berlin 3022"
  aegyptus resolve --shelfmark "Papyrus Westcar" --pretty
"""
)
@click.option("--system", default=None,
              type=click.Choice(["tla", "trismegistos", "oraec", "aes", "ramses", "wikidata", "karnak", "papyri_info"],
                                case_sensitive=False),
              help="External identifier system.")
@click.option("--id", "ext_id", default=None, help="External ID within the specified system.")
@click.option("--shelfmark", default=None, help="Museum/collection shelfmark to resolve via normalizer.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def resolve(system, ext_id, shelfmark, pretty):
    from sqlalchemy import text as sa_text
    from core.models import Concordance, Alias
    session = _get_session()
    try:
        if shelfmark:
            from core.concordance.normalizer import normalize_shelfmark
            normalized = normalize_shelfmark(shelfmark)
            rows = (session.query(Alias)
                    .filter(Alias.alias_type == "shelfmark",
                            Alias.alias_normalized == normalized)
                    .all())
            if not rows:
                # Try LIKE match
                rows = (session.query(Alias)
                        .filter(Alias.alias_type == "shelfmark",
                                Alias.alias_normalized.like(f"%{normalized}%"))
                        .limit(10)
                        .all())
            result = {
                "query": shelfmark,
                "normalized": normalized,
                "matches": [_serialize_alias(r) for r in rows],
            }
            _output(result, pretty)
            if not rows:
                sys.exit(2)
            return

        if not system or not ext_id:
            _output({"error": "Provide --system and --id, or --shelfmark."}, pretty)
            sys.exit(1)

        # Look up by system + external_id -- allow case-insensitive system match
        rows = (session.query(Concordance)
                .filter(Concordance.external_system.ilike(system),
                        Concordance.external_id == ext_id)
                .all())

        if not rows:
            # Also try with common aliases: tm -> trismegistos, TM -> Trismegistos
            alt_systems = {
                "trismegistos": ["Trismegistos", "TM", "tm"],
                "tla": ["TLA"],
                "oraec": ["ORAEC"],
            }
            for alt in alt_systems.get(system.lower(), []):
                rows = (session.query(Concordance)
                        .filter(Concordance.external_system == alt,
                                Concordance.external_id == ext_id)
                        .all())
                if rows:
                    break

        result = {"matches": [_serialize_concordance(r) for r in rows]}
        _output(result, pretty)
        if not rows:
            sys.exit(2)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus import
# ---------------------------------------------------------------------------

# Dependency order: ORAEC first (canonical TLA IDs), Trismegistos last.
IMPORT_ORDER = [
    "oraec", "aes", "tla-hf", "nederhof", "ramses", "papyri-info",
    "aed-dict", "aed-tei", "coptic-scriptorium", "met-api",
    "nederhof-philologeg", "trismegistos",
]


@cli.command(
    name="import",
    help="""Run corpus importers.

Runs one or all importers. Each importer reads upstream data and populates
the DB tables (texts, sentences, representation_layers, concordance).
All importers are idempotent -- safe to re-run.

VALID --source VALUES:
  oraec         ORAEC JSON corpus (13k+ texts)
  aes           Ancient Egyptian Sentences (links to ORAEC via TLA IDs)
  tla-hf        TLA Hugging Face premium sentences (30k+ sentences)
  nederhof      Nederhof Middle Egyptian texts
  ramses        RAMSES Late Egyptian corpus
  papyri-info   Papyri.info Egyptian texts
  aed-dict      AED dictionary (lemmata)
  aed-tei       AED-TEI corpus (hieroglyphic layers, German translations)
  coptic-scriptorium  Coptic Scriptorium CoNLL-U texts
  met-api       Metropolitan Museum objects (slow: rate-limited API)
  nederhof-philologeg PhilologEg St Andrews corpus (JAR placed by hand)
  trismegistos  Trismegistos concordance enrichment (run last)
  all           Run all importers in dependency order (the list above).
                A source whose data is missing is reported as an error
                and the run continues with the next one.

Use --status to see what has been imported without running anything.

OUTPUT FORMAT (JSON object):
  {
    "source": "oraec",
    "status": "complete",
    "stats": { <importer-specific stats> }
  }

  For --status:
  {
    "sources": {
      "oraec": {"texts": N, "sentences": N},
      ...
    },
    "total_texts": N,
    "total_sentences": N
  }

EXIT CODES:
  0  Import successful
  1  Error during import (with --source all: any importer failed)

EXAMPLES:
  aegyptus import --source oraec
  aegyptus import --source all
  aegyptus import --status
  aegyptus import --status --pretty
"""
)
@click.option("--source", default=None,
              type=click.Choice(IMPORT_ORDER + ["all"], case_sensitive=False),
              help="Which importer to run (required unless --status).")
@click.option("--status", "show_status", is_flag=True, help="Show import counts without running anything.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def import_cmd(source, show_status, pretty):
    from sqlalchemy import text as sa_text
    session = _get_session()
    try:
        if show_status:
            prefixes = {
                "oraec": "aeg_oraec_%",
                "aes": "aeg_aes_%",
                "tla_hf": "aeg_tla_hf_%",
                "nederhof": "aeg_nederhof_%",
                "ramses": "aeg_ramses_%",
                "papyri_info": "aeg_papyri_%",
                "aed_tei": "aeg_aedtei_%",
                "coptic_scriptorium": "aeg_copcorp_%",
                "met_api": "aeg_met_%",
                "nederhof_philologeg": "aeg_nederhof_philologeg_%",
                "trismegistos_enrich": "(enrichment)",
                "manual": "aeg_manual_%",
                "adhoc": "aeg_adhoc_%",
                "crawl": "aeg_crawl_%",
            }

            sources_data = {}
            total_texts = 0
            total_sentences = 0

            for src_name, prefix in prefixes.items():
                texts = session.execute(
                    sa_text("SELECT count(*) FROM texts WHERE canonical_id LIKE :p"),
                    {"p": prefix}
                ).scalar() or 0
                sentences = session.execute(
                    sa_text("SELECT count(*) FROM sentences WHERE canonical_id LIKE :p"),
                    {"p": prefix}
                ).scalar() or 0
                layers = session.execute(
                    sa_text("SELECT count(*) FROM representation_layers WHERE canonical_id LIKE :p"),
                    {"p": prefix}
                ).scalar() or 0
                concordance = session.execute(
                    sa_text("SELECT count(*) FROM concordance WHERE canonical_id LIKE :p"),
                    {"p": prefix}
                ).scalar() or 0

                sources_data[src_name] = {
                    "texts": texts,
                    "sentences": sentences,
                    "layers": layers,
                    "concordance": concordance,
                }
                total_texts += texts
                total_sentences += sentences

            result = {
                "sources": sources_data,
                "total_texts": total_texts,
                "total_sentences": total_sentences,
            }
            _output(result, pretty)
            session.close()
            return

        if not source:
            _output({"error": "Provide --source <name> or --status. Run aegyptus import --help for valid sources."}, pretty)
            sys.exit(1)

        session.close()

        def run_importer(src):
            """Run a single importer by name. Returns stats dict."""
            logger.setLevel(logging.INFO)
            if src == "oraec":
                from importers.oraec.importer import main as importer_main
                importer_main()
            elif src == "aes":
                from importers.aes.importer import main as importer_main
                importer_main()
            elif src == "tla-hf":
                from importers.tla_hf.importer import main as importer_main
                importer_main()
            elif src == "nederhof":
                from importers.nederhof.importer import main as importer_main
                importer_main()
            elif src == "ramses":
                from importers.ramses.importer import main as importer_main
                importer_main()
            elif src == "papyri-info":
                from importers.papyri_info.connector import run_full_import
                run_full_import()
            elif src == "aed-dict":
                from importers.aed_dict.importer import main as importer_main
                importer_main()
            elif src == "aed-tei":
                from importers.aed_tei.importer import main as importer_main
                importer_main()
            elif src == "coptic-scriptorium":
                from importers.coptic_scriptorium.importer import main as importer_main
                importer_main()
            elif src == "met-api":
                from importers.met_api.importer import main as importer_main
                importer_main()
            elif src == "nederhof-philologeg":
                from importers.nederhof_philologeg.importer import main as importer_main
                importer_main()
            elif src == "trismegistos":
                from importers.trismegistos.importer import main as importer_main
                importer_main()
            else:
                return {"source": src, "status": "error", "error": f"Unknown source: {src}"}
            return {"source": src, "status": "complete"}

        if source == "all":
            results = []
            for src in IMPORT_ORDER:
                try:
                    r = run_importer(src)
                    results.append(r)
                # Importers sys.exit(1) on missing data; keep going with the rest.
                except SystemExit as e:
                    if e.code in (0, None):
                        results.append({"source": src, "status": "complete"})
                    else:
                        results.append({"source": src, "status": "error",
                                        "error": f"exited with status {e.code}, see log"})
                except Exception as e:
                    results.append({"source": src, "status": "error", "error": str(e)})
            _output({"importers": results}, pretty)
            if any(r["status"] == "error" for r in results):
                sys.exit(1)
        else:
            try:
                result = run_importer(source)
                _output(result, pretty)
            except Exception as e:
                _output({"source": source, "status": "error", "error": str(e)}, pretty)
                sys.exit(1)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)


# ---------------------------------------------------------------------------
# aegyptus ingest
# ---------------------------------------------------------------------------

@cli.command(
    help="""Ad-hoc file ingestion. Ingest a text, JSON, or CSV file into the corpus.

Creates canonical records with aeg_adhoc_{content_hash} IDs. All records are
tagged source='ad_hoc', confidence='unreviewed'. Idempotent -- re-ingesting
the same content skips without error.

Supported formats (auto-detected from extension):
  .txt   Plain text -- each line becomes a sentence
  .json  JSON object or array of objects
  .csv   CSV with headers -- each row becomes a separate record

OUTPUT FORMAT (JSON object):
  {
    "canonical_id": "aeg_adhoc_abc123...",
    "status": "created",        // or "exists"
    "sentences": 5,
    "ids_linked": 2
  }

EXIT CODES:
  0  Success (created or already exists)
  1  Error (file not found, invalid format, DB error)

EXAMPLES:
  aegyptus ingest ./text.txt --name "Stela of Ahmose" --script-type hieroglyphic
  aegyptus ingest ./data.json --source "field_notes" --ids "tla:ABC123,tm:12345"
  aegyptus ingest ./batch.csv --script-type hieratic
"""
)
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Conventional name for the text.")
@click.option("--script-type", default=None,
              type=click.Choice(["hieroglyphic", "hieratic", "demotic", "coptic", "greek", "multiple"],
                                case_sensitive=False),
              help="Script type classification.")
@click.option("--source", default=None, help="Source attribution (default: ad_hoc).")
@click.option("--ids", default=None, help="External IDs to link, format: tla:XXXXX,tm:YYYYY.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def ingest(file_path, name, script_type, source, ids, pretty):
    from ingest.cli import (
        detect_format, ingest_text_file, ingest_json_file,
        ingest_csv_file, parse_ids,
    )
    try:
        id_pairs = parse_ids(ids) if ids else []
        fmt = detect_format(file_path)

        if fmt == "json":
            result = ingest_json_file(file_path, name, script_type, source, id_pairs)
        elif fmt == "csv":
            result = ingest_csv_file(file_path, name, script_type, source, id_pairs)
        else:
            result = ingest_text_file(file_path, name, script_type, source, id_pairs)

        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)


# ---------------------------------------------------------------------------
# aegyptus translate
# ---------------------------------------------------------------------------

@cli.command(
    help="""Run draft translations via local LLM or Anthropic API.

Default behavior: finds sentences with transliteration but no English
translation, translates them, and saves the result as a representation
layer with confidence='low' and source='ml_draft'.

Backend selection (--backend):
  auto       Try local llama-server first, fall back to Anthropic, then dry-run (default)
  local      Force local llama-server (LOCAL_LLM_URL env var or --local-url)
  anthropic  Force Anthropic Claude API (ANTHROPIC_API_KEY env var required)

VALID --backend VALUES:
  auto, local, anthropic

OUTPUT FORMAT (JSON array of results):
  [
    {
      "sentence_id": 42,
      "canonical_id": "aeg_oraec_320",
      "translation_en": "...",
      "confidence_llm": "MEDIUM",
      "backend": "local",
      "model": "...",
      "saved": true
    },
    ...
  ]

EXIT CODES:
  0  Translations produced
  1  Error
  2  No untranslated sentences found

EXAMPLES:
  aegyptus translate --limit 5
  aegyptus translate --text aeg_oraec_320 --no-save --pretty
  aegyptus translate --sentence-id 42 --backend anthropic
  aegyptus translate --limit 10 --source oraec --backend local
  aegyptus translate --limit 1 --no-save
"""
)
@click.option("--limit", default=100, type=int, show_default=True, help="Max sentences to translate.")
@click.option("--text", "text_id", default=None, help="Translate all sentences in this text (canonical_id).")
@click.option("--sentence-id", default=None, type=int, help="Translate a single sentence by ID.")
@click.option("--source", default=None, help="Filter untranslated sentences by source (e.g., oraec, aes).")
@click.option("--backend", default="auto",
              type=click.Choice(["local", "anthropic", "auto"], case_sensitive=False),
              show_default=True, help="Translation backend.")
@click.option("--local-url", default=None, help="Override LOCAL_LLM_URL for local backend.")
@click.option("--no-save", is_flag=True, help="Translate but do not save to DB.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def translate(limit, text_id, sentence_id, source, backend, local_url, no_save, pretty):
    from core.models import Sentence, SessionLocal
    from processing.draft_translation.service import DraftTranslationService

    session = SessionLocal()
    try:
        # Determine backend kwargs
        svc_kwargs = {}
        if backend == "local":
            svc_kwargs["local_llm_url"] = local_url or os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:8012")
        elif backend == "anthropic":
            svc_kwargs["api_key"] = os.environ.get("ANTHROPIC_API_KEY")
            if not svc_kwargs["api_key"]:
                _output({"error": "ANTHROPIC_API_KEY environment variable required for anthropic backend."}, pretty)
                sys.exit(1)
        else:  # auto
            if local_url:
                svc_kwargs["local_llm_url"] = local_url

        if no_save:
            svc_kwargs["dry_run"] = True

        svc = DraftTranslationService(**svc_kwargs)

        # Determine which sentences to translate
        sentences = []
        if sentence_id is not None:
            sent = session.query(Sentence).filter(Sentence.id == sentence_id).first()
            if not sent:
                _output({"error": f"Sentence {sentence_id} not found."}, pretty)
                sys.exit(2)
            sentences = [sent]
        elif text_id:
            sentences = (session.query(Sentence)
                         .filter(Sentence.canonical_id == text_id,
                                 Sentence.transliteration.isnot(None))
                         .order_by(Sentence.sequence_num)
                         .limit(limit)
                         .all())
            if not sentences:
                _output({"error": f"No transliterable sentences found for text '{text_id}'."}, pretty)
                sys.exit(2)
        else:
            sentences = svc.find_untranslated_sentences(session, source=source, limit=limit)
            if not sentences:
                _output({"info": "No untranslated sentences found matching criteria."}, pretty)
                return

        results = []
        for sent in sentences:
            tr = svc.translate_sentence(sent, session=session)
            saved = False
            if not no_save and tr.success and not tr.dry_run:
                layer_id = svc.save_result(tr, session)
                session.commit()
                saved = layer_id is not None

            results.append({
                "sentence_id": tr.sentence_id,
                "canonical_id": tr.canonical_id,
                "translation_en": tr.translation_en,
                "confidence_llm": tr.confidence_llm,
                "notes": tr.notes,
                "backend": tr.backend,
                "model": tr.model,
                "dry_run": tr.dry_run,
                "dry_run_prompt": tr.dry_run_prompt if tr.dry_run else None,
                "error": tr.error,
                "saved": saved,
            })

        _output(results, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus alias
# ---------------------------------------------------------------------------

@cli.command(
    help="""Manage text aliases (alternative names, shelfmarks, abbreviations).

ACTIONS (first positional argument):
  add       Add a new alias for a text
  search    Search aliases by text (fuzzy substring match)
  list      List all aliases for a canonical_id
  seed      Re-seed aliases from corpus data (ORAEC names, shelfmarks, etc.)

VALID --type VALUES (for 'add' action):
  conventional_name, shelfmark, abbreviation, foreign_title

OUTPUT FORMAT:
  add:    {"status": "created", "alias_id": N}
  search: [{"canonical_id": "...", "alias_text": "...", ...}, ...]
  list:   [{"alias_text": "...", "alias_type": "...", ...}, ...]
  seed:   {"oraec_names": N, "oraec_shelfmarks": N, ...}

EXIT CODES:
  0  Success
  1  Error (missing flags, DB error)
  2  No results (search/list returned empty)

EXAMPLES:
  aegyptus alias add "Tale of Sinuhe" --canonical-id aeg_oraec_320 --type conventional_name
  aegyptus alias search sinuhe --pretty
  aegyptus alias list --canonical-id aeg_oraec_320
  aegyptus alias seed
"""
)
@click.argument("action", type=click.Choice(["add", "search", "list", "seed"], case_sensitive=False))
@click.argument("value", default=None, required=False)
@click.option("--canonical-id", default=None, help="Canonical ID of the text (required for 'add' and 'list').")
@click.option("--type", "alias_type", default=None,
              type=click.Choice(["conventional_name", "shelfmark", "abbreviation", "foreign_title"],
                                case_sensitive=False),
              help="Alias type (required for 'add').")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def alias(action, value, canonical_id, alias_type, pretty):
    from core.models import Alias
    session = _get_session()
    try:
        if action == "add":
            if not value:
                _output({"error": "Provide the alias text as the second argument."}, pretty)
                sys.exit(1)
            if not canonical_id:
                _output({"error": "--canonical-id is required for 'add'."}, pretty)
                sys.exit(1)
            if not alias_type:
                _output({"error": "--type is required for 'add'."}, pretty)
                sys.exit(1)

            from core.concordance.alias_seeder import add_alias
            from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark

            normalizer = normalize_shelfmark if alias_type == "shelfmark" else normalize_conventional_name
            is_new = add_alias(session, canonical_id, value, alias_type,
                               normalizer_fn=normalizer, confidence="manual")
            session.commit()

            if is_new:
                # Fetch the created alias to get its ID
                created = (session.query(Alias)
                           .filter(Alias.canonical_id == canonical_id,
                                   Alias.alias_text == value)
                           .first())
                _output({"status": "created", "alias_id": created.id if created else None}, pretty)
            else:
                _output({"status": "exists"}, pretty)

        elif action == "search":
            if not value:
                _output({"error": "Provide search text as the second argument."}, pretty)
                sys.exit(1)

            rows = (session.query(Alias)
                    .filter(Alias.alias_normalized.ilike(f"%{value.lower()}%"))
                    .limit(50)
                    .all())

            results = [_serialize_alias(r) for r in rows]
            _output(results, pretty)
            if not results:
                sys.exit(2)

        elif action == "list":
            if not canonical_id:
                _output({"error": "--canonical-id is required for 'list'."}, pretty)
                sys.exit(1)

            rows = (session.query(Alias)
                    .filter(Alias.canonical_id == canonical_id)
                    .all())

            results = [_serialize_alias(r) for r in rows]
            _output(results, pretty)
            if not results:
                sys.exit(2)

        elif action == "seed":
            from core.concordance.alias_seeder import (
                seed_from_oraec_names, seed_from_oraec_shelfmarks,
                seed_from_nederhof, seed_from_tla_hf,
            )
            result = {
                "oraec_names": seed_from_oraec_names(session),
                "oraec_shelfmarks": seed_from_oraec_shelfmarks(session),
                "nederhof": seed_from_nederhof(session),
                "tla_hf": seed_from_tla_hf(session),
            }
            _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus crawl
# ---------------------------------------------------------------------------

@cli.command(
    help="""Web crawler operations.

ACTIONS (first positional argument):
  seeds     Harvest URLs from seed sources (scrapes index pages, populates crawl_queue)
  run       Dispatch pending crawl tasks (foreground, processes batch_size URLs)
  status    Show crawl queue depth and breakdown by domain/status

OUTPUT FORMAT:
  seeds:  [{"source_id": "...", "urls_found": N, "urls_inserted": N, ...}, ...]
  run:    {"dispatched": N}
  status: {"total": N, "by_status": {...}, "by_domain": {...}}

EXIT CODES:
  0  Success
  1  Error

EXAMPLES:
  aegyptus crawl seeds
  aegyptus crawl status --pretty
  aegyptus crawl run
"""
)
@click.argument("action", type=click.Choice(["seeds", "run", "status"], case_sensitive=False))
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def crawl(action, pretty):
    from sqlalchemy import text as sa_text

    try:
        if action == "seeds":
            from crawler.seeds.harvester import harvest_all
            stats = harvest_all()
            _output(stats, pretty)

        elif action == "run":
            from crawler.workers.tasks import dispatch_pending
            result = dispatch_pending(batch_size=50)
            _output(result, pretty)

        elif action == "status":
            session = _get_session()
            try:
                total = session.execute(sa_text("SELECT count(*) FROM crawl_queue")).scalar() or 0

                by_status = {}
                rows = session.execute(sa_text(
                    "SELECT status, count(*) FROM crawl_queue GROUP BY status ORDER BY count(*) DESC"
                )).fetchall()
                by_status = {r[0]: r[1] for r in rows}

                by_domain = {}
                rows = session.execute(sa_text(
                    "SELECT domain, count(*) FROM crawl_queue GROUP BY domain ORDER BY count(*) DESC LIMIT 20"
                )).fetchall()
                by_domain = {r[0]: r[1] for r in rows}

                by_type = {}
                rows = session.execute(sa_text(
                    "SELECT content_type_hint, count(*) FROM crawl_queue "
                    "GROUP BY content_type_hint ORDER BY count(*) DESC"
                )).fetchall()
                by_type = {r[0]: r[1] for r in rows}

                result = {
                    "total": total,
                    "by_status": by_status,
                    "by_domain": by_domain,
                    "by_content_type": by_type,
                }
                _output(result, pretty)
            finally:
                session.close()

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)


# ---------------------------------------------------------------------------
# aegyptus gaps
# ---------------------------------------------------------------------------

@cli.command(
    help="""Gap analysis -- identify missing data in the corpus.

Without --refresh, lists existing gap records from the DB. With --refresh,
runs a full gap analysis first, writing new gap records, then lists results.

VALID --type VALUES:
  not_imported       Texts known externally but not in corpus (reserved)
  no_transcription   Texts with layers but no transliteration
  no_translation     Texts with transliteration but no translation
  orphan             Texts with zero concordance links
  all                All gap types (default)

VALID --priority VALUES:
  P0, P1, P2, P3

OUTPUT FORMAT (JSON array):
  [
    {
      "id": 1,
      "canonical_id": "aeg_oraec_123",
      "gap_type": "no_translation",
      "priority": "P3",
      "recommended_action": "Queue for draft translation",
      "status": "open"
    },
    ...
  ]

EXIT CODES:
  0  Gaps found
  1  Error
  2  No gaps matching criteria

EXAMPLES:
  aegyptus gaps --limit 5
  aegyptus gaps --type no_translation --priority P3 --limit 20
  aegyptus gaps --refresh --pretty
  aegyptus gaps --type orphan --limit 10
"""
)
@click.option("--type", "gap_type", default=None,
              type=click.Choice(["not_imported", "no_transcription", "no_translation", "orphan", "all"],
                                case_sensitive=False),
              help="Filter by gap type.")
@click.option("--priority", default=None,
              type=click.Choice(["P0", "P1", "P2", "P3"], case_sensitive=False),
              help="Filter by priority level.")
@click.option("--limit", default=50, type=int, show_default=True, help="Max results to return.")
@click.option("--refresh", is_flag=True, help="Re-run gap analysis before listing results.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def gaps(gap_type, priority, limit, refresh, pretty):
    from core.models import Gap
    session = _get_session()
    try:
        if refresh:
            from gap_tracker.analyzer import GapAnalyzer
            analyzer = GapAnalyzer(session=session)
            report = analyzer.run_full_analysis(write_gaps=True)
            # Report is supplementary info on stderr
            print(json.dumps(report.to_dict(), default=str), file=sys.stderr)

        query = session.query(Gap)

        if gap_type and gap_type != "all":
            # Map CLI names to DB names
            type_map = {
                "no_transcription": "no_transliteration",
                "no_translation": "no_translation",
                "orphan": "orphan",
                "not_imported": "not_imported",
            }
            db_type = type_map.get(gap_type, gap_type)
            query = query.filter(Gap.gap_type == db_type)

        if priority:
            query = query.filter(Gap.priority == priority)

        query = query.filter(Gap.status == "open")
        query = query.order_by(Gap.priority, Gap.id)
        rows = query.limit(limit).all()

        results = [_serialize_gap(r) for r in rows]
        _output(results, pretty)

        if not results:
            sys.exit(2)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus export
# ---------------------------------------------------------------------------

@cli.command(
    name="export",
    help="""Export corpus to compressed JSONL files.

Creates one gzipped JSONL file per table, plus a manifest.json with
row counts, export date, and corpus version.

Output files:
  texts.jsonl.gz
  sentences.jsonl.gz
  concordance.jsonl.gz
  aliases.jsonl.gz
  representation_layers.jsonl.gz
  manifest.json

VALID --tables VALUES (comma-separated):
  texts, sentences, concordance, aliases, representation_layers

OUTPUT FORMAT (JSON object):
  {
    "output_dir": "/path/to/export",
    "tables": {"texts": 13026, "sentences": 98432, ...},
    "total_rows": N,
    "manifest": "/path/to/export/manifest.json"
  }

EXIT CODES:
  0  Export successful
  1  Error

EXAMPLES:
  aegyptus export
  aegyptus export --output-dir /tmp/corpus-export
  aegyptus export --tables texts,sentences --no-compress
  aegyptus export --pretty
"""
)
@click.option("--output-dir", default=None, help="Output directory (default: ./export).")
@click.option("--tables", default="texts,sentences,concordance,aliases,representation_layers",
              show_default=True, help="Comma-separated list of tables to export.")
@click.option("--compress/--no-compress", default=True, show_default=True,
              help="Gzip compress output files.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def export_cmd(output_dir, tables, compress, pretty):
    import gzip
    from pathlib import Path
    from sqlalchemy import text as sa_text

    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent / "export")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    table_list = [t.strip() for t in tables.split(",")]

    TABLES = {
        "texts": {
            "query": "SELECT canonical_id, conventional_name, script_type, date_earliest, date_latest, period_label, findspot, current_location, text_type, completeness, shelfmarks, metadata, created_at, updated_at FROM texts ORDER BY canonical_id",
            "columns": ["canonical_id", "conventional_name", "script_type", "date_earliest", "date_latest", "period_label", "findspot", "current_location", "text_type", "completeness", "shelfmarks", "metadata", "created_at", "updated_at"],
        },
        "sentences": {
            "query": "SELECT id, canonical_id, sequence_num, transliteration, translation, tokens, source, source_id, source_detail, confidence, created_at FROM sentences ORDER BY canonical_id, id",
            "columns": ["id", "canonical_id", "sequence_num", "transliteration", "translation", "tokens", "source", "source_id", "source_detail", "confidence", "created_at"],
        },
        "concordance": {
            "query": "SELECT id, canonical_id, external_system, external_id, relationship FROM concordance ORDER BY canonical_id, id",
            "columns": ["id", "canonical_id", "external_system", "external_id", "relationship"],
        },
        "aliases": {
            "query": "SELECT id, canonical_id, alias_text, alias_normalized, alias_type, confidence FROM aliases ORDER BY canonical_id, id",
            "columns": ["id", "canonical_id", "alias_text", "alias_normalized", "alias_type", "confidence"],
        },
        "representation_layers": {
            "query": "SELECT id, canonical_id, layer_type, content, language, source, source_detail, confidence, created_at FROM representation_layers ORDER BY canonical_id, id",
            "columns": ["id", "canonical_id", "layer_type", "content", "language", "source", "source_detail", "confidence", "created_at"],
        },
    }

    BATCH_SIZE = 5000
    session = _get_session()
    try:
        counts = {}
        for tname in table_list:
            if tname not in TABLES:
                _output({"error": f"Unknown table: {tname}. Valid: {list(TABLES.keys())}"}, pretty)
                sys.exit(1)

            spec = TABLES[tname]
            ext = ".jsonl.gz" if compress else ".jsonl"
            outpath = out / f"{tname}{ext}"

            opener = gzip.open if compress else open
            open_kwargs = {"mode": "wt", "encoding": "utf-8"} if compress else {"mode": "w", "encoding": "utf-8"}

            count = 0
            with opener(outpath, **open_kwargs) as f:
                offset = 0
                while True:
                    rows = session.execute(
                        sa_text(f"{spec['query']} LIMIT :limit OFFSET :offset"),
                        {"limit": BATCH_SIZE, "offset": offset},
                    ).fetchall()

                    if not rows:
                        break

                    for row in rows:
                        record = {}
                        for i, col in enumerate(spec["columns"]):
                            val = row[i]
                            if isinstance(val, datetime):
                                val = val.isoformat()
                            record[col] = val
                        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                        count += 1

                    offset += BATCH_SIZE
                    if len(rows) < BATCH_SIZE:
                        break

            counts[tname] = count

        # Get version tag
        try:
            ver_row = session.execute(sa_text(
                "SELECT version_tag FROM corpus_versions ORDER BY id DESC LIMIT 1"
            )).fetchone()
            version = ver_row[0] if ver_row else "unknown"
        except Exception:
            version = "unknown"

        manifest = {
            "corpus": "aegyptus",
            "version": version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "jsonl.gz" if compress else "jsonl",
            "tables": counts,
            "total_rows": sum(counts.values()),
            "schema_version": "0.1.0",
        }
        manifest_path = out / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        result = {
            "output_dir": str(out),
            "tables": counts,
            "total_rows": sum(counts.values()),
            "manifest": str(manifest_path),
        }
        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus serve
# ---------------------------------------------------------------------------

@cli.command(
    help="""Start the API server and/or dashboard.

By default, starts both the FastAPI query API and the dashboard. Use
--api-only or --dashboard-only to start just one.

The API serves at http://0.0.0.0:<api-port> with interactive docs at /docs.
The dashboard serves at http://0.0.0.0:<dashboard-port>.

EXIT CODES:
  0  Server stopped gracefully
  1  Error starting server

EXAMPLES:
  aegyptus serve
  aegyptus serve --api-port 9000
  aegyptus serve --api-only
  aegyptus serve --dashboard-only --dashboard-port 8888
"""
)
@click.option("--api-port", default=8000, type=int, show_default=True, help="Port for the API server.")
@click.option("--dashboard-port", default=8080, type=int, show_default=True, help="Port for the dashboard.")
@click.option("--api-only", is_flag=True, help="Start only the API server.")
@click.option("--dashboard-only", is_flag=True, help="Start only the dashboard.")
def serve(api_port, dashboard_port, api_only, dashboard_only):
    import uvicorn

    if api_only and dashboard_only:
        _output({"error": "Cannot use both --api-only and --dashboard-only."})
        sys.exit(1)

    if dashboard_only:
        print(f"Starting dashboard on http://0.0.0.0:{dashboard_port}", file=sys.stderr)
        uvicorn.run("dashboard.app:app", host="0.0.0.0", port=dashboard_port, log_level="info")
        return

    if api_only:
        print(f"Starting API on http://0.0.0.0:{api_port}", file=sys.stderr)
        uvicorn.run("api.app:app", host="0.0.0.0", port=api_port, log_level="info")
        return

    # Both: run API in main thread, dashboard info printed
    # For simplicity, start API (dashboard can be started separately)
    import threading

    def run_dashboard():
        uvicorn.run("dashboard.app:app", host="0.0.0.0", port=dashboard_port, log_level="warning")

    print(f"Starting API on http://0.0.0.0:{api_port}", file=sys.stderr)
    print(f"Starting dashboard on http://0.0.0.0:{dashboard_port}", file=sys.stderr)

    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()

    uvicorn.run("api.app:app", host="0.0.0.0", port=api_port, log_level="info")


# ---------------------------------------------------------------------------
# aegyptus tag
# ---------------------------------------------------------------------------

@cli.command(
    help="""Create a corpus version snapshot.

Inserts a row into corpus_versions with current table counts. The version
tag must be unique. Useful for marking milestones (e.g., after a major
import or data quality pass).

OUTPUT FORMAT (JSON object):
  {
    "version_tag": "v0.3.0",
    "text_count": 13026,
    "sentence_count": 98432,
    "layer_count": 45000,
    "concordance_count": 80000,
    "alias_count": 12000,
    "description": "Phase 5 complete"
  }

EXIT CODES:
  0  Version tagged successfully
  1  Error (duplicate tag, DB error)

EXAMPLES:
  aegyptus tag v0.3.0
  aegyptus tag v0.2.1-hotfix --description "Fixed papyri duplicates"
  aegyptus tag v0.3.0 --pretty
"""
)
@click.argument("version_tag")
@click.option("--description", default=None, help="Human-readable description of this version.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def tag(version_tag, description, pretty):
    from sqlalchemy import text as sa_text
    from core.models import CorpusVersion
    session = _get_session()
    try:
        # Check for duplicate
        existing = session.execute(
            sa_text("SELECT id FROM corpus_versions WHERE version_tag = :tag"),
            {"tag": version_tag},
        ).fetchone()

        if existing:
            _output({"error": f"Version '{version_tag}' already exists (id={existing[0]})."}, pretty)
            sys.exit(1)

        # Get current counts
        tables = {
            "text_count": "texts",
            "sentence_count": "sentences",
            "layer_count": "representation_layers",
            "concordance_count": "concordance",
            "alias_count": "aliases",
        }
        counts = {}
        for key, table in tables.items():
            counts[key] = session.execute(sa_text(f"SELECT count(*) FROM {table}")).scalar() or 0

        # Source breakdown for metadata
        rows = session.execute(sa_text(
            "SELECT split_part(canonical_id, '_', 2) AS src, count(*) "
            "FROM texts GROUP BY src ORDER BY count(*) DESC"
        )).fetchall()
        sources = {r[0]: r[1] for r in rows}

        try:
            gap_count = session.execute(sa_text("SELECT count(*) FROM gaps")).scalar() or 0
        except Exception:
            gap_count = 0

        version = CorpusVersion(
            version_tag=version_tag,
            description=description,
            text_count=counts["text_count"],
            sentence_count=counts["sentence_count"],
            layer_count=counts["layer_count"],
            concordance_count=counts["concordance_count"],
            alias_count=counts["alias_count"],
            extra_metadata={
                "tagged_at": datetime.now(timezone.utc).isoformat(),
                "texts_by_source": sources,
                "gap_count": gap_count,
            },
        )
        session.add(version)
        session.commit()

        result = {
            "version_tag": version_tag,
            "text_count": counts["text_count"],
            "sentence_count": counts["sentence_count"],
            "layer_count": counts["layer_count"],
            "concordance_count": counts["concordance_count"],
            "alias_count": counts["alias_count"],
            "description": description,
            "texts_by_source": sources,
        }
        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# aegyptus backup
# ---------------------------------------------------------------------------

@cli.command(
    help="""Run pg_dump to create a database backup.

Creates a compressed SQL dump of the Aegyptus database. Optionally uploads
to MinIO object storage. Cleans up backups older than 30 days.

Database connection uses environment variables or defaults:
  PGHOST=localhost  PGPORT=5434  PGUSER=aegyptus  PGPASSWORD=dev  PGDATABASE=aegyptus

OUTPUT FORMAT (JSON object):
  {
    "backup_file": "/path/to/aegyptus_2025-01-15_143022.sql.gz",
    "size": "42M",
    "uploaded": false
  }

EXIT CODES:
  0  Backup successful
  1  Error (pg_dump failure, disk error)

EXAMPLES:
  aegyptus backup
  aegyptus backup --output-dir /mnt/backups
  aegyptus backup --upload --pretty
"""
)
@click.option("--output-dir", default=None, help="Output directory (default: ./backups).")
@click.option("--upload", is_flag=True, help="Upload to MinIO after dump.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def backup(output_dir, upload, pretty):
    import subprocess
    from pathlib import Path

    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent / "backups")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"aegyptus_{date_str}.sql.gz"
    filepath = out / filename

    env = os.environ.copy()
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5434")
    env.setdefault("PGUSER", "aegyptus")
    env.setdefault("PGPASSWORD", "dev")
    env.setdefault("PGDATABASE", "aegyptus")

    try:
        proc = subprocess.run(
            f"pg_dump --format=plain --no-owner --no-acl | gzip > {filepath}",
            shell=True, env=env, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            _output({"error": f"pg_dump failed: {proc.stderr}"}, pretty)
            sys.exit(1)

        size = filepath.stat().st_size
        size_human = f"{size / 1024 / 1024:.1f}M" if size > 1024 * 1024 else f"{size / 1024:.1f}K"

        uploaded = False
        if upload:
            try:
                from minio import Minio
                minio_client = Minio(
                    os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
                    access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
                    secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
                    secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
                )
                bucket = "aegyptus-backups"
                if not minio_client.bucket_exists(bucket):
                    minio_client.make_bucket(bucket)
                minio_client.fput_object(bucket, filename, str(filepath))
                uploaded = True
            except Exception as e:
                print(f"MinIO upload failed: {e}", file=sys.stderr)

        # Clean up old backups
        import glob
        old_backups = sorted(glob.glob(str(out / "aegyptus_*.sql.gz")))
        cleaned = 0
        if len(old_backups) > 30:
            for old in old_backups[:-30]:
                Path(old).unlink()
                cleaned += 1

        result = {
            "backup_file": str(filepath),
            "size": size_human,
            "uploaded": uploaded,
        }
        if cleaned:
            result["old_backups_cleaned"] = cleaned

        _output(result, pretty)

    except Exception as e:
        _output({"error": str(e)}, pretty)
        sys.exit(1)


# ---------------------------------------------------------------------------
# aegyptus rosetta (multilingual decoding engine)
# ---------------------------------------------------------------------------
from rosetta.cli import rosetta as rosetta_group
cli.add_command(rosetta_group)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
