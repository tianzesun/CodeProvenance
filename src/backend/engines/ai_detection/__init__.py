"""AI Detection Engine - Advanced code generation detection.

Provides transformer-based perplexity, model fingerprinting, AST analysis,
and ensemble ML for state-of-the-art AI code detection.
"""

from .transformer_perplexity import (
    TransformerPerplexityAnalyzer,
    compute_perplexity,
    compute_ai_score,
    get_analyzer,
)
from .model_fingerprinting import (
    ModelFingerprinter,
    ModelFingerprint,
    detect_model,
    get_fingerprinter,
)

__all__ = [
    "TransformerPerplexityAnalyzer",
    "compute_perplexity",
    "compute_ai_score",
    "get_analyzer",
    "ModelFingerprinter",
    "ModelFingerprint",
    "detect_model",
    "get_fingerprinter",
]
