"""Ad-hoc ingestion CLI for Aegyptus.

Usage:
  python -m ingest <file> [--name "..."] [--script-type ...] [--source "..."] [--ids tla:XXXXX,tm:YYYYY]

Accepts: plain text, JSON, CSV
Creates canonical record with aeg_adhoc_{content_hash}
Tags everything: source='ad_hoc', confidence='unreviewed'
Optionally links via --ids flag to concordance

Examples:
  python -m ingest my_translation.txt --name "Tale of the Shipwrecked Sailor" --script-type hieroglyphic
  python -m ingest texts.json --source "university_collection"
  python -m ingest records.csv --ids tla:ABC123,tm:12345
"""

from ingest.cli import main

if __name__ == "__main__":
    main()
