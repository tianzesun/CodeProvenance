"""Feature Extraction - unified feature computation."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from src.backend.engines.features.feature_extractor import (
        FeatureExtractor,
        FeatureVector,
    )

__all__ = ["FeatureExtractor", "FeatureVector"]


def __getattr__(name: str) -> Any:
    """Load ``FeatureExtractor`` / ``FeatureVector`` on first access (PEP 562).

    The eager import made ``import src.backend.engines.features.ast_normalizer``
    (or ``scalable_index``, or ``stylometry``) load the whole engine stack —
    settings, the multi-layer AST analysis, the file classifier — even though
    those modules need none of it, and it created import cycles whenever one of
    those engines imported a sibling from this package.

    ``from src.backend.engines.features import FeatureExtractor`` still works.
    """
    if name in __all__:
        module = importlib.import_module(f"{__name__}.feature_extractor")
        value = getattr(module, name)
        globals()[name] = value  # cache: later lookups skip __getattr__
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
