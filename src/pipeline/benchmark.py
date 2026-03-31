"""Benchmark Pipeline - Automated evaluation against standard datasets."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
from benchmark.runners.base_runner import BaseRunner, BenchmarkResult
from benchmark.runners.bigclonebench_runner import BigCloneBenchRunner
from benchmark.evaluators.similarity_evaluator import SimilarityEvaluator


@dataclass
class BenchmarkConfig:
    dataset_path: Path
    threshold: float = 0.5
    output_path: Optional[Path] = None


@dataclass
class BenchmarkOutput:
    benchmark_name: str
    tool_name: str
    metrics: Dict[str, Any]
    result: BenchmarkResult
    generated_at: str = ""


class BenchmarkPipeline:
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.runner: Optional[BaseRunner] = None

    def run(self, benchmark_name: str = 'bigclonebench') -> BenchmarkOutput:
        if benchmark_name.lower() == 'bigclonebench':
            self.runner = BigCloneBenchRunner(threshold=self.config.threshold)
        else:
            raise ValueError(f"Unknown benchmark: {benchmark_name}")
        result = self.runner.run(self.config.dataset_path)
        metrics = SimilarityEvaluator.compute_metrics(result)
        if result.predictions:
            metrics['roc_auc'] = SimilarityEvaluator.compute_roc_auc(result.predictions)
        return BenchmarkOutput(benchmark_name=benchmark_name, tool_name="CodeProvenance",
                               metrics=metrics, result=result, generated_at=datetime.now().isoformat())

    def threshold_sweep(self, benchmark_name: str = 'bigclonebench') -> Dict[str, Any]:
        if benchmark_name.lower() == 'bigclonebench':
            self.runner = BigCloneBenchRunner(threshold=self.config.threshold)
        result = self.runner.run(self.config.dataset_path)
        if not result.predictions:
            return {'error': 'No predictions'}
        sweep = SimilarityEvaluator.threshold_sweep(result.predictions)
        opt_th, opt_f1 = SimilarityEvaluator.find_optimal_threshold(result.predictions)
        return {'optimal_threshold': opt_th, 'optimal_f1': opt_f1, 'sweep': sweep}
