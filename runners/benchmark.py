"""Benchmark runner plugin."""
from typing import Dict, Any
from pathlib import Path
from engines.registry.plugin_base import ExecutionPlugin
from engines.registry.loader import register_plugin


@register_plugin
class BenchmarkRunner(ExecutionPlugin):
    """Benchmark execution plugin."""

    name = "benchmark"

    def run(self, dataset: str, mode: str = "full") -> Dict[str, Any]:
        """Run benchmark pipeline.

        Args:
            dataset: Dataset name to run benchmark on.
            mode: Execution mode (full, core, layer, diagnostic).

        Returns:
            Benchmark results dictionary.
        """
        # Import here to avoid circular imports
        from benchmark.runners import (
            CoreBenchmarkRunner,
            FullBenchmarkRunner,
            ThreeLayerBenchmarkRunner,
            DiagnosticBenchmarkRunner,
        )

        runners_map = {
            "full": FullBenchmarkRunner,
            "core": CoreBenchmarkRunner,
            "layer": ThreeLayerBenchmarkRunner,
            "diagnostic": DiagnosticBenchmarkRunner,
        }

        runner_cls = runners_map.get(mode)
        if runner_cls is None:
            raise ValueError(f"Unknown mode: {mode}. Available: {list(runners_map.keys())}")

        runner = runner_cls()
        dataset_path = Path(f"data/{dataset}")

        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        pairs = runner.load_dataset(dataset_path)
        result = runner.evaluate(pairs)
        return result.summary_dict()
