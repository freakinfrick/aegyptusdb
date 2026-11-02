"""Parser registry: maps domains to parser classes.

Usage:
    from crawler.parsers.registry import get_parser
    parser = get_parser("www.attalus.org")
    results = parser.parse(html_content, url)
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from crawler.parsers.base import BaseParser

logger = logging.getLogger(__name__)

# Domain -> parser class mapping, populated by register_parser()
_registry: dict[str, type[BaseParser]] = {}


def register_parser(parser_class: type[BaseParser]) -> type[BaseParser]:
    """Register a parser class for its declared domains."""
    for domain in parser_class.DOMAINS:
        normalized = domain.lower().strip()
        if normalized in _registry:
            logger.warning(
                "Overwriting parser for domain %s: %s -> %s",
                normalized,
                _registry[normalized].__name__,
                parser_class.__name__,
            )
        _registry[normalized] = parser_class
        logger.debug("Registered parser %s for domain %s", parser_class.__name__, normalized)
    return parser_class


def get_parser(url_or_domain: str) -> BaseParser:
    """Get the appropriate parser for a URL or domain.

    Falls back to GenericParser if no site-specific parser is registered.
    """
    # Extract domain from URL if needed
    if "/" in url_or_domain or ":" in url_or_domain:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc.lower()
    else:
        domain = url_or_domain.lower().strip()

    # Try exact match
    if domain in _registry:
        return _registry[domain]()

    # Try without www. prefix
    bare = domain.removeprefix("www.")
    if bare in _registry:
        return _registry[bare]()

    # Try with www. prefix
    with_www = f"www.{domain}"
    if with_www in _registry:
        return _registry[with_www]()

    # Fallback to generic parser
    from crawler.parsers.generic import GenericParser
    return GenericParser()


def list_registered() -> dict[str, str]:
    """Return mapping of domain -> parser class name."""
    return {domain: cls.__name__ for domain, cls in sorted(_registry.items())}
