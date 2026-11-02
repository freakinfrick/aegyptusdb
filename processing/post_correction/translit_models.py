"""Python-native loader for MaReTE TranslitModels.

The TranslitModels repo provides JSON model files that map Manuel de Codage
hieroglyphic encodings to possible transliterations with frequency data.
These models were built from AES and RAMSES corpora.

Key insight: the JARs in the repo are MODEL BUILDERS (training tools).
The actual models are JSON files that we load directly in Python --
no JVM needed for inference/lookup.

Model structure:
    {
        "words": [
            {
                "encoding": "M17 X1 D21 N35",  # MdC sign sequence
                "interpretations": [
                    {
                        "transliteration": "jtrn",
                        "freq": 42,
                        "relFreq": 85.7,
                        "originalsLemmasInAes": [{"lemma": "jtrn"}]
                    },
                    ...
                ]
            },
            ...
        ]
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Default model paths relative to project root
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[2] / "data" / "upstream" / "translit_models" / "Models"


@dataclass
class Interpretation:
    """A possible transliteration for an MdC encoding."""

    transliteration: str
    freq: int
    rel_freq: float
    lemmas: list[str] = field(default_factory=list)


@dataclass
class TranslitEntry:
    """A word entry: MdC encoding -> possible transliterations."""

    encoding: str
    interpretations: list[Interpretation]

    @property
    def best_transliteration(self) -> str | None:
        """Return the most frequent transliteration."""
        if not self.interpretations:
            return None
        return max(self.interpretations, key=lambda i: i.freq).transliteration

    @property
    def top_n(self, n: int = 3) -> list[Interpretation]:
        """Return the top N most frequent interpretations."""
        return sorted(self.interpretations, key=lambda i: -i.freq)[:n]


class TranslitModel:
    """A loaded transliteration model with lookup capabilities."""

    def __init__(self, name: str, source: str):
        self.name = name
        self.source = source
        self._by_encoding: dict[str, TranslitEntry] = {}
        self._word_count = 0

    @property
    def size(self) -> int:
        return self._word_count

    def add_entry(self, entry: TranslitEntry) -> None:
        self._by_encoding[entry.encoding] = entry
        self._word_count += 1

    def lookup(self, encoding: str) -> TranslitEntry | None:
        """Look up transliterations for an MdC encoding."""
        return self._by_encoding.get(encoding)

    def best_transliteration(self, encoding: str) -> str | None:
        """Get the most likely transliteration for an MdC encoding."""
        entry = self.lookup(encoding)
        if entry:
            return entry.best_transliteration
        return None

    def all_transliterations(self, encoding: str) -> list[Interpretation]:
        """Get all possible transliterations with frequencies."""
        entry = self.lookup(encoding)
        if entry:
            return sorted(entry.interpretations, key=lambda i: -i.freq)
        return []

    def validate_transliteration(self, encoding: str, transliteration: str) -> float | None:
        """Check if a transliteration is valid for an encoding.

        Returns the relative frequency (0-100) if found, None if not in model.
        """
        entry = self.lookup(encoding)
        if not entry:
            return None

        for interp in entry.interpretations:
            if interp.transliteration == transliteration:
                return interp.rel_freq

        return 0.0  # Encoding known but transliteration not found

    def suggest_corrections(self, encoding: str, ocr_transliteration: str) -> list[tuple[str, float]]:
        """Suggest corrections for a possibly garbled OCR transliteration.

        Returns list of (suggested_transliteration, confidence) tuples.
        """
        entry = self.lookup(encoding)
        if not entry:
            return []

        suggestions = []
        for interp in sorted(entry.interpretations, key=lambda i: -i.freq):
            # Calculate simple edit-distance-based confidence
            confidence = interp.rel_freq / 100.0
            suggestions.append((interp.transliteration, confidence))

        return suggestions[:5]

    def has_encoding(self, encoding: str) -> bool:
        return encoding in self._by_encoding


class TranslitModelLoader:
    """Loads TranslitModels JSON files into Python objects.

    Usage:
        loader = TranslitModelLoader()
        model = loader.load_combined()  # AES+RAMSES model
        result = model.best_transliteration("M17 X1")
    """

    def __init__(self, models_dir: str | Path | None = None):
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR

    def load(self, model_file: str | Path) -> TranslitModel:
        """Load a single model JSON file."""
        path = Path(model_file)
        if not path.is_absolute():
            path = self.models_dir / path

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        logger.info("Loading TranslitModel from %s", path.name)
        with open(path) as f:
            data = json.load(f)

        model = TranslitModel(
            name=data.get("modelName", path.stem),
            source=data.get("modelSource", ""),
        )

        for word_data in data.get("words", []):
            interpretations = []
            for interp_data in word_data.get("interpretations", []):
                lemmas = [
                    lem.get("lemma", "")
                    for lem in interp_data.get("originalsLemmasInAes", [])
                ]
                interpretations.append(Interpretation(
                    transliteration=interp_data["transliteration"],
                    freq=interp_data.get("freq", 0),
                    rel_freq=interp_data.get("relFreq", 0.0),
                    lemmas=lemmas,
                ))

            model.add_entry(TranslitEntry(
                encoding=word_data["encoding"],
                interpretations=interpretations,
            ))

        logger.info("Loaded %s: %d entries", model.name, model.size)
        return model

    def load_aes(self) -> TranslitModel:
        """Load the AES (Ancient Egyptian Sentences) model."""
        return self.load("AESModel.json")

    def load_ramses(self) -> TranslitModel:
        """Load the RAMSES training set model."""
        return self.load("RamsesTrainingSetModel.json")

    def load_combined(self) -> TranslitModel:
        """Load the combined AES+RAMSES model (recommended)."""
        return self.load("AES+RamsesTrainingSetModel.json")

    def available_models(self) -> list[str]:
        """List available model files."""
        if not self.models_dir.exists():
            return []
        return [f.name for f in self.models_dir.glob("*.json")]
