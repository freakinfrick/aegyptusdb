"""Witness Index — parallel sentence retrieval and evidence assembly."""

from .index import InvertedIndexBuilder
from .dossier import WitnessDossier, TokenWitness, ParallelExample, assemble_dossier

__all__ = [
    "InvertedIndexBuilder",
    "WitnessDossier",
    "TokenWitness",
    "ParallelExample",
    "assemble_dossier",
]
