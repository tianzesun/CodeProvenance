"""Base adapter interface - FROZEN CONTRACT.

All adapters MUST implement this interface. No exceptions.
No legacy float returns. No custom formats.

This is the scientific enforcement of consistency.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.backend.benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair


class BaseAdapter(ABC):
    """Base class for all benchmark adapters.

    Every adapter must implement `evaluate()` returning canonical `EvaluationResult`.
    This ensures:
    - Comparability across engines
    - Scientific rigor
    - Auditability
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return adapter name.

        Returns:
            Adapter name (e.g., "jplag", "moss", "nicad").
        """
        pass

    @property
    def version(self) -> str:
        """Return adapter version.

        Returns:
            Adapter version string.
        """
        return "1.0"

    @abstractmethod
    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate a code pair - FROZEN INTERFACE.

        Args:
            pair: EnrichedPair with code snippets and metadata.

        Returns:
            EvaluationResult with canonical schema.

        Raises:
            NotImplementedError: If not implemented.
        """
        pass

    def evaluate_batch(self, pairs: List[EnrichedPair]) -> List[EvaluationResult]:
        """Evaluate a batch of code pairs.

        Default implementation calls evaluate() for each pair.
        Subclasses may override for batch optimization.

        Args:
            pairs: List of EnrichedPair instances.

        Returns:
            List of EvaluationResult instances.
        """
        return [self.evaluate(pair) for pair in pairs]

    def compare(self, code1: str, code2: str) -> float:
        """Compare two code strings - compatibility layer for registry.
        
        This method wraps evaluate() to provide compatibility with the
        DetectionEngine interface expected by the registry.
        
        Args:
            code1: First code string.
            code2: Second code string.
            
        Returns:
            Similarity score in [0, 1].
        """
        from src.backend.benchmark.contracts.evaluation_result import EnrichedPair
        
        # Create a synthetic pair for comparison
        pair = EnrichedPair(
            pair_id=f"compare_{id(code1)}_{id(code2)}",
            id_a="code1",
            id_b="code2",
            code_a=code1,
            code_b=code2,
            label=0,  # Unknown
            clone_type=0,  # Unknown
            difficulty="MEDIUM",
            language="python",
        )
        
        result = self.evaluate(pair)
        return result.score

    def _make_result(
        self,
        pair: EnrichedPair,
        score: float,
        threshold: float = 0.5,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Helper to create EvaluationResult.

        Args:
            pair: The evaluated pair.
            score: Similarity score in [0, 1].
            threshold: Decision threshold.
            confidence: Confidence score (defaults to score).
            metadata: Additional metadata.

        Returns:
            EvaluationResult with canonical schema.
        """
        # Clamp score to [0, 1]
        score = max(0.0, min(1.0, score))

        # Default confidence to score if not provided
        if confidence is None:
            confidence = score

        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        # Binary decision
        decision = score >= threshold

        return EvaluationResult(
            pair_id=pair.pair_id,
            score=score,
            decision=decision,
            confidence=confidence,
            engine=self.name,
            metadata=metadata or {},
        )
