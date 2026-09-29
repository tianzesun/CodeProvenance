"""AI Detection Engine - Advanced code generation detection.

Provides transformer-based perplexity, model fingerprinting, AST analysis,
adversarial defense, and ensemble ML for state-of-the-art AI code detection.
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
from .ast_analyzer import (
    ASTAnalyzer,
    ASTFeatures,
    analyze_ast,
    compute_ast_score,
    get_analyzer as get_ast_analyzer,
)
from .adversarial_defense import (
    AdversarialDefense,
    AdversarialAnalysis,
    analyze_adversarial,
    compute_semantic_hash,
    get_defense,
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
    "ASTAnalyzer",
    "ASTFeatures",
    "analyze_ast",
    "compute_ast_score",
    "get_ast_analyzer",
    "AdversarialDefense",
    "AdversarialAnalysis",
    "analyze_adversarial",
    "compute_semantic_hash",
    "get_defense",
]
