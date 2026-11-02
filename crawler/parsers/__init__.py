"""HTML parser registry for crawled content extraction.

Import this package to auto-register all site-specific parsers.

Usage:
    from crawler.parsers import get_parser
    parser = get_parser("www.attalus.org")
    results = parser.parse(html_content, url)
"""

# Import all parser modules to trigger @register_parser decorators
from crawler.parsers import attalus  # noqa: F401
from crawler.parsers import eef  # noqa: F401
from crawler.parsers import generic  # noqa: F401
from crawler.parsers import pyramid_texts  # noqa: F401
from crawler.parsers import sacred_texts  # noqa: F401
from crawler.parsers.base import BaseParser, ParseResult, detect_language
from crawler.parsers.registry import get_parser, list_registered

__all__ = [
    "BaseParser",
    "ParseResult",
    "detect_language",
    "get_parser",
    "list_registered",
]
