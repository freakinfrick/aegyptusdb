"""Seed URL harvester: scrapes index pages, extracts outbound URLs,
classifies by content type, and populates the crawl_queue table."""

import logging
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from sqlalchemy import text as sa_text

from core.models import CrawlQueue, SessionLocal

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seed_urls"
SOURCES_FILE = DATA_DIR / "sources.yaml"
DOMAIN_CONFIG_FILE = DATA_DIR / "domain_config.yaml"

# Content type classification by file extension
EXT_TO_TYPE = {
    ".pdf": "pdf",
    ".htm": "html",
    ".html": "html",
    ".shtml": "html",
    ".asp": "html",
    ".php": "html",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".tif": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".txt": "text",
    ".xml": "xml",
    ".json": "json",
}

# URL patterns to skip (not useful text content)
SKIP_PATTERNS = [
    re.compile(r"\.(css|js|ico|svg|woff|woff2|ttf|eot|mp3|mp4|wav|avi|zip|gz|tar|rar)$", re.I),
    re.compile(r"^mailto:", re.I),
    re.compile(r"^javascript:", re.I),
    re.compile(r"^#"),
    re.compile(r"^data:", re.I),
]


def load_sources() -> list[dict]:
    """Load seed source definitions from YAML."""
    with open(SOURCES_FILE) as f:
        data = yaml.safe_load(f)
    return data["sources"]


def load_domain_config() -> dict:
    """Load per-domain configuration."""
    with open(DOMAIN_CONFIG_FILE) as f:
        return yaml.safe_load(f)


def classify_url(url: str) -> str:
    """Classify URL by likely content type based on extension/path."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    for ext, ctype in EXT_TO_TYPE.items():
        if path.endswith(ext):
            return ctype

    # Default to html for web pages
    return "html"


def should_skip_url(url: str) -> bool:
    """Check if a URL should be skipped."""
    for pattern in SKIP_PATTERNS:
        if pattern.search(url):
            return True
    return False


def extract_links(html: str, base_url: str) -> list[dict]:
    """Extract all outbound links from an HTML page.

    Returns list of dicts with keys: url, content_type_hint, anchor_text.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href:
            continue

        absolute_url = urljoin(base_url, href)

        # Strip fragments
        parsed = urlparse(absolute_url)
        clean_url = parsed._replace(fragment="").geturl()

        if clean_url in seen:
            continue
        seen.add(clean_url)

        if should_skip_url(clean_url):
            continue

        # Only keep http(s) URLs
        if not clean_url.startswith(("http://", "https://")):
            continue

        anchor_text = a_tag.get_text(strip=True)[:200]
        content_type = classify_url(clean_url)

        links.append({
            "url": clean_url,
            "content_type_hint": content_type,
            "anchor_text": anchor_text,
        })

    return links


def fetch_page(url: str, timeout: float = 30.0) -> Optional[str]:
    """Fetch a page with respectful headers. Returns HTML text or None."""
    config = load_domain_config()
    user_agent = config["defaults"]["user_agent"]

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 403:
                logger.warning("403 Forbidden for %s - logging as blocked", url)
                return None
            if resp.status_code == 429:
                logger.warning("429 Rate limited for %s - backing off", url)
                return None
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None


def link_rot_check(urls: list[str], timeout: float = 15.0) -> list[dict]:
    """Check a list of URLs for link rot using HEAD requests.

    Returns list of dicts: {url, status, status_code, redirect_url, error}.
    """
    config = load_domain_config()
    user_agent = config["defaults"]["user_agent"]
    headers = {"User-Agent": user_agent}
    results = []

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        for url in urls:
            result = {"url": url, "status": "unknown", "status_code": None, "redirect_url": None, "error": None}
            try:
                resp = client.head(url, headers=headers)
                result["status_code"] = resp.status_code
                if resp.status_code < 400:
                    result["status"] = "alive"
                    if str(resp.url) != url:
                        result["redirect_url"] = str(resp.url)
                elif resp.status_code == 403:
                    result["status"] = "blocked"
                elif resp.status_code == 404:
                    result["status"] = "dead"
                else:
                    result["status"] = "error"
            except httpx.HTTPError as e:
                result["status"] = "dead"
                result["error"] = str(e)

            results.append(result)
            # Polite delay between HEAD requests
            time.sleep(0.5)

    return results


