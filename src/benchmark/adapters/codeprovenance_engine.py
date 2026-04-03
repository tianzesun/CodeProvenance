"""Adapter for CodeProvenance's actual similarity engine to benchmark interface.

This adapter wraps the actual CodeProvenance SimilarityEngine from src/engines/
so it can be registered and tested in the benchmark system.

FROZEN INTERFACE: evaluate() returns canonical EvaluationResult.
"""
from __future__ import annotations

from typing import Any, Dict

from .base_adapter import BaseAdapter
from ..contracts.evaluation_result import EvaluationResult, EnrichedPair


class CodeProvenanceAdapter(BaseAdapter):
    """CodeProvenance adapter with canonical output."""

    def __init__(
        self,
        token_weight: float = 1.5,
        ast_weight: float = 2.0,
        embedding_weight: float = 0.8,
        use_deep_analysis: bool = True,
        threshold: float = 0.5,
    ):
        self._token_weight = token_weight
        self._ast_weight = ast_weight
        self._embedding_weight = embedding_weight
        self._use_deep_analysis = use_deep_analysis
        self._threshold = threshold
        self._engine = None

    def _get_engine(self) -> Any:
        """Lazy-load the actual CodeProvenance engine."""
        if self._engine is None:
            from src.engines.similarity.base_similarity import SimilarityEngine
            from src.engines.similarity.base_similarity import register_builtin_algorithms

            self._engine = SimilarityEngine()
            register_builtin_algorithms(self._engine)
            self._engine.enable_deep_analysis(self._use_deep_analysis)
        return self._engine

    @property
    def name(self) -> str:
        return "codeprovenance"

    @property
    def version(self) -> str:
        return "1.0"

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate a code pair using CodeProvenance - FROZEN INTERFACE.

        Args:
            pair: EnrichedPair with code snippets and metadata.

        Returns:
            EvaluationResult with canonical schema.
        """
        score = self._compare(pair.code_a, pair.code_b)
        return self._make_result(
            pair=pair,
            score=score,
            threshold=self._threshold,
            metadata={
                "token_weight": self._token_weight,
                "ast_weight": self._ast_weight,
                "embedding_weight": self._embedding_weight,
                "use_deep_analysis": self._use_deep_analysis,
            },
        )

    def _compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using the actual CodeProvenance engine."""
        if not code_a or not code_b:
            return 0.0

        engine = self._get_engine()

        # Parse code into the format expected by the engine
        parsed_a = {
            "raw": code_a,
            "code": code_a,
            "tokens": code_a.split(),
            "ast": None,
            "language": "python",
        }
        parsed_b = {
            "raw": code_b,
            "code": code_b,
            "tokens": code_b.split(),
            "ast": None,
            "language": "python",
        }

        try:
            result = engine.compare(parsed_a, parsed_b)
            score = result.get("overall_score", 0.0)
            calibrated = self._calibrate_score(score)
            return max(0.0, min(1.0, calibrated))
        except Exception as e:
            print(f"Warning: CodeProvenance engine failed: {e}")
            return self._fallback_similarity(code_a, code_b)

    def _calibrate_score(self, score: float) -> float:
        """Calibrate score to reduce false positives."""
        if score < 0.25:
            return score * 0.5
        elif score > 0.6:
            return 0.6 + (score - 0.6) * 1.2
        else:
            return score

    def _fallback_similarity(self, code_a: str, code_b: str) -> float:
        """Simple fallback when full engine fails."""
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0
