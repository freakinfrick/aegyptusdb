"""CLI for manual alias management.

Usage:
  python -m ingest.alias add "Papyrus Berlin 3022" --canonical-id aeg_oraec_XXXX --type shelfmark
  python -m ingest.alias add "Tale of Sinuhe" --canonical-id aeg_oraec_100 --type conventional_name
  python -m ingest.alias search "Berlin 3022"
  python -m ingest.alias list --canonical-id aeg_oraec_100
"""

import argparse
import sys

from sqlalchemy import text as sql_text

from core.concordance.normalizer import normalize_conventional_name, normalize_shelfmark
from core.models import Alias, SessionLocal


def cmd_add(args):
    """Add a new alias."""
    session = SessionLocal()
    try:
        # Verify canonical_id exists
        exists = session.execute(
            sql_text("SELECT 1 FROM texts WHERE canonical_id = :cid"),
            {"cid": args.canonical_id},
        ).fetchone()

        if not exists:
            print(f"Error: canonical_id '{args.canonical_id}' not found in texts table")
            sys.exit(1)

        # Choose normalizer based on type
        if args.type == "shelfmark":
            normalized = normalize_shelfmark(args.alias_text)
        else:
            normalized = normalize_conventional_name(args.alias_text)

        # Check if already exists
        existing = session.execute(
            sql_text(
                "SELECT id FROM aliases WHERE alias_text = :text AND canonical_id = :cid"
            ),
            {"text": args.alias_text, "cid": args.canonical_id},
        ).fetchone()

        if existing:
            print(f"Alias already exists: '{args.alias_text}' -> {args.canonical_id}")
            return

        alias = Alias(
            canonical_id=args.canonical_id,
            alias_text=args.alias_text,
            alias_normalized=normalized,
            alias_type=args.type,
            confidence="manual",
        )
        session.add(alias)
        session.commit()

        print(f"Added alias: '{args.alias_text}' (normalized: '{normalized}') "
              f"-> {args.canonical_id} [type={args.type}]")

    finally:
        session.close()


def cmd_search(args):
    """Search for aliases matching a query."""
    session = SessionLocal()
    try:
        query = args.query

        # Try both normalizers
        norm_shelfmark = normalize_shelfmark(query)
        norm_name = normalize_conventional_name(query)

        # Search by normalized form
        rows = session.execute(
            sql_text(
                "SELECT a.alias_text, a.alias_normalized, a.alias_type, "
                "a.canonical_id, a.confidence, t.conventional_name "
                "FROM aliases a "
                "JOIN texts t ON a.canonical_id = t.canonical_id "
                "WHERE a.alias_normalized = :norm1 OR a.alias_normalized = :norm2 "
                "ORDER BY a.confidence, a.alias_type"
            ),
            {"norm1": norm_shelfmark, "norm2": norm_name},
        ).fetchall()

        if not rows:
            # Fuzzy: try LIKE match
            rows = session.execute(
                sql_text(
                    "SELECT a.alias_text, a.alias_normalized, a.alias_type, "
                    "a.canonical_id, a.confidence, t.conventional_name "
                    "FROM aliases a "
                    "JOIN texts t ON a.canonical_id = t.canonical_id "
                    "WHERE a.alias_normalized LIKE :pattern "
                    "ORDER BY a.confidence, a.alias_type "
                    "LIMIT 20"
                ),
                {"pattern": f"%{norm_name}%"},
            ).fetchall()

        if not rows:
            print(f"No matches for '{query}'")
            return

        print(f"Matches for '{query}' (normalized: '{norm_shelfmark}' / '{norm_name}'):")
        for alias_text, normalized, alias_type, canonical_id, confidence, conv_name in rows:
            print(f"  [{alias_type}] '{alias_text}' -> {canonical_id} "
                  f"({conv_name or 'unnamed'}) [{confidence}]")

    finally:
        session.close()


def cmd_list(args):
    """List aliases for a canonical_id."""
    session = SessionLocal()
    try:
        rows = session.execute(
            sql_text(
                "SELECT alias_text, alias_normalized, alias_type, confidence "
                "FROM aliases WHERE canonical_id = :cid ORDER BY alias_type"
            ),
            {"cid": args.canonical_id},
        ).fetchall()

        if not rows:
            print(f"No aliases for {args.canonical_id}")
            return

        print(f"Aliases for {args.canonical_id}:")
        for alias_text, normalized, alias_type, confidence in rows:
            print(f"  [{alias_type}] '{alias_text}' (norm: '{normalized}') [{confidence}]")

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Aegyptus alias table",
        prog="python -m ingest.alias",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Add a new alias")
    add_parser.add_argument("alias_text", help="The alias text to add")
    add_parser.add_argument("--canonical-id", required=True, help="Target canonical_id")
    add_parser.add_argument(
        "--type",
        choices=["conventional_name", "shelfmark", "abbreviation", "foreign_title"],
        default="conventional_name",
        help="Alias type (default: conventional_name)",
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search for aliases")
    search_parser.add_argument("query", help="Search query")

    # list command
    list_parser = subparsers.add_parser("list", help="List aliases for a canonical_id")
    list_parser.add_argument("--canonical-id", required=True, help="Target canonical_id")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
