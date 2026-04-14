"""Base similarity engine interface for the benchmark system.

This is the SINGLE authoritative interface that ALL detection engines must implement.
No engine is allowed outside this contract.

Contract:
    - Input: two normalized code strings
    - Output: similarity score in [0.0, 1.0]
    - 0.0 = completely different, 1.0 = identical
    - Deterministic: same inputs always produce same output
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SimilarityScore:
    """Result of a similarity comparison.
    
    Attributes:
        score: Overall similarity score in [0.0, 1.0].
        component_scores: Breakdown by component (e.g., token, ast, semantic).
        confidence: Confidence in the score [0.0, 1.0].
        metadata: Additional information about the comparison.
    """
    score: float
    component_scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate score ranges."""
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"Similarity score must be in [0.0, 1.0], got {self.score}"
            )


class BaseSimilarityEngine(ABC):
    """Abstract base class for ALL detection engines.
    
    ALL engines MUST implement this interface.
    This guarantees:
    1. Consistent API across all engines
    2. Comparable results across engine types
    3. Reproducible experiments
    4. Benchmark-driven improvement
    
    Usage:
        class TokenEngine(BaseSimilarityEngine):
            @property
            def name(self) -> str:
                return "token_v1"
            
            def compare(self, code_a: str, code_b: str) -> float:
                # Return similarity in [0, 1]
                return compute_token_similarity(code_a, code_b)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return unique engine identifier.
        
        Returns:
            Unique name for this engine (e.g., "token_v1", "ast_hybrid").
            Must be stable across runs for reproducibility.
        """
        pass
    
    @abstractmethod
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code snippets and return similarity score.
        
        MANDATORY CONTRACT:
        - Input: two normalized code strings
        - Output: similarity score in [0.0, 1.0]
        - 0.0 means completely different
        - 1.0 means identical
        - Must be deterministic (same inputs -> same output)
        
        Args:
            code_a: First normalized code string.
            code_b: Second normalized code string.
            
        Returns:
            Similarity score between 0.0 and 1.0.
            
        Raises:
            ValueError: If inputs are empty or invalid.
        """
        pass
    
    def compare_with_details(self, code_a: str, code_b: str) -> SimilarityScore:
        """Compare with detailed breakdown. Default: wraps compare().
        
        Override this if your engine provides component-level scores.
        
        Args:
            code_a: First normalized code string.
            code_b: Second normalized code string.
            
        Returns:
            SimilarityScore with breakdown.
        """
        score = self.compare(code_a, code_b)
        return SimilarityScore(
            score=score,
            component_scores={self.name: score},
            metadata={"engine": self.name}
        )
    
    def supports_language(self, language: str) -> bool:
        """Check if engine supports a specific language.
        
        Args:
            language: Programming language identifier.
            
        Returns:
            True if engine can process this language.
        """
        return True
    
    def configure(self, **kwargs: Any) -> None:
        """Configure engine parameters (optional override).
        
        Args:
            **kwargs: Configuration key-value pairs.
        """
        pass
    
    def reset(self) -> None:
        """Reset engine state (for stateful engines)."""
        pass