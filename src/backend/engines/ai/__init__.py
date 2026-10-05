"""AI-generated code detection.

Public names are loaded on first access (PEP 562) instead of at import time.
Importing any submodule (``ast_features``, ``classifier``, ``signals`` ...) used
to run this file first, which eagerly imported the orchestrator, the Binoculars
wrapper, the legacy similarity engine and numpy: heavy, and a source of import
cycles whenever one of those modules imported something from this package.

``from src.backend.engines.ai import AIDetectionOrchestrator`` still works.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from .binoculars_detector import BinocularsDetector
    from .orchestrator import AIDetectionOrchestrator
    from .transformer_detector import CodeBERTDetector, ZeroShotAIDetector

_EXPORTS: dict[str, str] = {
    "AIDetectionOrchestrator": ".orchestrator",
    "BinocularsDetector": ".binoculars_detector",
    "CodeBERTDetector": ".transformer_detector",
    "ZeroShotAIDetector": ".transformer_detector",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name, __name__), name)
    globals()[name] = value  # cache: later lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
