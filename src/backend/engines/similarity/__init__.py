"""Similarity Engines - pure computation via registry."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from src.backend.engines.similarity.similarity_registry import SimilarityRegistry

if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from src.backend.engines.similarity.base_similarity import (
        BaseSimilarityAlgorithm,
        SimilarityEngine,
        register_builtin_algorithms,
    )

__all__ = [
    "BaseSimilarityAlgorithm",
    "SimilarityEngine",
    "SimilarityRegistry",
    "register_builtin_algorithms",
]

_LAZY = {"BaseSimilarityAlgorithm", "SimilarityEngine", "register_builtin_algorithms"}


def __getattr__(name: str) -> Any:
    """Load names from ``base_similarity`` on first use.

    The old implementation returned ``BaseSimilarityAlgorithm`` for ALL THREE
    names, so ``from ... import SimilarityEngine`` silently handed back the abstract
    base class, and ``register_builtin_algorithms`` was that class too.
    """
    if name in _LAZY:
        value = getattr(importlib.import_module(f"{__name__}.base_similarity"), name)
        globals()[name] = value  # cache: later lookups skip __getattr__
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
