"""CLI for gap tracker service.

Usage:
    python -m gap_tracker [--priority P0] [--type orphan] [--limit 100]
    python -m gap_tracker --full                    # Full analysis, write to DB
    python -m gap_tracker --type no_translation     # Single gap type
    python -m gap_tracker --tm-check                # TM local coverage check
    python -m gap_tracker --report                  # Print report without writing
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gap tracker: identify missing texts and enrichment needs")
    parser.add_argument("--full", action="store_true", help="Run full gap analysis")
    parser.add_argument("--type", type=str, choices=[
        "no_translation", "no_transliteration", "orphan", "no_layers", "sentences_no_layers"
    ], help="Run analysis for a specific gap type")
    parser.add_argument("--priority", type=str, choices=["P0", "P1", "P2", "P3"],
                        help="Filter output by priority level")
    parser.add_argument("--limit", type=int, default=500, help="Max gaps per type (default: 500)")
    parser.add_argument("--no-write", action="store_true", help="Don't write gaps to database")
    parser.add_argument("--tm-check", action="store_true", help="Check Trismegistos local coverage")
    parser.add_argument("--report", action="store_true", help="Print full report as JSON")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    from .analyzer import GapAnalyzer
    from .trismegistos import TrismegistosChecker

    if args.tm_check:
        with TrismegistosChecker() as checker:
            coverage = checker.check_local_coverage()
            if args.json:
                print(json.dumps(coverage, indent=2))
            else:
                print("=== Trismegistos Local Coverage ===")
                for k, v in coverage.items():
                    print(f"  {k}: {v}")
        return

    with GapAnalyzer() as analyzer:
        if args.type:
            summary = analyzer.run_single_analysis(
                gap_type=args.type,
                write_gaps=not args.no_write,
                limit=args.limit,
            )
            if args.json:
                print(json.dumps({
                    "type": summary.gap_type,
                    "count": summary.count,
                    "priority": summary.priority,
                    "samples": summary.sample_ids[:10],
                }, indent=2))
            else:
                print(f"Gap type: {summary.gap_type}")
                print(f"Count: {summary.count}")
                print(f"Priority: {summary.priority}")
                if summary.sample_ids:
                    print(f"Samples: {', '.join(summary.sample_ids[:5])}")
        else:
            # Full analysis (default)
            report = analyzer.run_full_analysis(
                write_gaps=not args.no_write,
                limit_per_type=args.limit,
            )

            if args.priority:
                # Filter summaries by priority
                report.summaries = [s for s in report.summaries if s.priority == args.priority]

            if args.json or args.report:
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print("=" * 60)
                print("GAP ANALYSIS REPORT")
                print("=" * 60)
                print(f"Timestamp: {report.timestamp}")
                print(f"Corpus: {report.total_texts} texts, {report.total_sentences} sentences, "
                      f"{report.total_layers} layers, {report.total_concordance} concordance links")
                print()

                for s in report.summaries:
                    print(f"  [{s.priority}] {s.gap_type}: {s.count} texts")
                    if s.sample_ids:
                        print(f"       Samples: {', '.join(s.sample_ids[:5])}")

                if report.coverage:
                    print()
                    print("--- Coverage ---")
                    for section, data in report.coverage.items():
                        if isinstance(data, dict):
                            print(f"  {section}:")
                            for k, v in data.items():
                                print(f"    {k}: {v}")

                if report.gaps_written:
                    print()
                    print(f"Wrote {report.gaps_written} gap records to database")

                print("=" * 60)


if __name__ == "__main__":
    main()
