"""Benchmark runner plugin."""

from pathlib import Path
from typing import Any

from src.backend.bootstrap.plugins.loader import register_plugin
from src.backend.bootstrap.plugins.plugin_base import ExecutionPlugin


@register_plugin
class BenchmarkRunner(ExecutionPlugin):
    """Benchmark execution plugin."""

    name = "benchmark"

    def run(self, dataset: str, mode: str = "full") -> dict[str, Any]:
        """Run benchmark pipeline.

        Args:
            dataset: Dataset name to run benchmark on.
            mode: Execution mode (full, core, layer, diagnostic).

        Returns:
            Benchmark results dictionary.
        """
        # Import here to avoid circular imports
        from src.backend.benchmark.runners import (
            CoreBenchmarkRunner,
            DiagnosticBenchmarkRunner,
            FullBenchmarkRunner,
            ThreeLayerBenchmarkRunner,
        )

        runners_map = {
            "full": FullBenchmarkRunner,
            "core": CoreBenchmarkRunner,
            "layer": ThreeLayerBenchmarkRunner,
            "diagnostic": DiagnosticBenchmarkRunner,
        }

        runner_cls = runners_map.get(mode)
        if runner_cls is None:
            raise ValueError(
                f"Unknown mode: {mode}. Available: {list(runners_map.keys())}"
            )

        runner = runner_cls()
        dataset_path = Path(f"data/{dataset}")

        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        pairs = runner.load_dataset(dataset_path)
        result = runner.evaluate(pairs)
        return result.summary_dict()
