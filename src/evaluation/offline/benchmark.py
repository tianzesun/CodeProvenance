"""Benchmark Runner - uses unified evaluation system."""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from src.evaluation.evaluator import Evaluator
from src.evaluation.metrics import Metrics
from benchmark.runners.base_runner import BaseRunner as BenchmarkRunner, BenchmarkPair, BenchmarkResult

@dataclass
class BenchmarkOutput:
    tool: str
    dataset: str
    metrics: Dict[str, Any]
    report: Dict

class Benchmark:
    """Benchmark runner using unified evaluation."""
    def __init__(self, threshold: float = 0.5):
        self.evaluator = Evaluator()
        self.threshold = threshold
    def run(self, runner: BenchmarkRunner, dataset_path: Path) -> BenchmarkOutput:
        result = runner.run(dataset_path)
        return BenchmarkOutput(
            tool=runner.tool_name,
            dataset=runner.dataset,
            metrics=result.to_dict(),
            report={},
        )