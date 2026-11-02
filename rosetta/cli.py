"""Rosetta CLI — multilingual decoding engine commands."""

import json
import logging
import sys

import click

logger = logging.getLogger(__name__)


def _get_session():
    """Lazy import and create a DB session."""
    from core.models import SessionLocal
    return SessionLocal()


def _output(data, pretty=False):
    """Write JSON to stdout."""
    if pretty:
        click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    else:
        click.echo(json.dumps(data, default=str, ensure_ascii=False))


@click.group()
def rosetta():
    """Rosetta multilingual decoding engine."""
    pass


@rosetta.command("build-lexicon")
@click.option("--phase", default=None, help="Run specific phase (1a-1g). Default: all.")
@click.option("--dry-run", is_flag=True, help="Show what would be done without writing.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def build_lexicon(phase, dry_run, pretty):
    """Build or enrich the Thoth Lexicon from corpus evidence.

    Phases: 1a=seed, 1b=german_glosses, 1c=english_contexts,
    1d=bridge, 1e=coptic, 1f=stats, 1g=confidence_tiers
    """
    session = _get_session()
    try:
        from rosetta.lexicon.builder import LexiconBuilder
        builder = LexiconBuilder(session)

        if dry_run:
            # Show what would run
            phases = ["1a: seed_from_lemmata", "1b: enrich_german_glosses",
                      "1c: enrich_english_contexts", "1d: bridge_german_to_english",
                      "1e: link_coptic_cognates", "1f: compute_stats",
                      "1g: set_confidence_tiers"]
            if phase:
                phases = [p for p in phases if p.startswith(phase)]
            _output({"dry_run": True, "phases": phases}, pretty)
            return

        phase_map = {
            "1a": builder.seed_from_lemmata,
            "1b": builder.enrich_german_glosses,
            "1c": builder.enrich_english_contexts,
            "1d": builder.bridge_german_to_english,
            "1e": builder.link_coptic_cognates,
            "1f": builder.compute_stats,
            "1g": builder.set_confidence_tiers,
        }

        if phase:
            if phase not in phase_map:
                _output({"error": f"Unknown phase: {phase}. Valid: {list(phase_map.keys())}"}, pretty)
                sys.exit(1)
            result = {phase: phase_map[phase]()}
        else:
            result = builder.build_all()

        _output(result, pretty)
    except Exception as e:
        logger.exception("build-lexicon failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


@rosetta.command("build-index")
@click.option("--pretty", is_flag=True)
def build_index(pretty):
    """Build the inverted lemma index for parallel sentence retrieval."""
    session = _get_session()
    try:
        from rosetta.witness.index import InvertedIndexBuilder
        builder = InvertedIndexBuilder(session)
        count = builder.build_index()
        stats = builder.index_stats()
        stats["entries_created"] = count
        _output(stats, pretty)
    except Exception as e:
        logger.exception("build-index failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


@rosetta.command("mechanical")
@click.option("--source", default=None, help="Filter by source (aed_tei, oraec, aes). Default: all.")
@click.option("--limit", default=0, type=int, help="Max sentences. 0 = no limit.")
@click.option("--min-tokens", default=1, type=int, show_default=True)
@click.option("--dry-run", is_flag=True)
@click.option("--pretty", is_flag=True)
def mechanical(source, limit, min_tokens, dry_run, pretty):
    """Mechanical (CPU-only, no LLM) translation via DE→EN bridge dictionary.

    Translates sentences with word-level German glosses using a corpus-derived
    dictionary. Covers 99.7% of AED-TEI tokens. No GPU or API needed.
    """
    session = _get_session()
    try:
        from rosetta.engine.mechanical import MechanicalTranslator
        mt = MechanicalTranslator(session)
        bridge_size = mt.build_bridge()
        click.echo(f"Bridge built: {bridge_size:,} DE→EN entries", err=True)

        result = mt.translate_batch(
            source=source, limit=limit, min_tokens=min_tokens, dry_run=dry_run
        )
        _output(result, pretty)
    except Exception as e:
        logger.exception("mechanical translation failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


@rosetta.command("polish")
@click.option("--limit", default=0, type=int, help="Max sentences. 0 = all.")
@click.option("--min-tokens", default=6, type=int, show_default=True)
@click.option("--dry-run", is_flag=True)
@click.option("--pretty", is_flag=True)
def polish(limit, min_tokens, dry_run, pretty):
    """Gemini fluency polish for mechanical translations (>5 tokens).

    Sends full dossier (mechanical EN + German + glosses) to Gemini 3.1 Flash Lite.
    Respects rate limits: 11 RPM, ~100K tokens/request (10% of context).
    """
    session = _get_session()
    try:
        from rosetta.engine.gemini_polish import GeminiPolisher
        gp = GeminiPolisher(session)
        result = gp.polish_all(
            limit=limit, min_tokens=min_tokens, dry_run=dry_run
        )
        _output(result, pretty)
        gp.close()
    except Exception as e:
        logger.exception("polish failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


@rosetta.command("translate")
@click.option("--tier", default="all", help="Translation tier: T1/T2/T3/T4/all")
@click.option("--limit", default=100, type=int, show_default=True)
@click.option("--backend", default="local", type=click.Choice(["local", "anthropic", "auto"]))
@click.option("--local-url", default=None, help="Local LLM URL override.")
@click.option("--dry-run", is_flag=True)
@click.option("--pretty", is_flag=True)
def translate(tier, limit, backend, local_url, dry_run, pretty):
    """Translate sentences using witness-grounded Rosetta engine.

    Tiers: T1 (German+glosses), T2 (German only), T3 (tokens only),
    T4 (transliteration only), T5 (fragments, skipped by default).
    """
    session = _get_session()
    try:
        from rosetta.engine.translator import RosettaTranslator
        from rosetta.engine.validator import RosettaValidator
        from rosetta.engine.batch import BatchOrchestrator

        translator = RosettaTranslator(backend=backend, local_url=local_url)
        validator = RosettaValidator()
        orchestrator = BatchOrchestrator(session, translator, validator)

        if dry_run:
            _output({"dry_run": True, "tier": tier, "limit": limit, "backend": backend}, pretty)
            return

        if tier == "all":
            result = orchestrator.run_all_tiers(
                limits={"T1": limit, "T2": limit, "T3": limit, "T4": limit // 4}
            )
        else:
            result = orchestrator.run_batch(tier=tier, limit=limit, backend=backend)

        _output(result, pretty)
        if isinstance(result, dict) and result.get("translated", 0) == 0:
            sys.exit(2)
    except Exception as e:
        logger.exception("translate failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()


@rosetta.command("status")
@click.option("--pretty", is_flag=True)
def status(pretty):
    """Show Rosetta system status: lexicon, index, and translation coverage."""
    session = _get_session()
    try:
        from sqlalchemy import text as sa_text

        # Lexicon stats
        lex = session.execute(sa_text("""
            SELECT
                COUNT(*) as total,
                COUNT(definition_en) as has_en,
                COUNT(definition_de) as has_de,
                COUNT(glosses_bridged_en) as has_bridged,
                COUNT(CASE WHEN confidence = 'gold' THEN 1 END) as gold,
                COUNT(CASE WHEN confidence = 'silver' THEN 1 END) as silver,
                COUNT(CASE WHEN confidence = 'bronze' THEN 1 END) as bronze
            FROM thoth_lexicon
        """)).fetchone()

        # Index stats
        idx = session.execute(sa_text("""
            SELECT COUNT(*) as entries,
                   COUNT(DISTINCT lemma_id) as unique_lemmas,
                   COUNT(DISTINCT sentence_id) as unique_sentences
            FROM rosetta_lemma_index
        """)).fetchone()

        # Translation coverage
        cov = session.execute(sa_text("""
            SELECT
                COUNT(*) as total_sentences,
                COUNT(CASE WHEN translation ? 'en' THEN 1 END) as has_en,
                COUNT(CASE WHEN translation ? 'de' THEN 1 END) as has_de,
                COUNT(CASE WHEN translation ? '_rosetta' THEN 1 END) as rosetta_translated
            FROM sentences
        """)).fetchone()

        result = {
            "lexicon": {
                "total": lex[0], "has_en": lex[1], "has_de": lex[2],
                "has_bridged": lex[3],
                "gold": lex[4], "silver": lex[5], "bronze": lex[6],
            },
            "index": {
                "entries": idx[0], "unique_lemmas": idx[1], "unique_sentences": idx[2],
            },
            "coverage": {
                "total_sentences": cov[0], "has_en": cov[1], "has_de": cov[2],
                "rosetta_translated": cov[3],
                "en_pct": round(cov[1] / max(cov[0], 1) * 100, 1),
            },
        }
        _output(result, pretty)
    except Exception as e:
        logger.exception("status failed")
        _output({"error": str(e)}, pretty)
        sys.exit(1)
    finally:
        session.close()
