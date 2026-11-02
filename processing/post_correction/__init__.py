"""OCR post-correction for Egyptological texts.

Provides:
- TranslitModels: Python-native loader for MaReTE transliteration models (JSON)
- JVM wrapper: subprocess interface to NeedlemanWunsch alignment JAR
- CorrectionService: full post-correction pipeline with rule-based + model-based stages
"""

from .translit_models import TranslitModelLoader, TranslitModel
from .jvm_wrapper import NeedlemanWunschWrapper
from .correction import CorrectionService, CorrectionResult

__all__ = [
    "TranslitModelLoader",
    "TranslitModel",
    "NeedlemanWunschWrapper",
    "CorrectionService",
    "CorrectionResult",
]
