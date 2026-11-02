"""Entry point: python -m crawler.seeds [harvest|linkrot]"""

import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "harvest"

    if cmd == "harvest":
        from crawler.seeds.harvester import harvest_all, print_stats
        stats = harvest_all()
        print_stats(stats)

    elif cmd == "linkrot":
        from crawler.seeds.harvester import run_eef_link_rot_check
        report = run_eef_link_rot_check()

        # Print summary
        print("\n=== EEF Link-Rot Report ===\n")
        for src in report["sources"]:
            print(f"Source: {src['name']}")
            s = src["summary"]
            print(f"  Total: {s['total']}  Alive: {s['alive']}  Dead: {s['dead']}  Blocked: {s['blocked']}  Error: {s['error']}")
            dead_links = [l for l in src["links"] if l["status"] in ("dead", "error")]
            if dead_links:
                print("  Dead/Error links:")
                for l in dead_links[:20]:
                    print(f"    {l['status']:>8s} | {l.get('status_code', '???')} | {l['url']}")
                    if l.get("error"):
                        print(f"             {l['error'][:100]}")
            print()

        # Save full report
        report_path = "data/seed_urls/linkrot_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Full report saved to {report_path}")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m crawler.seeds [harvest|linkrot]")
        sys.exit(1)


if __name__ == "__main__":
    main()
