"""End-to-end benchmark runner script.

This script runs the complete benchmark loop:
1. Generate synthetic dataset (ground truth)
2. Run all engines on the dataset
3. Compute metrics (precision, recall, F1, MAP, MRR)
4. Store results in reports/
5. Run failure analysis
6. Print summary

Usage:
    python -m benchmark.run_benchmark
    python -m benchmark.run_benchmark --engine hybrid --output results/run_001.json
    python -m benchmark.run_benchmark --all-engines --output-dir results/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets.synthetic_generator import (
    SyntheticDatasetGenerator,
    SyntheticDataset,
)
from benchmark.similarity import BaseSimilarityEngine
from benchmark.similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)
from benchmark.analysis.failure_analysis import FailureAnalyzer, failure_to_improvement_map


@dataclass
class RunResult:
    """Result of a single benchmark run."""
    run_id: str
    timestamp: str
    engine_name: str
    engine_version: str
    dataset_name: str
    dataset_version: str
    dataset_stats: Dict[str, int]
    threshold: float
    metrics: Dict[str, float]
    failure_analysis: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    improvement_targets: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "engine": {
                "name": self.engine_name,
                "version": self.engine_version,
            },
            "dataset": {
                "name": self.dataset_name,
                "version": self.dataset_version,
                "stats": self.dataset_stats,
            },
            "threshold": self.threshold,
            "metrics": self.metrics,
            "failure_analysis": self.failure_analysis,
            "recommendations": self.recommendations,
            "improvement_targets": self.improvement_targets,
        }


def _collect_results(
    engine: BaseSimilarityEngine,
    dataset: SyntheticDataset,
    threshold: float = 0.5,
) -> Tuple[List[Tuple[float, int, int, str, str]], float]:
    """Run engine on all dataset pairs, collect results.
    
    Args:
        engine: Similarity engine instance.
        dataset: Synthetic dataset with ground truth.
        threshold: Optional pre-computed threshold.
        
    Returns:
        Tuple of (results, optimized_threshold).
    """
    results: List[Tuple[float, int, int, str, str]] = []
    scores_by_label: Dict[int, List[float]] = {0: [], 1: []}
    
    for pair in dataset.pairs:
        score = engine.compare(pair.code_a, pair.code_b)
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        results.append((score, pair.label, pair.clone_type, pair.code_a, pair.code_b))
        scores_by_label[pair.label].append(score)
    
    # Optimize threshold if not provided
    if threshold is None:
        best_threshold = _optimize_threshold(results)
    else:
        best_threshold = threshold
    
    return results, best_threshold


def _optimize_threshold(results: List[Tuple[float, int, int, str, str]]) -> float:
    """Find optimal threshold by maximizing F1.
    
    Args:
        results: List of (score, label, clone_type, code_a, code_b).
        
    Returns:
        Optimal threshold value.
    """
    best_threshold = 0.5
    best_f1 = 0.0
    
    for t_int in range(0, 101):
        t = t_int / 100.0
        tp = fp = tn = fn = 0
        
        for score, label, _, _, _ in results:
            predicted = 1 if score >= t else 0
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 0:
                tn += 1
            else:
                fn += 1
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
    
    return best_threshold


def _run_single_engine(
    engine: BaseSimilarityEngine,
    dataset: SyntheticDataset,
    output_dir: str = "reports",
) -> RunResult:
    """Run a single engine benchmark with failure analysis.
    
    Args:
        engine: Similarity engine instance.
        dataset: Synthetic dataset.
        output_dir: Directory to store results.
        
    Returns:
        RunResult with metrics and analysis.
    """
    print(f"\n{'='*60}")
    print(f"Running engine: {engine.name}")
    print(f"{'='*60}")
    
    # Step 1: Collect raw results
    print("  [1/4] Computing similarity scores...")
    results, threshold = _collect_results(engine, dataset)
    print(f"  Optimized threshold: {threshold:.2f}")
    
    # Step 2: Compute metrics
    print("  [2/4] Computing metrics...")
    tp = fp = tn = fn = 0
    for score, label, _, _, _ in results:
        predicted = 1 if score >= threshold else 0
        if predicted == 1 and label == 1:
            tp += 1
        elif predicted == 1 and label == 0:
            fp += 1
        elif predicted == 0 and label == 0:
            tn += 1
        else:
            fn += 1
    
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    
    # Compute MAP and MRR
    query_results: Dict[str, List[Tuple[str, float, int]]] = {}
    for i, (score, label, clone_type, _, _) in enumerate(results):
        pair = dataset.pairs[i]
        query_id = f"query_{i // 10}"  # Group pairs into queries
        if query_id not in query_results:
            query_results[query_id] = []
        query_results[query_id].append((f"doc_{i}", score, label))
    
    map_score = _compute_map(query_results)
    mrr_score = _compute_mrr(query_results)
    
    metrics = {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "accuracy": round(acc, 4),
        "map_score": round(map_score, 4),
        "mrr_score": round(mrr_score, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }
    
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall:    {rec:.4f}")
    print(f"  F1:        {f1:.4f}")
    print(f"  Accuracy:  {acc:.4f}")
    print(f"  MAP:       {map_score:.4f}")
    print(f"  MRR:       {mrr_score:.4f}")
    
    # Step 3: Failure analysis
    print("  [3/4] Running failure analysis...")
    analyzer = FailureAnalyzer()
    failure_report = analyzer.analyze(
        engine_name=engine.name,
        dataset_name=f"{dataset.name}_v{dataset.version}",
        results=results,
        threshold=threshold,
    )
    
    recommendations = failure_report.recommendations
    improvement_targets = failure_to_improvement_map(failure_report)
    
    # Step 4: Save results
    print("  [4/4] Saving results...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_result = RunResult(
        run_id=run_id,
        timestamp=datetime.now().isoformat(),
        engine_name=engine.name,
        engine_version="1.0",
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        dataset_stats=dataset.stats(),
        threshold=threshold,
        metrics=metrics,
        failure_analysis={
            "false_positives": fp,
            "false_negatives": fn,
            "by_clone_type": {
                name: {"count": cat.count, "avg_score": cat.avg_score}
                for name, cat in failure_report.failures_by_type.items()
            },
            "by_characteristic": {
                name: {"count": cat.count, "avg_score": cat.avg_score}
                for name, cat in failure_report.failures_by_characteristic.items()
            },
        },
        recommendations=recommendations,
        improvement_targets=improvement_targets,
    )
    
    report_file = output_path / f"{run_id}_{engine.name}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(run_result.to_dict(), f, indent=2)
    
    print(f"  Report saved to: {report_file}")
    print(f"\n  Failure Analysis Summary:")
    if fp > 0:
        print(f"    False Positives: {fp}")
    if fn > 0:
        print(f"    False Negatives: {fn}")
    if recommendations:
        for rec in recommendations[:3]:
            print(f"    - {rec}")
    
    return run_result


def _compute_map(query_results: Dict[str, List[Tuple[str, float, int]]]) -> float:
    """Compute Mean Average Precision.
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        
    Returns:
        MAP score.
    """
    if not query_results:
        return 0.0
    
    aps = []
    for query_id, doc_list in query_results.items():
        sorted_docs = sorted(doc_list, key=lambda x: x[1], reverse=True)
        relevant_count = 0
        precision_sum = 0.0
        
        for i, (_, _, relevance) in enumerate(sorted_docs):
            if relevance == 1:
                relevant_count += 1
                precision_sum += relevant_count / (i + 1)
        
        total_relevant = sum(1 for _, _, r in sorted_docs if r == 1)
        ap = precision_sum / total_relevant if total_relevant > 0 else 0.0
        aps.append(ap)
    
    return sum(aps) / len(aps) if aps else 0.0


def _compute_mrr(query_results: Dict[str, List[Tuple[str, float, int]]]) -> float:
    """Compute Mean Reciprocal Rank.
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        
    Returns:
        MRR score.
    """
    if not query_results:
        return 0.0
    
    rrs = []
    for query_id, doc_list in query_results.items():
        sorted_docs = sorted(doc_list, key=lambda x: x[1], reverse=True)
        for i, (_, _, relevance) in enumerate(sorted_docs):
            if relevance == 1:
                rrs.append(1.0 / (i + 1))
                break
        else:
            rrs.append(0.0)
    
    return sum(rrs) / len(rrs) if rrs else 0.0


def main() -> int:
    """Main entry point for benchmark runner.
    
    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        description="Run CodeProvenance Benchmark",
    )
    parser.add_argument(
        "--engine",
        choices=["token", "ast", "hybrid", "all"],
        default="all",
        help="Which engine(s) to run (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/benchmarks",
        help="Output directory for results (default: reports/benchmarks)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for dataset generation",
    )
    parser.add_argument(
        "--type1", type=int, default=50,
        help="Number of Type-1 pairs",
    )
    parser.add_argument(
        "--type2", type=int, default=50,
        help="Number of Type-2 pairs",
    )
    parser.add_argument(
        "--type3", type=int, default=50,
        help="Number of Type-3 pairs",
    )
    parser.add_argument(
        "--type4", type=int, default=50,
        help="Number of Type-4 pairs",
    )
    parser.add_argument(
        "--non-clone", type=int, default=200,
        help="Number of non-clone pairs",
    )
    
    args = parser.parse_args()
    
    # Step 1: Generate synthetic dataset
    print("="*60)
    print("CODEPROVENANCE BENCHMARK SYSTEM")
    print("="*60)
    print(f"\n[Step 1/3] Generating synthetic dataset...")
    print(f"  Type-1 (identical):     {args.type1}")
    print(f"  Type-2 (renamed):       {args.type2}")
    print(f"  Type-3 (restructured):  {args.type3}")
    print(f"  Type-4 (semantic):      {args.type4}")
    print(f"  Non-clone:              {args.non_clone}")
    
    generator = SyntheticDatasetGenerator(seed=args.seed)
    dataset = generator.generate_pair_count(
        type1=args.type1,
        type2=args.type2,
        type3=args.type3,
        type4=args.type4,
        non_clone=args.non_clone,
    )
    print(f"\n  Dataset stats: {dataset.stats()}")
    
    # Step 2: Select engines
    engines: List[BaseSimilarityEngine] = []
    if args.engine in ("token", "all"):
        engines.append(TokenWinnowingEngine())
    if args.engine in ("ast", "all"):
        engines.append(ASTEngine())
    if args.engine in ("hybrid", "all"):
        engines.append(HybridEngine())
    
    print(f"\n[Step 2/3] Running {len(engines)} engine(s)")
    for eng in engines:
        print(f"  - {eng.name}")
    
    # Step 3: Run benchmarks
    print(f"\n[Step 3/3] Running benchmarks...")
    all_results: List[RunResult] = []
    
    for eng in engines:
        result = _run_single_engine(eng, dataset, args.output_dir)
        all_results.append(result)
    
    # Summary
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"{'Engine':<25} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"{'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    
    for r in all_results:
        m = r.metrics
        print(
            f"{r.engine_name:<25} "
            f"{m['precision']:>10.4f} "
            f"{m['recall']:>10.4f} "
            f"{m['f1']:>10.4f}"
        )
    
    print(f"\nResults saved to: {args.output_dir}/")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())