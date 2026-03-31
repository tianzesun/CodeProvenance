"""Similarity evaluator for precision, recall, F1 scores."""
from typing import Dict, List, Any, Optional, Tuple
import json
from pathlib import Path
from datetime import datetime
from benchmark.runners.base_runner import BenchmarkResult


class SimilarityEvaluator:
    @staticmethod
    def compute_metrics(result: BenchmarkResult) -> Dict[str, Any]:
        return {
            'precision': result.precision,
            'recall': result.recall,
            'f1_score': result.f1_score,
            'accuracy': result.accuracy,
            'true_positives': result.true_positives,
            'false_positives': result.false_positives,
            'false_negatives': result.false_negatives,
            'true_negatives': result.true_negatives,
            'total_pairs': result.total_pairs,
            'execution_time': result.execution_time,
        }

    @staticmethod
    def compute_roc_auc(predictions: List[Tuple[str, float, bool]]) -> float:
        if not predictions:
            return 0.0
        pos = [s for _, s, c in predictions if c]
        neg = [s for _, s, c in predictions if not c]
        if not pos or not neg:
            return 0.5
        conc = sum(1 if p > n else 0.5 if p == n else 0 for p in pos for n in neg)
        return conc / (len(pos) * len(neg))

    @staticmethod
    def threshold_sweep(predictions: List[Tuple[str, float, bool]], n: int = 20) -> List[Dict[str, Any]]:
        results = []
        for i in range(n + 1):
            th = i / n
            tp = fp = fn = tn = 0
            for _, s, c in predictions:
                pred = s >= th
                if c and pred: tp += 1
                elif not c and pred: fp += 1
                elif c and not pred: fn += 1
                else: tn += 1
            total = tp + fp + fn + tn
            prec = tp / (tp + fp) if tp + fp else 0
            rec = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
            results.append({'threshold': th, 'precision': prec, 'recall': rec, 'f1_score': f1,
                            'accuracy': (tp + tn) / total if total else 0,
                            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn})
        return results

    @staticmethod
    def find_optimal_threshold(predictions: List[Tuple[str, float, bool]], metric: str = 'f1_score') -> Tuple[float, float]:
        sweep = SimilarityEvaluator.threshold_sweep(predictions)
        best = max(sweep, key=lambda x: x.get(metric, 0))
        return best['threshold'], best.get(metric, 0)

    @staticmethod
    def save_metrics(metrics: Dict[str, Any], output_path: Path, tool: str = "CodeProvenance") -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump({'tool_name': tool, 'evaluated_at': datetime.now().isoformat(), 'metrics': metrics}, f, indent=2)
