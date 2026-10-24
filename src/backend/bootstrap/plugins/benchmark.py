"""Benchmark runner plugin."""

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
            dataset: Accepted for CLI compatibility; the runners use synthetic data.
            mode: Execution mode (full, core, layer, diagnostic).

        Returns:
            Benchmark results dictionary.
        """
        # Import here to avoid circular imports. The runners live in their own
        # modules; the package __init__ does not re-export them.
        from src.backend.benchmark.runners.core_runner import CoreBenchmarkRunner
        from src.backend.benchmark.runners.diagnostic_runner import (
            DiagnosticBenchmarkRunner,
        )
        from src.backend.benchmark.runners.full_runner import FullBenchmarkRunner
        from src.backend.benchmark.runners.layer_runner import (
            ThreeLayerBenchmarkRunner,
        )

        runners_map: dict[str, type[Any]] = {
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

        # These runners generate their own synthetic pairs and expose run();
        # they have no load_dataset/evaluate, so ``dataset`` is not consumed.
        return runner_cls().run()
