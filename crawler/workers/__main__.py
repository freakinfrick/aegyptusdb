"""Entry point: python -m crawler.workers [dispatch|fetch-test|status]

Direct-mode commands for testing the crawler without Celery.
For production, use: celery -A crawler.workers.celery_app worker --loglevel=info
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_dispatch(batch_size: int = 50):
    """Dispatch pending URLs (via Celery task queue)."""
    from crawler.workers.tasks import dispatch_pending
    result = dispatch_pending.delay(batch_size)
    print(f"Dispatched batch task: {result.id}")
    print("Monitor with: celery -A crawler.workers.celery_app inspect active")


def cmd_fetch_test(url: str = None):
    """Fetch a single test URL synchronously (no Celery needed)."""
    from core.models import CrawlQueue, SessionLocal
    from crawler.workers.tasks import fetch_url

    session = SessionLocal()
    try:
        if url:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # Insert or find test URL
            record = session.query(CrawlQueue).filter(CrawlQueue.url == url).first()
            if not record:
                record = CrawlQueue(
                    url=url,
                    domain=domain,
                    content_type_hint="html",
                    status="pending",
                    extra_metadata={"seed_source": "manual_test"},
                )
                session.add(record)
                session.commit()
            record_id = record.id
        else:
            # Pick first pending
            record = session.query(CrawlQueue).filter(CrawlQueue.status == "pending").first()
            if not record:
                print("No pending URLs in crawl_queue")
                return
            record_id = record.id
            url = record.url

        print(f"Fetching: {url} (id={record_id})")
        # Call synchronously (not .delay())
        result = fetch_url(record_id)
        print(f"Result: {result}")
    finally:
        session.close()


def cmd_status():
    """Show crawl_queue status summary."""
    from sqlalchemy import text as sa_text

    from core.models import SessionLocal

    session = SessionLocal()
    try:
        rows = session.execute(
            sa_text("SELECT status, count(*) FROM crawl_queue GROUP BY status ORDER BY count(*) DESC")
        ).fetchall()
        print("\n=== Crawl Queue Status ===\n")
        for status, count in rows:
            print(f"  {status:>12s}: {count}")

        total = sum(r[1] for r in rows)
        print(f"  {'TOTAL':>12s}: {total}")

        print("\n=== By Domain (top 15) ===\n")
        domain_rows = session.execute(
            sa_text("""
                SELECT domain, count(*),
                       count(*) FILTER (WHERE status = 'fetched') as fetched,
                       count(*) FILTER (WHERE status = 'pending') as pending,
                       count(*) FILTER (WHERE status = 'blocked') as blocked,
                       count(*) FILTER (WHERE status = 'error') as errored
                FROM crawl_queue GROUP BY domain ORDER BY count(*) DESC LIMIT 15
            """)
        ).fetchall()
        print(f"  {'Domain':<40s} {'Total':>6s} {'Fetch':>6s} {'Pend':>6s} {'Block':>6s} {'Err':>6s}")
        print(f"  {'-'*40} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
        for row in domain_rows:
            print(f"  {row[0]:<40s} {row[1]:>6d} {row[2]:>6d} {row[3]:>6d} {row[4]:>6d} {row[5]:>6d}")
    finally:
        session.close()


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    if cmd == "dispatch":
        batch = int(args[1]) if len(args) > 1 else 50
        cmd_dispatch(batch)
    elif cmd == "fetch-test":
        url = args[1] if len(args) > 1 else None
        cmd_fetch_test(url)
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m crawler.workers [dispatch|fetch-test [URL]|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
