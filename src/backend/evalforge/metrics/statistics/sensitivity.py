"""
Sensitivity Analysis Module.

Measures how similarity scores degrade as perturbation intensity increases.
Answers the question: "How sensitive is this system to small changes?"
"""

from typing import Dict, List
import numpy as np


class SensitivityAnalyzer:
    """
    Analyzes score sensitivity across increasing perturbation intensity levels.
    
    Uses finite difference methods to measure score degradation across
    standardized transformation intensities.
    """

    @staticmethod
    def compute(scores_by_level: Dict[int, float]) -> Dict[str, float]:
        """
        Compute sensitivity curve across perturbation levels.

        Args:
            scores_by_level: Dictionary mapping perturbation intensity level (0..5)
                           to observed similarity score

        Returns:
            Dictionary with mean_delta, max_drop, sensitivity_curve
        """
        levels = sorted(scores_by_level.keys())
        deltas = []

        for i in range(len(levels) - 1):
            current_level = levels[i]
            next_level = levels[i + 1]
            delta = scores_by_level[next_level] - scores_by_level[current_level]
            deltas.append(delta)

        return {
            "mean_delta": float(np.mean(deltas)) if deltas else 0.0,
            "max_drop": float(min(deltas)) if deltas else 0.0,
            "sensitivity_curve": deltas,
            "total_degradation": float(scores_by_level[levels[-1]] - scores_by_level[levels[0]]),
            "decay_rate": float(np.mean(np.abs(deltas))) if deltas else 0.0
        }

    @staticmethod
    def rank_sensitivity(
        tool_scores: Dict[str, Dict[int, float]]
    ) -> Dict[str, Dict[str, float]]:
        """Rank multiple tools by sensitivity performance."""
        results = {}
        for tool_id, level_scores in tool_scores.items():
            results[tool_id] = SensitivityAnalyzer.compute(level_scores)
        
        return dict(sorted(
            results.items(),
            key=lambda x: abs(x[1]["mean_delta"])
        ))