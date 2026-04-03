"""Tool adapters for cross-dataset benchmarking.

All tools output a score between 0-1 through a unified interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class ToolAdapter(ABC):
    """Unified interface for all similarity detection tools.

    Every tool must implement compare() returning a float in [0, 1].
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        """Return similarity score in [0, 1]."""
        pass

    def compare_batch(
        self,
        pairs: List[Tuple[str, str]],
        **kwargs,
    ) -> List[float]:
        return [self.compare(a, b, **kwargs) for a, b in pairs]


class EngineToolAdapter(ToolAdapter):
    """Adapt an existing BaseEngine to the ToolAdapter interface.

    Wraps engines from src/engines/base_engine.py and normalizes
    their output to [0, 1].
    """

    def __init__(
        self,
        engine,
        name: Optional[str] = None,
        score_range: Optional[Tuple[float, float]] = None,
    ):
        self._engine = engine
        self._name = name or getattr(engine, "name", "unknown")
        self._score_range = score_range

    @property
    def name(self) -> str:
        return self._name

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        result = self._engine.compare(code_a, code_b, **kwargs)
        raw_score = self._extract_score(result)
        return self._normalize(raw_score)

    def _extract_score(self, result) -> float:
        if isinstance(result, (int, float)):
            return float(result)
        if hasattr(result, "score"):
            return float(result.score)
        if isinstance(result, dict):
            return float(result.get("score", result.get("similarity", 0.0)))
        return 0.0

    def _normalize(self, raw: float) -> float:
        if self._score_range is not None:
            lo, hi = self._score_range
            if hi == lo:
                return 0.0
            normalized = (raw - lo) / (hi - lo)
            return max(0.0, min(1.0, normalized))
        return max(0.0, min(1.0, raw))


class FunctionToolAdapter(ToolAdapter):
    """Adapt a plain function to the ToolAdapter interface."""

    def __init__(self, func, name: str):
        self._func = func
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        return float(self._func(code_a, code_b, **kwargs))


class JaccardToolAdapter(ToolAdapter):
    """Simple token-level Jaccard similarity as a baseline tool."""

    @property
    def name(self) -> str:
        return "jaccard"

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        tokens_a = set(code_a.split())
        tokens_b = set(code_b.split())
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)


class LineOverlapToolAdapter(ToolAdapter):
    """Line-level overlap similarity as a baseline tool."""

    @property
    def name(self) -> str:
        return "line_overlap"

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        lines_a = set(code_a.strip().splitlines())
        lines_b = set(code_b.strip().splitlines())
        lines_a = {l.strip() for l in lines_a if l.strip()}
        lines_b = {l.strip() for l in lines_b if l.strip()}
        if not lines_a and not lines_b:
            return 1.0
        if not lines_a or not lines_b:
            return 0.0
        intersection = lines_a & lines_b
        union = lines_a | lines_b
        return len(intersection) / len(union)
