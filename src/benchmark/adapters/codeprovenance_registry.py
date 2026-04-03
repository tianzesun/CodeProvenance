"""Adapter for CodeProvenance versioned engine registry.

This adapter uses the new versioned strategy registration pattern
from src/engines/similarity/codeprovenance/registry.py
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from benchmark.similarity.base_engine import BaseSimilarityEngine


class CodeProvenanceRegistryEngine(BaseSimilarityEngine):
    """Adapter for CodeProvenance versioned engines using registry pattern.

    Uses the ENGINE_REGISTRY to get the appropriate engine version,
    enabling clean version management and reproducible evaluations.
    """

    def __init__(
        self,
        version: str = "codeprovenance:v3",
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize with specific engine version.

        Args:
            version: Engine version string (e.g., "codeprovenance:v1")
            config: Optional configuration for the engine
        """
        self._version = version
        self._config = config or {}
        self._engine = None

    def _get_engine(self) -> Any:
        """Lazy-load the engine from registry."""
        if self._engine is None:
            try:
                from src.engines.similarity.codeprovenance.registry import get_engine
                self._engine = get_engine(self._version)
            except ImportError:
                # Fallback to direct import if registry not available
                from src.engines.similarity.codeprovenance import get_engine
                self._engine = get_engine(self._version)
        return self._engine

    @property
    def name(self) -> str:
        """Engine name for identification."""
        return self._version

    @property
    def version(self) -> str:
        """Engine version string."""
        return self._version

    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using versioned engine.

        Args:
            code_a: First code string
            code_b: Second code string

        Returns:
            Similarity score in [0.0, 1.0]
        """
        if not code_a or not code_b:
            return 0.0

        engine = self._get_engine()

        try:
            score = engine.compare(code_a, code_b)
            return max(0.0, min(1.0, score))
        except Exception as e:
            print(f"Warning: CodeProvenance {self._version} failed: {e}")
            return self._fallback_similarity(code_a, code_b)

    def _fallback_similarity(self, code_a: str, code_b: str) -> float:
        """Simple fallback when full engine fails."""
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0

    def get_metadata(self) -> Dict[str, Any]:
        """Get engine metadata for reporting."""
        return {
            "engine": self._version,
            "version": self._version.split(":")[1] if ":" in self._version else "unknown",
            "config": self._config
        }


# Convenience classes for specific versions
class CodeProvenanceV1(CodeProvenanceRegistryEngine):
    """CodeProvenance v1: Basic token similarity."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(version="codeprovenance:v1", config=config)


class CodeProvenanceV2(CodeProvenanceRegistryEngine):
    """CodeProvenance v2: Token + AST hybrid."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(version="codeprovenance:v2", config=config)


class CodeProvenanceV3(CodeProvenanceRegistryEngine):
    """CodeProvenance v3: Multi-signal fusion."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(version="codeprovenance:v3", config=config)