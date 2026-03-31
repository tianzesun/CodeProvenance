"""Benchmark Pipeline - Automated evaluation with unified output format."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import csv
import yaml
from benchmark.runners.base_runner import BaseRunner, BenchmarkResult, BenchmarkPair
from benchmark.runners.bigclonebench_runner import BigCloneBenchRunner
from benchmark.evaluator.standard import BenchmarkEvaluator, ReportWriter


@dataclass
class BenchmarkConfig:
    dataset_path: Path
    threshold: float = 0.5
    ground_truth_path: Optional[Path] = None


@dataclass
class BenchmarkOutput:
    experiment: str
    dataset: str
    tool: str
    metrics: Dict[str, Any]
    timestamp: str = ""


class BenchmarkPipeline:
    """
    Benchmark pipeline following PRO3.md standard:
    1. Run tool (normalize output to standard format)
    2. Evaluate against ground truth
    3. Save CSV + JSON reports
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.report_writer = ReportWriter()
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'BenchmarkPipeline':
        """Load pipeline configuration from benchmark.yaml."""
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f)
        dataset_cfg = cfg.get("datasets", [])[0]
        eval_cfg = cfg.get("evaluation", {})
        return cls(BenchmarkConfig(
            dataset_path=Path(dataset_cfg.get("path", "")),
            threshold=eval_cfg.get("threshold", 0.5),
        ))
    
    def run(self, tool_name: str = "CodeProvenance",
            benchmark_name: str = "bigclonebench", experiment: str = "baseline_v1") -> BenchmarkOutput:
        """
        Execute benchmark: run tool -> normalize -> evaluate -> report.
        """
        # 1. Load ground truth
        gt_path = self.config.dataset_path / "ground_truth.json"
        ground_truth = {"pairs": []}
        if gt_path.exists():
            with open(gt_path) as f:
                ground_truth = json.load(f)
        # 2. Run detection
        runner = BigCloneBenchRunner(threshold=self.config.threshold)
        pairs = runner.load_dataset(self.config.dataset_path)
        # 3. Normalize to standard output format
        predictions = []
        for p in pairs:
            sim = runner.run_comparison(p, self.config.threshold)
            predictions.append({
                "file1": p.id + "_a",
                "file2": p.id + "_b",
                "similarity": sim,
            })
        # 4. Generate predictions.json
        pred_data = {"pairs": predictions}
        pred_path = self.config.dataset_path / "predictions.json"
        pred_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pred_path, 'w') as f:
            json.dump(pred_data, f, indent=2)
        # 5. Evaluate
        metrics = BenchmarkEvaluator.evaluate(predictions, ground_truth, self.config.threshold)
        # 6. Save reports
        report_results = {tool_name: metrics}
        self.report_writer.save_csv(report_results, f"{experiment}_{benchmark_name}")
        self.report_writer.save_json(experiment, benchmark_name, report_results)
        
        return BenchmarkOutput(
            experiment=experiment, dataset=benchmark_name, tool=tool_name,
            metrics=metrics, timestamp=datetime.now().isoformat()
        )
    
    def run_comparative(
        self, tool_results: Dict[str, List[Dict[str, Any]]],
        ground_truth_path: Path, experiment: str = "baseline_v1"
    ) -> Dict[str, Any]:
        """Compare multiple tools on the same dataset."""
        with open(ground_truth_path) as f:
            ground_truth = json.load(f)
        results = {}
        for tool_name, predictions in tool_results.items():
            results[tool_name] = BenchmarkEvaluator.evaluate(predictions, ground_truth, self.config.threshold)
        self.report_writer.save_csv(results, f"{experiment}_comparative")
        return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("pipeline/config/benchmark.yaml"))
    p.add_argument("--dataset", type=Path, required=False)
    p.add_argument("--threshold", type=float, default=0.5)
    args = p.parse_args()
    cfg = BenchmarkConfig(
        dataset_path=args.dataset or Path("benchmark/datasets/bigclone/"),
        threshold=args.threshold,
    )
    pipeline = BenchmarkPipeline(cfg)
    result = pipeline.run()
    print(f"\nBenchmark Result: {result.experiment}")
    print(json.dumps(result.metrics, indent=2))
