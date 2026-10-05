"""MVP detection primitives for high-precision plagiarism review.

Imports are lazy (PEP 562): ``pipeline`` and ``precision_ranking`` need the evidence ranker and the
evaluation package, and importing them eagerly made the normaliser, AST hasher, starter remover and
same-bug detector unusable whenever either was unavailable.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_BASE = "src.backend.engines.mvp"
_EXPORTS: dict[str, tuple[str, str]] = {
    "ASTSubtreeHasher": ("ast_subtree", "ASTSubtreeHasher"),
    "ASTComparison": ("ast_subtree", "ASTComparison"),
    "CodeNormalizer": ("normalization", "CodeNormalizer"),
    "NormalizedCode": ("normalization", "NormalizedCode"),
    "MVPDetectionPipeline": ("pipeline", "MVPDetectionPipeline"),
    "MVPAnalysisResult": ("pipeline", "MVPAnalysisResult"),
    "PrecisionAt20Ranker": ("precision_ranking", "PrecisionAt20Ranker"),
    "RankedCase": ("precision_ranking", "RankedCase"),
    "RuntimeOutcome": ("same_bug", "RuntimeOutcome"),
    "SameBugDetector": ("same_bug", "SameBugDetector"),
    "SameBugFinding": ("same_bug", "SameBugFinding"),
    "StarterCodeRemover": ("starter_code", "StarterCodeRemover"),
    "StarterRemovalResult": ("starter_code", "StarterRemovalResult"),
}

__all__ = list(_EXPORTS)

if TYPE_CHECKING:  # pragma: no cover
    from src.backend.engines.mvp.ast_subtree import ASTComparison, ASTSubtreeHasher
    from src.backend.engines.mvp.normalization import CodeNormalizer, NormalizedCode
    from src.backend.engines.mvp.pipeline import MVPAnalysisResult, MVPDetectionPipeline
    from src.backend.engines.mvp.precision_ranking import PrecisionAt20Ranker, RankedCase
    from src.backend.engines.mvp.same_bug import RuntimeOutcome, SameBugDetector, SameBugFinding
    from src.backend.engines.mvp.starter_code import StarterCodeRemover, StarterRemovalResult


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(f"{_BASE}.{module_name}"), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *_EXPORTS])
