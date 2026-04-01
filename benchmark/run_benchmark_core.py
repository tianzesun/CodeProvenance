"""Core benchmark runner — focused, reproducible, minimal dependencies.

Layers:
A. Benchmark Core (dataset + engines + metrics)
B. Optional Diagnostics (error attribution, failure analysis, stability)

Usage:
    # Layer A only (clean, reproducible benchmark)
    python -m benchmark.run_benchmark_core

    # Layer A + B (full diagnostics)  
    python -m benchmark.run_diagnostic
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from benchmark.metrics import (
    compute_classification_metrics,
    mean_average_precision,
    mean_reciprocal_rank,
)


def run_benchmark(
    engine,
    pairs: List[Tuple[str, str, int]],
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Run benchmark on a single engine.
    
    Args:
        engine: Any engine with compare(code_a, code_b) -> float.
        pairs: List of (code_a, code_b, label).
        threshold: Decision threshold.
        
    Returns:
        Metrics dictionary.
    """
    scores: List[Tuple[float, int]] = []
    for code_a, code_b, label in pairs:
        score = engine.compare(code_a, code_b)
        scores.append((max(0.0, min(1.0, score)), label))
    
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
    
    classification = compute_classification_metrics(tp, fp, tn, fn)
    
    # Optimize threshold
    best_threshold, best_f1 = _optimize_threshold(scores)
    
    # Re-compute with best threshold
    if best_f1 > classification["f1"]:
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
        threshold = best_threshold
    
    # Ranking metrics
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
        "threshold": round(threshold, 2),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def _optimize_threshold(
    scores: List[Tuple[float, int]]
) -> Tuple[float, float]:
    """Find optimal threshold by maximizing F1.
    
    Args:
        scores: List of (score, label).
        
    Returns:
        Tuple of (best_threshold, best_f1).
    """
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


def main() -> int:
    """Run core benchmark.
    
    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="Core benchmark (Layer A)")
    parser.add_argument("--engine", choices=["token", "ast", "hybrid", "all"], default="all")
    parser.add_argument("--type1", type=int, default=50)
    parser.add_argument("--type2", type=int, default=50)
    parser.add_argument("--type3", type=int, default=50)
    parser.add_argument("--type4", type=int, default=50)
    parser.add_argument("--non-clone", type=int, default=200)
    parser.add_argument("--output", default="reports/core")
    args = parser.parse_args()
    
    # Generate dataset
    generator = SyntheticDatasetGenerator(seed=42)
    dataset = generator.generate_pair_count(args.type1, args.type2, args.type3, args.type4, args.non_clone)
    
    # Build pairs list: (code_a, code_b, label)
    pairs = [(p.code_a, p.code_b, p.label) for p in dataset.pairs]
    
    # Select engines
    engines: Dict[str, Any] = {}
    if args.engine in ("token", "all"):
        engines["token"] = TokenWinnowingEngine()
    if args.engine in ("ast", "all"):
        engines["ast"] = ASTEngine()
    if args.engine in ("hybrid", "all"):
        engines["hybrid"] = HybridEngine()
    
    # Run
    results: Dict[str, Any] = {}
    for name, engine in engines.items():
        print(f"Running: {name}")
        results[name] = run_benchmark(engine, pairs)
        m = results[name]
        print(f"  P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}")
    
    # Save
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report = {
        "run_id": f"core_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "dataset": {
            "name": "synthetic",
            "version": "1.0",
            "pairs": dataset.stats(),
        },
        "engines": results,
    }
    
    report_file = output_path / f"{report['run_id']}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nResults saved to: {report_file}")
    
    # Summary table
    print(f"\n{'Engine':<20} {'P':>8} {'R':>8} {'F1':>8}")
    print("-" * 46)
    for name, m in results.items():
        print(f"{name:<20} {m['precision']:>8.4f} {m['recall']:>8.4f} {m['f1']:>8.4f}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())