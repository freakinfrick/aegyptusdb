"""Per-domain rate limiter and politeness enforcement.

Features:
- Per-domain rate limiting from YAML config
- robots.txt parser and cache
- Exponential backoff on 429/503
- 403 = blocked, logged, never retried
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import yaml

logger = logging.getLogger(__name__)

DOMAIN_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "seed_urls" / "domain_config.yaml"


class DomainState:
    """Track per-domain state: last request time, backoff level, robots.txt."""

    def __init__(self, domain: str, rps: float):
        self.domain = domain
        self.min_interval = 1.0 / rps if rps > 0 else 1.0
        self.last_request_time = 0.0
        self.backoff_level = 0
        self.robots: Optional[RobotFileParser] = None
        self.robots_fetched = False
        self.blocked = False
        self.lock = threading.Lock()


class RateLimiter:
    """Per-domain rate limiter with robots.txt support.

    Usage:
        limiter = RateLimiter()

        # Before fetching:
        if not limiter.is_allowed(url):
            # skip this URL
            pass

        limiter.wait(url)  # blocks until domain slot is available
        # ... fetch the URL ...
        limiter.record_response(url, status_code)
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config = self._load_config(config_path or DOMAIN_CONFIG_FILE)
        self._domains: dict[str, DomainState] = {}
        self._global_lock = threading.Lock()

    @staticmethod
    def _load_config(path: Path) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    def _get_domain_state(self, domain: str) -> DomainState:
        """Get or create state for a domain."""
        if domain not in self._domains:
            with self._global_lock:
                if domain not in self._domains:
                    domain_cfg = self._config.get("domains", {}).get(domain, {})
                    rps = domain_cfg.get("requests_per_second",
                                         self._config["defaults"]["requests_per_second"])
                    self._domains[domain] = DomainState(domain, rps)
        return self._domains[domain]

    def _fetch_robots_txt(self, domain: str, scheme: str = "https") -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt for a domain. Cached per domain."""
        robots_url = f"{scheme}://{domain}/robots.txt"
        user_agent = self._config["defaults"]["user_agent"]

        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(robots_url, headers={"User-Agent": user_agent})
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    logger.debug("Parsed robots.txt for %s", domain)
                    return rp
                else:
                    # No robots.txt or error = allow all
                    logger.debug("No robots.txt for %s (status %d), allowing all", domain, resp.status_code)
                    return None
        except httpx.HTTPError as e:
            logger.debug("Failed to fetch robots.txt for %s: %s", domain, e)
            return None

    def is_allowed(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt and not blocked.

        Returns False if:
        - Domain is marked as blocked (got 403)
        - robots.txt disallows the URL
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        state = self._get_domain_state(domain)

        if state.blocked:
            return False

        # Fetch robots.txt once per domain
        if not state.robots_fetched:
            with state.lock:
                if not state.robots_fetched:
                    state.robots = self._fetch_robots_txt(domain, parsed.scheme)
                    state.robots_fetched = True

        if state.robots is not None:
            user_agent = self._config["defaults"]["user_agent"].split("/")[0]
            if not state.robots.can_fetch(user_agent, url):
                logger.info("robots.txt disallows: %s", url)
                return False

        return True

    def get_crawl_delay(self, domain: str) -> Optional[float]:
        """Get Crawl-delay from robots.txt if specified."""
        state = self._get_domain_state(domain)
        if state.robots is not None:
            user_agent = self._config["defaults"]["user_agent"].split("/")[0]
            delay = state.robots.crawl_delay(user_agent)
            if delay is not None:
                return float(delay)
        return None

    def wait(self, url: str):
        """Block until it's safe to make a request to this domain.

        Respects per-domain rate limit and any active backoff.
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        state = self._get_domain_state(domain)

        with state.lock:
            now = time.monotonic()
            elapsed = now - state.last_request_time

            # Use crawl-delay from robots.txt if larger than config
            crawl_delay = self.get_crawl_delay(domain)
            interval = state.min_interval
            if crawl_delay is not None and crawl_delay > interval:
                interval = crawl_delay

            # Apply backoff
            if state.backoff_level > 0:
                backoff_base = self._config["defaults"]["backoff_base"]
                backoff_max = self._config["defaults"]["backoff_max"]
                backoff_time = min(backoff_base ** state.backoff_level, backoff_max)
                interval = max(interval, backoff_time)

            wait_time = interval - elapsed
            if wait_time > 0:
                logger.debug("Rate limit: waiting %.2fs for %s", wait_time, domain)
                time.sleep(wait_time)

            state.last_request_time = time.monotonic()

    def record_response(self, url: str, status_code: int):
        """Record a response status code to update backoff state.

        - 429/503: increase backoff
        - 403: mark domain as blocked
        - 2xx: reset backoff
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        state = self._get_domain_state(domain)

        with state.lock:
            if status_code == 403:
                state.blocked = True
                logger.warning("Domain %s returned 403 - marked as blocked, will not retry", domain)
            elif status_code in (429, 503):
                state.backoff_level = min(state.backoff_level + 1, 8)
                logger.warning("Domain %s returned %d - backoff level now %d",
                               domain, status_code, state.backoff_level)
            elif 200 <= status_code < 400:
                if state.backoff_level > 0:
                    state.backoff_level = max(0, state.backoff_level - 1)

    def mark_blocked(self, url: str, reason: str = "403"):
        """Explicitly mark a domain as blocked."""
        domain = urlparse(url).netloc
        state = self._get_domain_state(domain)
        state.blocked = True
        logger.warning("Domain %s marked as blocked: %s", domain, reason)

    def get_stats(self) -> dict:
        """Return current rate limiter state for all tracked domains."""
        stats = {}
        for domain, state in self._domains.items():
            stats[domain] = {
                "min_interval": state.min_interval,
                "backoff_level": state.backoff_level,
                "blocked": state.blocked,
                "robots_fetched": state.robots_fetched,
                "has_robots": state.robots is not None,
            }
        return stats
