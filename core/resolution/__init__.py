"""Entity resolution and merge pipeline.

Resolves incoming text identifiers against the existing corpus,
then merges matched content or creates new records.
"""

from core.resolution.engine import (
    ALIAS_FUZZY_THRESHOLD,
    CONTENT_NGRAM_THRESHOLD,
    EntityResolver,
    MatchResult,
    NoMatch,
    ResolutionResult,
)
from core.resolution.merger import StagingMerger

__all__ = [
    "ALIAS_FUZZY_THRESHOLD",
    "CONTENT_NGRAM_THRESHOLD",
    "EntityResolver",
    "MatchResult",
    "NoMatch",
    "ResolutionResult",
    "StagingMerger",
]
