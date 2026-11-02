"""Celery tasks for the Aegyptus crawler worker framework.

Each task is stateless:
1. Pull URL + content type hint from crawl_queue
2. Check robots.txt / rate limiter
3. Fetch the page (httpx)
4. Classify the response content type
5. Store raw content in MinIO (content-addressed key)
6. Update crawl_queue record (status, fetched_at, object_store_key)
"""

import hashlib
import io
import logging
import os
from datetime import datetime, timezone

import httpx
from minio import Minio
from minio.error import S3Error

from core.models import CrawlQueue, SessionLocal
from crawler.rate_limiter.limiter import RateLimiter
from crawler.workers.celery_app import app

logger = logging.getLogger(__name__)

# MinIO config
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "aegyptus-raw")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

# Shared rate limiter instance (per worker process)
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_minio_client() -> Minio:
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )
    # Ensure bucket exists
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
    return client


def content_address_key(url: str, content: bytes) -> str:
    """Generate a content-addressed storage key.

    Format: {url_hash_prefix}/{content_sha256}
    The url_hash_prefix provides directory-like grouping.
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
    content_hash = hashlib.sha256(content).hexdigest()
    return f"{url_hash}/{content_hash}"


def detect_content_type(response: httpx.Response) -> str:
    """Detect content type from response headers."""
    ct = response.headers.get("content-type", "").lower()
    if "pdf" in ct:
        return "pdf"
    if "html" in ct:
        return "html"
    if "image" in ct:
        return "image"
    if "xml" in ct:
        return "xml"
    if "json" in ct:
        return "json"
    if "text" in ct:
        return "text"
    return "binary"


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_url(self, crawl_queue_id: int):
    """Fetch a URL from the crawl queue and store in MinIO."""
    session = SessionLocal()
    try:
        record = session.query(CrawlQueue).get(crawl_queue_id)
        if record is None:
            logger.error("CrawlQueue record %d not found", crawl_queue_id)
            return {"status": "error", "reason": "record_not_found"}

        url = record.url

        # Skip already fetched
        if record.status in ("fetched", "blocked"):
            logger.info("Skipping %s (status=%s)", url, record.status)
            return {"status": "skipped", "reason": record.status}

        # Mark as in-progress
        record.status = "fetching"
        session.commit()

        # Check rate limiter / robots.txt
        limiter = get_rate_limiter()
        if not limiter.is_allowed(url):
            record.status = "blocked"
            record.extra_metadata = {**(record.extra_metadata or {}), "block_reason": "robots_txt_or_domain_blocked"}
            session.commit()
            logger.info("Blocked by robots.txt or domain policy: %s", url)
            return {"status": "blocked", "url": url}

        # Wait for rate limit slot
        limiter.wait(url)

        # Fetch
        user_agent = "Aegyptus-Corpus-Builder/0.1 (+https://github.com/aegyptus; scholarly research)"
        headers = {"User-Agent": user_agent}

        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                resp = client.get(url, headers=headers)

            limiter.record_response(url, resp.status_code)

            if resp.status_code == 403:
                record.status = "blocked"
                record.extra_metadata = {**(record.extra_metadata or {}), "status_code": 403}
                session.commit()
                logger.warning("403 blocked: %s", url)
                return {"status": "blocked", "url": url, "status_code": 403}

            if resp.status_code in (429, 503):
                record.status = "pending"  # will retry
                session.commit()
                try:
                    raise self.retry(exc=Exception(f"Rate limited: {resp.status_code}"))
                except TypeError:
                    # Running outside Celery context
                    return {"status": "retry", "url": url, "status_code": resp.status_code}

            if resp.status_code >= 400:
                # Client errors (404, etc.) are not retryable
                record.status = "error"
                record.extra_metadata = {**(record.extra_metadata or {}), "status_code": resp.status_code}
                session.commit()
                logger.warning("HTTP %d for %s - marked as error", resp.status_code, url)
                return {"status": "error", "url": url, "status_code": resp.status_code}

        except httpx.HTTPError as e:
            record.status = "error"
            record.extra_metadata = {**(record.extra_metadata or {}), "error": str(e)}
            session.commit()
            logger.error("HTTP error fetching %s: %s", url, e)
            try:
                raise self.retry(exc=e)
            except TypeError:
                return {"status": "error", "url": url, "reason": str(e)}

        # Classify content type
        actual_type = detect_content_type(resp)
        content = resp.content

        # Store in MinIO
        storage_key = content_address_key(url, content)
        try:
            minio_client = get_minio_client()

            # Add file extension based on content type
            ext_map = {"pdf": ".pdf", "html": ".html", "image": ".bin", "xml": ".xml", "json": ".json", "text": ".txt"}
            ext = ext_map.get(actual_type, ".bin")
            full_key = f"{storage_key}{ext}"

            content_stream = io.BytesIO(content)
            minio_client.put_object(
                MINIO_BUCKET,
                full_key,
                content_stream,
                length=len(content),
                content_type=resp.headers.get("content-type", "application/octet-stream"),
            )
            logger.info("Stored %s -> minio://%s/%s (%d bytes)", url, MINIO_BUCKET, full_key, len(content))

        except S3Error as e:
            record.status = "error"
            record.extra_metadata = {**(record.extra_metadata or {}), "minio_error": str(e)}
            session.commit()
            logger.error("MinIO error for %s: %s", url, e)
            return {"status": "error", "url": url, "reason": "minio_error"}

        # Update crawl_queue record
        record.status = "fetched"
        record.fetched_at = datetime.now(timezone.utc)
        record.object_store_key = full_key
        record.content_type_hint = actual_type
        record.extra_metadata = {
            **(record.extra_metadata or {}),
            "content_length": len(content),
            "response_content_type": resp.headers.get("content-type", ""),
            "final_url": str(resp.url),
        }
        session.commit()

        return {
            "status": "fetched",
            "url": url,
            "storage_key": full_key,
            "content_type": actual_type,
            "size": len(content),
        }

    except Exception as e:
        session.rollback()
        logger.error("Unexpected error processing %d: %s", crawl_queue_id, e)
        raise
    finally:
        session.close()


@app.task
def dispatch_pending(batch_size: int = 50):
    """Dispatch pending crawl_queue items as individual fetch tasks.

    Pulls up to batch_size pending URLs and enqueues them as fetch_url tasks.
    """
    session = SessionLocal()
    try:
        pending = (
            session.query(CrawlQueue)
            .filter(CrawlQueue.status == "pending")
            .limit(batch_size)
            .all()
        )

        dispatched = 0
        for record in pending:
            fetch_url.delay(record.id)
            dispatched += 1

        logger.info("Dispatched %d fetch tasks", dispatched)
        return {"dispatched": dispatched}
    finally:
        session.close()
