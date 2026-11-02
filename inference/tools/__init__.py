"""Oracle tools (v5.0 §SPEC-ADDENDUM-v5).

The Oracle's tools are thin wrappers around the aegyptus CLI plus the live
topology engine. No parallel corpus implementation.

Exported registry TOOL_REGISTRY maps tool name → (callable, openai_schema).
"""
from typing import Any

from inference.tools.search_corpus import search_corpus, SEARCH_CORPUS_SCHEMA
from inference.tools.search_transliteration import (
    search_transliteration, SEARCH_TRANSLITERATION_SCHEMA,
)
from inference.tools.show_text import show_text, SHOW_TEXT_SCHEMA
from inference.tools.show_sentence import show_sentence, SHOW_SENTENCE_SCHEMA
from inference.tools.resolve_shelfmark import (
    resolve_shelfmark, RESOLVE_SHELFMARK_SCHEMA,
)
from inference.tools.find_chamber import find_chamber, FIND_CHAMBER_SCHEMA
from inference.tools.show_on_map import show_on_map, SHOW_ON_MAP_SCHEMA
from inference.tools.corpus_stats import corpus_stats, CORPUS_STATS_SCHEMA
from inference.tools.open_portal import open_portal, OPEN_PORTAL_SCHEMA
from inference.tools.speak import speak, SPEAK_SCHEMA
from inference.tools.read_article import read_article, READ_ARTICLE_SCHEMA
from inference.tools.tts import tts, TTS_SCHEMA


TOOL_REGISTRY: dict[str, tuple[Any, dict[str, Any]]] = {
    "search_corpus":          (search_corpus,          SEARCH_CORPUS_SCHEMA),
    "search_transliteration": (search_transliteration, SEARCH_TRANSLITERATION_SCHEMA),
    "show_text":              (show_text,              SHOW_TEXT_SCHEMA),
    "show_sentence":          (show_sentence,          SHOW_SENTENCE_SCHEMA),
    "resolve_shelfmark":      (resolve_shelfmark,      RESOLVE_SHELFMARK_SCHEMA),
    "find_chamber":           (find_chamber,           FIND_CHAMBER_SCHEMA),
    "show_on_map":            (show_on_map,            SHOW_ON_MAP_SCHEMA),
    "corpus_stats":           (corpus_stats,           CORPUS_STATS_SCHEMA),
    # v5.0 Day-2 carry-over: agentic actions on the world.
    "open_portal":            (open_portal,            OPEN_PORTAL_SCHEMA),
    "speak":                  (speak,                  SPEAK_SCHEMA),
    "read_article":           (read_article,           READ_ARTICLE_SCHEMA),
    "tts":                    (tts,                    TTS_SCHEMA),
}


def tool_schemas() -> list[dict[str, Any]]:
    """Return list of OpenAI-format tool schemas for all registered tools."""
    return [schema for _, schema in TOOL_REGISTRY.values()]