def harvest_source(source: dict, session) -> dict:
    """Harvest URLs from a single seed source.

    Returns stats dict: {source_id, urls_found, urls_inserted, errors}.
    """
    source_id = source["id"]
    stats = {"source_id": source_id, "urls_found": 0, "urls_inserted": 0, "errors": []}

    logger.info("Harvesting source: %s", source_id)

    for entry_url in source["entry_urls"]:
        logger.info("  Fetching index page: %s", entry_url)
        html = fetch_page(entry_url)
        if html is None:
            stats["errors"].append(f"Failed to fetch {entry_url}")
            continue

        links = extract_links(html, entry_url)
        stats["urls_found"] += len(links)

        for link in links:
            domain = urlparse(link["url"]).netloc
            try:
                existing = session.query(CrawlQueue).filter(CrawlQueue.url == link["url"]).first()
                if existing:
                    continue

                record = CrawlQueue(
                    url=link["url"],
                    domain=domain,
                    content_type_hint=link["content_type_hint"],
                    status="pending",
                    extra_metadata={
                        "seed_source": source_id,
                        "anchor_text": link.get("anchor_text", ""),
                        "entry_url": entry_url,
                    },
                )
                session.add(record)
                stats["urls_inserted"] += 1
            except Exception as e:
                stats["errors"].append(f"Error inserting {link['url']}: {e}")

        # Commit per source page
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            stats["errors"].append(f"Commit failed for {entry_url}: {e}")

    return stats


def run_eef_link_rot_check() -> dict:
    """Run link-rot check specifically on EEF pages.

    Returns a report dict with alive/dead/blocked counts and details.
    """
    sources = load_sources()
    eef_sources = [s for s in sources if s.get("link_rot_check")]

    report = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [],
    }

    for source in eef_sources:
        source_report = {
            "source_id": source["id"],
            "name": source["name"],
            "entry_urls": source["entry_urls"],
            "links": [],
            "summary": {"total": 0, "alive": 0, "dead": 0, "blocked": 0, "error": 0},
        }

        for entry_url in source["entry_urls"]:
            html = fetch_page(entry_url)
            if html is None:
                source_report["links"].append({
                    "url": entry_url,
                    "status": "entry_page_failed",
                })
                continue

            links = extract_links(html, entry_url)
            urls = [l["url"] for l in links]

            logger.info("Checking %d links from %s", len(urls), entry_url)
            results = link_rot_check(urls)

            for r in results:
                source_report["links"].append(r)
                source_report["summary"]["total"] += 1
                status = r["status"]
                if status in source_report["summary"]:
                    source_report["summary"][status] += 1

        report["sources"].append(source_report)

    return report


def harvest_all():
    """Harvest URLs from all seed sources and populate crawl_queue."""
    sources = load_sources()
    session = SessionLocal()
    all_stats = []

    try:
        for source in sources:
            # Skip API-based sources (Internet Archive uses different flow)
            if source.get("use_api"):
                logger.info("Skipping API-based source: %s (handled by dedicated worker)", source["id"])
                # Still add the entry URL as a placeholder
                for entry_url in source["entry_urls"]:
                    domain = urlparse(entry_url).netloc
                    existing = session.query(CrawlQueue).filter(CrawlQueue.url == entry_url).first()
                    if not existing:
                        record = CrawlQueue(
                            url=entry_url,
                            domain=domain,
                            content_type_hint="api",
                            status="pending",
                            extra_metadata={
                                "seed_source": source["id"],
                                "use_api": True,
                                "notes": source.get("notes", ""),
                            },
                        )
                        session.add(record)
                session.commit()
                all_stats.append({"source_id": source["id"], "urls_found": 0, "urls_inserted": 1, "errors": [], "api_source": True})
                continue

            stats = harvest_source(source, session)
            all_stats.append(stats)
            logger.info("  Source %s: found=%d, inserted=%d, errors=%d",
                        stats["source_id"], stats["urls_found"], stats["urls_inserted"], len(stats["errors"]))

    finally:
        session.close()

    return all_stats


def print_stats(all_stats: list[dict]):
    """Print harvest stats summary."""
    total_found = 0
    total_inserted = 0
    total_errors = 0

    print("\n=== Seed URL Harvest Report ===\n")
    for stats in all_stats:
        api_tag = " [API]" if stats.get("api_source") else ""
        print(f"  {stats['source_id']}{api_tag}:")
        print(f"    URLs found:    {stats['urls_found']}")
        print(f"    URLs inserted: {stats['urls_inserted']}")
        if stats["errors"]:
            print(f"    Errors:        {len(stats['errors'])}")
            for err in stats["errors"][:3]:
                print(f"      - {err}")
        total_found += stats["urls_found"]
        total_inserted += stats["urls_inserted"]
        total_errors += len(stats["errors"])

    print(f"\n  TOTAL: found={total_found}, inserted={total_inserted}, errors={total_errors}")

    # Print DB summary
    session = SessionLocal()
    try:
        total = session.query(CrawlQueue).count()
        by_domain = session.execute(
            sa_text("SELECT domain, count(*) FROM crawl_queue GROUP BY domain ORDER BY count(*) DESC LIMIT 20")
        ).fetchall()
        by_type = session.execute(
            sa_text("SELECT content_type_hint, count(*) FROM crawl_queue GROUP BY content_type_hint ORDER BY count(*) DESC")
        ).fetchall()

        print(f"\n  crawl_queue total: {total}")
        print("\n  By domain:")
        for domain, count in by_domain:
            print(f"    {domain}: {count}")
        print("\n  By content type:")
        for ctype, count in by_type:
            print(f"    {ctype}: {count}")
    finally:
        session.close()
