"""Comparative runner plugin."""
from typing import Dict, Any
from pathlib import Path
from src.bootstrap.plugins.plugin_base import ExecutionPlugin
from src.bootstrap.plugins.loader import register_plugin


@register_plugin
class ComparativeRunner(ExecutionPlugin):
    """Comparative analysis plugin."""

    name = "compare"

    def run(self, baseline: str, candidate: str) -> Dict[str, Any]:
        """Run comparative analysis between two datasets.

        Args:
            baseline: Baseline dataset name.
            candidate: Candidate dataset name.

        Returns:
            Comparative analysis results.
        """
        # Import here to avoid circular imports
        from benchmark.runners import ComparativeBenchmarkRunner

        runner = ComparativeBenchmarkRunner()

        baseline_path = Path(f"data/{baseline}")
        candidate_path = Path(f"data/{candidate}")

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline dataset not found: {baseline_path}")
        if not candidate_path.exists():
            raise FileNotFoundError(f"Candidate dataset not found: {candidate_path}")

        baseline_pairs = runner.load_dataset(baseline_path)
        candidate_pairs = runner.load_dataset(candidate_path)

        baseline_result = runner.evaluate(baseline_pairs)
        candidate_result = runner.evaluate(candidate_pairs)

        return {
            "baseline": baseline_result.summary_dict(),
            "candidate": candidate_result.summary_dict(),
            "comparison": {
                "f1_delta": round(
                    candidate_result.f1_score - baseline_result.f1_score, 4
                ),
                "precision_delta": round(
                    candidate_result.precision - baseline_result.precision, 4
                ),
                "recall_delta": round(
                    candidate_result.recall - baseline_result.recall, 4
                ),
            },
        }
