"""Adapter for CodeProvenance's actual similarity engine to benchmark interface.

This adapter wraps the actual CodeProvenance SimilarityEngine from src/engines/
so it can be registered and tested in the benchmark system.
"""
from __future__ import annotations

from typing import Any, Dict

from benchmark.similarity.base_engine import BaseSimilarityEngine


class CodeProvenanceEngine(BaseSimilarityEngine):
    """Adapter for CodeProvenance's SimilarityEngine to benchmark interface.
    
    Wraps the actual src/engines/similarity code to enable benchmark testing
    of the real tool, not just the simplified benchmark-only engines.
    """
    
    def __init__(
        self,
        token_weight: float = 1.5,
        ast_weight: float = 2.0,
        embedding_weight: float = 0.8,
        use_deep_analysis: bool = True,
    ):
        self._token_weight = token_weight
        self._ast_weight = ast_weight
        self._embedding_weight = embedding_weight
        self._use_deep_analysis = use_deep_analysis
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
        return "codeprovenance_v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using the actual CodeProvenance engine.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score in [0.0, 1.0].
        """
        if not code_a or not code_b:
            return 0.0
        
        engine = self._get_engine()
        
        # Parse code into the format expected by the engine
        # IMPORTANT: Must include "raw" key for UniXcoder/embedding engines
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
            
            # Apply calibration to reduce false positives
            # The fused score is already weighted, but we apply
            # a slight sigmoid-like calibration for better separation
            calibrated = self._calibrate_score(score)
            return max(0.0, min(1.0, calibrated))
        except Exception as e:
            print(f"Warning: CodeProvenance engine failed: {e}")
            return self._fallback_similarity(code_a, code_b)
    
    def _calibrate_score(self, score: float) -> float:
        """Calibrate score to reduce false positives.
        
        Uses a simple piecewise mapping:
        - Scores below 0.3 are mapped to near 0
        - Scores above 0.6 are mapped to near 1
        - Middle range is stretched
        """
        if score < 0.25:
            return score * 0.5  # Suppress low scores
        elif score > 0.6:
            return 0.6 + (score - 0.6) * 1.2  # Boost high scores
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