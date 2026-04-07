"""
Result Aggregation Layer.

Computes group-level statistics across multiple pairs and tools.
This layer produces the final publication-grade summary metrics.
"""

from typing import List, Dict, Any
import numpy as np


class ResultAggregator:
    """
    Aggregates individual pair-level results into global benchmark statistics.
    
    Computes summary metrics that can be directly published in papers or product
    documentation.
    """

    @staticmethod
    def summarize_pair_results(
        pair_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate results across multiple code pairs.

        Args:
            pair_results: List of per-pair results with distribution, ci, robustness

        Returns:
            Global summary statistics
        """
        means = [r["distribution"]["mean"] for r in pair_results]
        stds = [r["distribution"]["std"] for r in pair_results]
        robustness_scores = [r["robustness"]["robustness_score"] for r in pair_results]
        ci_lowers = [r["confidence_interval"]["ci_lower"] for r in pair_results]
        ci_uppers = [r["confidence_interval"]["ci_upper"] for r in pair_results]

        return {
            "global_mean": float(np.mean(means)),
            "global_std": float(np.mean(stds)),
            "mean_ci_width": float(np.mean(np.subtract(ci_uppers, ci_lowers))),
            "robustness_mean": float(np.mean(robustness_scores)),
            "robustness_std": float(np.std(robustness_scores)),
            "pair_count": len(pair_results),
            "individual_results": pair_results
        }

    @staticmethod
    def cross_tool_comparison(
        tool_results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Dict[str, float]]:
        """Generate comparative summary across multiple detection tools."""
        comparison = {}

        for tool_id, results in tool_results.items():
            robustness_scores = [r["robustness"]["robustness_score"] for r in results]
            means = [r["distribution"]["mean"] for r in results]

            comparison[tool_id] = {
                "average_score": float(np.mean(means)),
                "average_robustness": float(np.mean(robustness_scores)),
                "score_std": float(np.std(means)),
                "rank": 0  # to be filled after sorting
            }

        # Assign ranks by robustness (primary) then score (secondary)
        sorted_tools = sorted(
            comparison.keys(),
            key=lambda t: (-comparison[t]["average_robustness"], -comparison[t]["average_score"])
        )

        for i, tool_id in enumerate(sorted_tools):
            comparison[tool_id]["rank"] = i + 1

        return comparison