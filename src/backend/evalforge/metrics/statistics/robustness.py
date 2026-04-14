"""
Robustness Scoring Engine - Core research contribution metric.

Measures how stable similarity scores are under semantic-preserving transformations.
This is the primary metric for comparative benchmark evaluation.
"""

from typing import List, Dict
import numpy as np


class RobustnessScorer:
    """
    Computes robustness score for similarity detection systems.
    
    Robustness R = 1 - (coefficient of variation²)
    This metric measures how stable detection is under controlled perturbation.
    """

    @staticmethod
    def compute(base_score: float, transformed_scores: List[float]) -> Dict[str, float]:
        """
        Compute robustness score for a tool against transformation space.

        Args:
            base_score: Original unmodified pair score
            transformed_scores: Scores after applying semantic-preserving transformations

        Returns:
            Dictionary with robustness_score, variance, mean
        """
        variance = np.var(transformed_scores)
        mean = np.mean(transformed_scores)

        if mean == 0.0:
            robustness = 0.0
        else:
            # Robustness = 1 - (variance / mean²) = 1 - (coefficient of variation)²
            robustness = 1.0 - (variance / (mean ** 2))
            robustness = max(0.0, min(1.0, robustness))

        return {
            "robustness_score": float(robustness),
            "variance": float(variance),
            "mean": float(mean),
            "base_score": float(base_score)
        }

    @staticmethod
    def compare_robustness(
        tool_scores: Dict[str, List[float]],
        base_scores: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """Compare robustness across multiple tools."""
        return {
            tool_id: RobustnessScorer.compute(base_scores[tool_id], scores)
            for tool_id, scores in tool_scores.items()
        }