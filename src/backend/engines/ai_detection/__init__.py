"""AI Detection Engine - Advanced code generation detection.

Provides transformer-based perplexity, model fingerprinting, AST analysis,
adversarial defense, and ensemble ML for state-of-the-art AI code detection.

Submodules are imported lazily (PEP 562). ``transformer_perplexity`` used to be imported eagerly
and pulled in ``torch`` at import time, so a machine without torch lost the AST analyzer, the
fingerprinter and the adversarial defense as well.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

# public name -> (submodule, attribute)
_EXPORTS: dict[str, tuple[str, str]] = {
    "TransformerPerplexityAnalyzer": ("transformer_perplexity", "TransformerPerplexityAnalyzer"),
    "compute_perplexity": ("transformer_perplexity", "compute_perplexity"),
    "compute_ai_score": ("transformer_perplexity", "compute_ai_score"),
    "get_analyzer": ("transformer_perplexity", "get_analyzer"),
    "ModelFingerprinter": ("model_fingerprinting", "ModelFingerprinter"),
    "ModelFingerprint": ("model_fingerprinting", "ModelFingerprint"),
    "detect_model": ("model_fingerprinting", "detect_model"),
    "get_fingerprinter": ("model_fingerprinting", "get_fingerprinter"),
    "ASTAnalyzer": ("ast_analyzer", "ASTAnalyzer"),
    "ASTFeatures": ("ast_analyzer", "ASTFeatures"),
    "analyze_ast": ("ast_analyzer", "analyze_ast"),
    "compute_ast_score": ("ast_analyzer", "compute_ast_score"),
    "get_ast_analyzer": ("ast_analyzer", "get_analyzer"),
    "AdversarialDefense": ("adversarial_defense", "AdversarialDefense"),
    "AdversarialAnalysis": ("adversarial_defense", "AdversarialAnalysis"),
    "analyze_adversarial": ("adversarial_defense", "analyze_adversarial"),
    "compute_semantic_hash": ("adversarial_defense", "compute_semantic_hash"),
    "get_defense": ("adversarial_defense", "get_defense"),
}

__all__ = list(_EXPORTS)

if TYPE_CHECKING:  # pragma: no cover
    from .adversarial_defense import (
        AdversarialAnalysis,
        AdversarialDefense,
        analyze_adversarial,
        compute_semantic_hash,
        get_defense,
    )
    from .ast_analyzer import ASTAnalyzer, ASTFeatures, analyze_ast, compute_ast_score
    from .ast_analyzer import get_analyzer as get_ast_analyzer
    from .model_fingerprinting import ModelFingerprint, ModelFingerprinter, detect_model, get_fingerprinter
    from .transformer_perplexity import (
        TransformerPerplexityAnalyzer,
        compute_ai_score,
        compute_perplexity,
        get_analyzer,
    )


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(f".{module_name}", __name__), attribute)
    globals()[name] = value  # cache for next time
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *_EXPORTS])
