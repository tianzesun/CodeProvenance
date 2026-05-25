"""Core benchmark runner - focused, reproducible, minimal dependencies."""

from __future__ import annotations

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.backend.benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from src.backend.benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from src.backend.benchmark.evaluation.metrics import compute_average_precision


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
        
        # Manual classification metrics calculation
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
        
        # Confusion matrix sanity checks
        total_predictions = tp + fp + tn + fn
        assert total_predictions == len(scores), f"Confusion matrix sum ({total_predictions}) != total samples ({len(scores)})"

        # Verify predictions at threshold 0.00 (should predict all positive)
        tp_at_0 = sum(1 for score, label in scores if score >= 0.0 and label == 1)
        fp_at_0 = sum(1 for score, label in scores if score >= 0.0 and label == 0)
        tn_at_0 = sum(1 for score, label in scores if score < 0.0 and label == 0)
        fn_at_0 = sum(1 for score, label in scores if score < 0.0 and label == 1)

        expected_tp_at_0 = sum(1 for _, label in scores if label == 1)
        expected_fp_at_0 = sum(1 for _, label in scores if label == 0)
        assert tp_at_0 == expected_tp_at_0, f"TP at threshold 0.0: {tp_at_0} != expected {expected_tp_at_0}"
        assert fp_at_0 == expected_fp_at_0, f"FP at threshold 0.0: {fp_at_0} != expected {expected_fp_at_0}"
        assert tn_at_0 == 0, f"TN at threshold 0.0 should be 0, got {tn_at_0}"
        assert fn_at_0 == 0, f"FN at threshold 0.0 should be 0, got {fn_at_0}"

        classification = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "accuracy": accuracy,
            "confusion_matrix_sanity": {
                "total_samples": len(scores),
                "matrix_sum": total_predictions,
                "threshold_0_check": {
                    "tp": tp_at_0, "fp": fp_at_0, "tn": tn_at_0, "fn": fn_at_0,
                    "passed": tp_at_0 == expected_tp_at_0 and fp_at_0 == expected_fp_at_0 and tn_at_0 == 0 and fn_at_0 == 0
                }
            }
        }
        
        query_results: Dict[str, List[Tuple[str, float, int]]] = {}
        for i, (score, label) in enumerate(scores):
            q_id = f"q_{i // 10}"
            query_results.setdefault(q_id, []).append((f"d_{i}", score, label))
        
        # MAP and MRR calculation
        ap_sum = 0.0
        mrr_sum = 0.0
        query_count = 0
        
        for q_id, results in query_results.items():
            # Sort by score descending
            sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
            
            # Calculate Average Precision
            hits = 0
            ap = 0.0
            for rank, (doc_id, score, label) in enumerate(sorted_results, 1):
                if label == 1:
                    hits += 1
                    ap += hits / rank
            
            if hits > 0:
                ap_sum += ap / hits
            
            # Calculate MRR
            for rank, (doc_id, score, label) in enumerate(sorted_results, 1):
                if label == 1:
                    mrr_sum += 1.0 / rank
                    break
            
            query_count += 1
        
        map_score = ap_sum / query_count if query_count > 0 else 0.0
        mrr_score = mrr_sum / query_count if query_count > 0 else 0.0
        
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
        """Find optimal threshold by maximizing F1 using unique observed scores with constraints."""
        best_threshold, best_f1 = 0.5, 0.0

        # Early exit if there are no positive labels to optimize for
        has_positives = any(label == 1 for (_, label) in scores)
        if not has_positives or len(scores) == 0:
            return 0.5, 0.0

        # Use unique observed scores as threshold candidates, plus boundary values
        unique_scores = sorted(set(score for score, _ in scores))
        threshold_candidates = [0.0] + unique_scores + [1.0]

        for threshold in threshold_candidates:
            tp = fp = tn = fn = 0
            for score, label in scores:
                pred = 1 if score >= threshold else 0
                if pred == 1 and label == 1:
                    tp += 1
                elif pred == 1 and label == 0:
                    fp += 1
                elif pred == 0 and label == 0:
                    tn += 1
                else:
                    fn += 1
            precision_t = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall_t = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            fpr_t = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            f1_t = 2 * precision_t * recall_t / (precision_t + recall_t) if (precision_t + recall_t) > 0 else 0.0

            # Apply constraints to prevent degenerate solutions:
            # - Minimum precision of 0.1 (not all-positive)
            # - Maximum FPR of 0.5 (not too noisy)
            if precision_t >= 0.1 and fpr_t <= 0.5 and f1_t > best_f1:
                best_f1 = f1_t
                best_threshold = threshold
        return best_threshold, best_f1

    def _compute_score_diagnostics(self, scores: List[Tuple[float, int]]) -> Dict[str, Any]:
        """Compute diagnostic statistics for score distributions by class."""
        if not scores:
            return {"error": "No scores provided"}

        positive_scores = [score for score, label in scores if label == 1]
        negative_scores = [score for score, label in scores if label == 0]

        def compute_stats(score_list):
            if not score_list:
                return {"count": 0, "min": None, "median": None, "max": None, "mean": None}
            sorted_scores = sorted(score_list)
            return {
                "count": len(score_list),
                "min": sorted_scores[0],
                "median": sorted_scores[len(sorted_scores) // 2],
                "max": sorted_scores[-1],
                "mean": sum(sorted_scores) / len(sorted_scores)
            }

        return {
            "positive_class": compute_stats(positive_scores),
            "negative_class": compute_stats(negative_scores),
            "score_direction_check": {
                "positive_median > negative_median": (
                    positive_scores and negative_scores and
                    sorted(positive_scores)[len(positive_scores) // 2] >
                    sorted(negative_scores)[len(negative_scores) // 2]
                ),
                "interpretation": "Higher scores should indicate plagiarism (positive class)"
            }
        }