"""Core benchmark runner - focused, reproducible, minimal dependencies."""

from __future__ import annotations

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from benchmark.metrics import compute_classification_metrics, mean_average_precision, mean_reciprocal_rank


class CoreBenchmarkRunner:
    """Core benchmark runner (Layer A only)."""

    def __init__(self, output_dir: str = "reports/core"):
        self.output_dir = output_dir

    def run(
        self,
        engine_name: str = "all",
        type1: int = 50,
        type2: int = 50,
        type3: int = 50,
        type4: int = 50,
        non_clone: int = 200,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Run core benchmark."""
        generator = SyntheticDatasetGenerator(seed=seed)
        dataset = generator.generate_pair_count(type1, type2, type3, type4, non_clone)
        
        pairs = [(p.code_a, p.code_b, p.label) for p in dataset.pairs]
        
        engines: Dict[str, Any] = {}
        if engine_name in ("token", "all"):
            engines["token"] = TokenWinnowingEngine()
        if engine_name in ("ast", "all"):
            engines["ast"] = ASTEngine()
        if engine_name in ("hybrid", "all"):
            engines["hybrid"] = HybridEngine()
        
        results: Dict[str, Any] = {}
        for name, engine in engines.items():
            results[name] = self._run_single_engine(engine, pairs)
        
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        report = {
            "run_id": f"core_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "dataset": {"name": "synthetic", "version": "1.0", "pairs": dataset.stats()},
            "engines": results,
        }
        
        report_file = output_path / f"{report['run_id']}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

    def _run_single_engine(
        self, engine: Any, pairs: List[Tuple[str, str, int]], threshold: float = 0.5
    ) -> Dict[str, Any]:
        """Run benchmark on a single engine."""
        scores: List[Tuple[float, int]] = []
        for code_a, code_b, label in pairs:
            score = engine.compare(code_a, code_b)
            scores.append((max(0.0, min(1.0, score)), label))
        
        best_threshold, best_f1 = self._optimize_threshold(scores)
        
        tp = fp = tn = fn = 0
        for score, label in scores:
            pred = 1 if score >= best_threshold else 0
            if pred == 1 and label == 1:
                tp += 1
            elif pred == 1 and label == 0:
                fp += 1
            elif pred == 0 and label == 0:
                tn += 1
            else:
                fn += 1
        
        classification = compute_classification_metrics(tp, fp, tn, fn)
        
        query_results: Dict[str, List[Tuple[str, float, int]]] = {}
        for i, (score, label) in enumerate(scores):
            q_id = f"q_{i // 10}"
            query_results.setdefault(q_id, []).append((f"d_{i}", score, label))
        
        map_score = mean_average_precision(query_results)
        mrr_score = mean_reciprocal_rank(query_results)
        
        return {
            "precision": round(classification["precision"], 4),
            "recall": round(classification["recall"], 4),
            "f1": round(classification["f1"], 4),
            "accuracy": round(classification["accuracy"], 4),
            "map": round(map_score, 4),
            "mrr": round(mrr_score, 4),
            "threshold": round(best_threshold, 2),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        }

    def _optimize_threshold(self, scores: List[Tuple[float, int]]) -> Tuple[float, float]:
        """Find optimal threshold by maximizing F1."""
        best_threshold, best_f1 = 0.5, 0.0
        for t_int in range(0, 101):
            t = t_int / 100.0
            tp = fp = tn = fn = 0
            for score, label in scores:
                pred = 1 if score >= t else 0
                if pred == 1 and label == 1:
                    tp += 1
                elif pred == 1 and label == 0:
                    fp += 1
                elif pred == 0 and label == 0:
                    tn += 1
                else:
                    fn += 1
            classification = compute_classification_metrics(tp, fp, tn, fn)
            if classification["f1"] > best_f1:
                best_f1 = classification["f1"]
                best_threshold = t
        return best_threshold, best_f1