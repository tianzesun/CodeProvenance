"""Diagnostic runner plugin."""

from pathlib import Path
from typing import Any

from src.backend.bootstrap.plugins.loader import register_plugin
from src.backend.bootstrap.plugins.plugin_base import ExecutionPlugin


@register_plugin
class DiagnosticRunner(ExecutionPlugin):
    """Diagnostic analysis plugin."""

    name = "diagnose"

    def run(self, job_id: str) -> dict[str, Any]:
        """Run diagnostic analysis on a job.

        Args:
            job_id: Job ID to diagnose.

        Returns:
            Diagnostic results dictionary.
        """
        # Import here to avoid circular imports
        from benchmark.runners import DiagnosticBenchmarkRunner

        runner = DiagnosticBenchmarkRunner()

        job_path = Path(f"data/jobs/{job_id}")
        if not job_path.exists():
            raise FileNotFoundError(f"Job not found: {job_path}")

        pairs = runner.load_dataset(job_path)
        result = runner.evaluate(pairs)
        return result.summary_dict()
