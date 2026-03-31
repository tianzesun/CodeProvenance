"""Comparative evaluator for multi-tool comparison."""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime


@dataclass
class ComparativeResult:
    tool_results: Dict[str, Dict[str, Any]]
    benchmark_name: str
    evaluated_at: str = ""

    def rank_by(self, metric: str = 'f1_score') -> List[Tuple[str, float]]:
        rankings = [(t, r.get(metric, 0.0)) for t, r in self.tool_results.items()]
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def summary_table(self) -> str:
        h = f"{'Tool':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'AUC':>10}"
        lines = [h, "-" * 62]
        for t, _ in self.rank_by('f1_score'):
            r = self.tool_results.get(t, {})
            lines.append(f"{t:<20} {r.get('precision',0):>10.4f} {r.get('recall',0):>10.4f} {r.get('f1_score',0):>10.4f} {r.get('roc_auc',0):>10.4f}")
        return "\n".join(lines)


class ComparativeEvaluator:
    def __init__(self, benchmark_name: str):
        self.benchmark_name = benchmark_name
        self.tool_results: Dict[str, Dict[str, Any]] = {}

    def add_result(self, tool_name: str, metrics: Dict[str, Any]) -> None:
        self.tool_results[tool_name] = metrics

    def add_benchmark_result(self, tool_name: str, result) -> None:
        metrics = {
            'precision': result.precision, 'recall': result.recall,
            'f1_score': result.f1_score, 'accuracy': result.accuracy,
            'tp': result.true_positives, 'fp': result.false_positives,
            'fn': result.false_negatives, 'tn': result.true_negatives,
        }
        if result.predictions:
            from benchmark.evaluators.similarity_evaluator import SimilarityEvaluator
            metrics['roc_auc'] = SimilarityEvaluator.compute_roc_auc(result.predictions)
        self.add_result(tool_name, metrics)

    def evaluate(self) -> ComparativeResult:
        return ComparativeResult(tool_results=self.tool_results,
                                 benchmark_name=self.benchmark_name, evaluated_at=datetime.now().isoformat())

    def rank_tools(self, metric: str = 'f1_score') -> List[Tuple[str, float]]:
        rankings = [(t, r.get(metric, 0.0)) for t, r in self.tool_results.items()]
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def save(self, output_path: Path, format: str = 'json') -> None:
        result = self.evaluate()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if format == 'json':
            with open(output_path, 'w') as f:
                json.dump({'benchmark': result.benchmark_name, 'results': result.tool_results,
                           'rankings': {'f1': self.rank_tools('f1_score')}}, f, indent=2)
