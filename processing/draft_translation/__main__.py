"""CLI for draft translation service.

Usage:
    python -m processing.draft_translation [--dry-run] [--source aes] [--limit 10] [--sentence-id 12345]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft translation of Egyptian texts")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without calling API")
    parser.add_argument("--backend", choices=["local", "anthropic", "auto"], default="auto",
                        help="Translation backend (default: auto-detect)")
    parser.add_argument("--local-url", type=str, help="Local llama-server URL (default: auto-detect localhost:8012)")
    parser.add_argument("--source", type=str, help="Filter sentences by source (aes, oraec, tla_hf, ramses)")
    parser.add_argument("--limit", type=int, default=10, help="Max sentences to translate (default: 10)")
    parser.add_argument("--sentence-id", type=int, help="Translate a specific sentence by ID")
    parser.add_argument("--min-tokens", type=int, default=3, help="Min token count per sentence (default: 3, skips tiny fragments)")
    parser.add_argument("--no-save", action="store_true", help="Do NOT save results to DB (default: saves)")
    parser.add_argument("--commit-every", type=int, default=50, help="Commit to DB every N sentences (default: 50)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--batch-mode", type=int, default=0, metavar="N",
                        help="Pack N sentences per LLM call (0=off, 20 recommended for fragments)")
    args = parser.parse_args()

    from core.models import Sentence, SessionLocal
    from .service import DraftTranslationService

    session = SessionLocal()
    kwargs = {"dry_run": args.dry_run}
    if args.local_url:
        kwargs["local_llm_url"] = args.local_url
    if args.backend == "local":
        kwargs.setdefault("local_llm_url", "http://127.0.0.1:8012")
    elif args.backend == "anthropic":
        # Force anthropic even if local is available
        kwargs["local_llm_url"] = None
    service = DraftTranslationService(**kwargs)

    try:
        if args.sentence_id:
            sentence = session.get(Sentence, args.sentence_id)
            if not sentence:
                logger.error("Sentence %d not found", args.sentence_id)
                sys.exit(1)
            sentences = [sentence]
        else:
            sentences = service.find_untranslated_sentences(
                session, source=args.source, limit=args.limit,
                min_tokens=args.min_tokens,
            )
            if not sentences:
                logger.info("No untranslated sentences found matching criteria")
                sys.exit(0)

        logger.info("Processing %d sentences (backend=%s%s)", len(sentences), service.backend,
                     f", batch={args.batch_mode}" if args.batch_mode else "")

        saved = 0
        pending = 0
        successful = 0
        failed = 0

        if args.batch_mode > 0 and service.backend == "local":
            # Batched mode: N sentences per LLM call
            batch_results = service.translate_batch_local(
                sentences, session=session, batch_size=args.batch_mode,
            )
            for result in batch_results:
                successful += 1
                if not args.no_save:
                    layer_id = service.save_result(result, session)
                    if layer_id:
                        saved += 1
                        pending += 1
                if pending >= args.commit_every:
                    session.commit()
                    logger.info("Checkpoint: committed %d (%d total saved)", pending, saved)
                    pending = 0
            failed = len(sentences) - successful
        else:
            # Single-sentence mode (original path)
            for i, sentence in enumerate(sentences):
                result = service.translate_sentence(sentence, session=session)
                if (i + 1) % 10 == 0:
                    logger.info("Translated %d/%d sentences (%d saved)", i + 1, len(sentences), saved)

                if args.json:
                    print(json.dumps({
                        "sentence_id": result.sentence_id,
                        "canonical_id": result.canonical_id,
                        "translation": result.translation_en,
                        "notes": result.notes,
                        "confidence_llm": result.confidence_llm,
                        "dry_run": result.dry_run,
                        "error": result.error,
                        "model": result.model,
                        "metadata": result.layer_metadata if result.success else {},
                    }, indent=2))
                elif result.dry_run:
                    print(result.dry_run_prompt)
                    print()
                elif result.success:
                    successful += 1
                elif not result.success:
                    failed += 1

                if not args.no_save and result.success and not result.dry_run:
                    layer_id = service.save_result(result, session)
                    if layer_id:
                        saved += 1
                        pending += 1

                if pending >= args.commit_every:
                    session.commit()
                    logger.info("Checkpoint: committed %d layers (%d total saved)", pending, saved)
                    pending = 0

        if not args.no_save and pending > 0:
            session.commit()
            logger.info("Final commit: %d layers (%d total saved)", pending, saved)

        # Summary
        logger.info("Done: %d successful, %d failed, %d saved, %d total", successful, failed, saved, len(sentences))

    finally:
        session.close()


if __name__ == "__main__":
    main()
