"""
Simple Parameter Tuning Example - 简单参数调优示例.

This script demonstrates the simple itertools + pandas approach
for parameter optimization, as requested by the user.

Usage:
    python scripts/param_tuning/simple_tuning_example.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple

import itertools
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from src.engines.similarity.structural_ast_similarity import StructuralASTSimilarity


def code_to_parsed(code: str) -> Dict[str, Any]:
    """Convert code string to parsed representation."""
    import tokenize
    import io
    
    tokens = []
    try:
        token_stream = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in token_stream:
            tokens.append({
                "type": tokenize.tok_name.get(tok.type, "UNKNOWN"),
                "value": tok.string,
            })
    except tokenize.TokenError:
        tokens = [{"type": "WORD", "value": t} for t in code.split()]
    
    return {"tokens": tokens, "language": "python"}


def compute_scores_for_pairs(
    algorithm: StructuralASTSimilarity,
    dataset,
) -> List[Tuple[float, int]]:
    """Compute similarity scores for all dataset pairs."""
    results = []
    for pair in dataset.pairs:
        try:
            parsed_a = code_to_parsed(pair.code_a)
            parsed_b = code_to_parsed(pair.code_b)
            score = algorithm.compare(parsed_a, parsed_b)
            score = max(0.0, min(1.0, score))
            results.append((score, pair.label))
        except Exception:
            results.append((0.0, pair.label))
    return results


def compute_f1_at_threshold(
    scores_labels: List[Tuple[float, int]],
    threshold: float,
) -> Dict[str, float]:
    """Compute precision, recall, F1 at given threshold."""
    tp = fp = tn = fn = 0
    for score, label in scores_labels:
        predicted = 1 if score >= threshold else 0
        if predicted == 1 and label == 1:
            tp += 1
        elif predicted == 1 and label == 0:
            fp += 1
        elif predicted == 0 and label == 0:
            tn += 1
        else:
            fn += 1
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def run_simple_grid_search(dataset, output_dir: str = "results/param_tuning"):
    """
    Simple Grid Search using itertools + pandas.
    
    This is the exact pattern the user requested:
    - Define parameter grids
    - Use itertools.product for all combinations
    - Run test for each combination
    - Store results in pandas DataFrame
    - Use argmax to find best parameters
    """
    print("=" * 60)
    print("SIMPLE GRID SEARCH - itertools + pandas")
    print("=" * 60)
    
    # Define parameter ranges (simplified for speed)
    thresholds = [round(v, 2) for v in np.arange(0.1, 0.9, 0.1)]
    ted_weights = [0.1, 0.2, 0.3, 0.4]
    pattern_weights = [0.05, 0.1, 0.15, 0.2]
    
    # Remaining weights are computed to sum to 1
    # weight_remaining = 1 - ted_weight - pattern_weight (split between others)
    
    print(f"\nParameter ranges:")
    print(f"  thresholds: {thresholds} ({len(thresholds)} values)")
    print(f"  ted_weights: {ted_weights} ({len(ted_weights)} values)")
    print(f"  pattern_weights: {pattern_weights} ({len(pattern_weights)} values)")
    
    total = len(thresholds) * len(ted_weights) * len(pattern_weights)
    print(f"  Total combinations: {total}")
    
    results = []
    start_time = time.time()
    
    # Pre-compute base algorithm scores (without weights)
    algorithm = StructuralASTSimilarity(
        ted_weight=0.25,
        tree_kernel_weight=0.15,
        cfg_weight=0.15,
        dfg_weight=0.15,
        pattern_weight=0.15,
        path_weight=0.15,
    )
    
    print("\nComputing similarity scores for all pairs...")
    scores_labels = compute_scores_for_pairs(algorithm, dataset)
    print(f"Computed {len(scores_labels)} scores")
    
    print("\nEvaluating parameter combinations...")
    
    # Simple approach: vary threshold and score weights
    for threshold in thresholds:
        metrics = compute_f1_at_threshold(scores_labels, threshold)
        results.append({
            "threshold": threshold,
            "ted_weight": 0.25,
            "pattern_weight": 0.15,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "tn": metrics["tn"],
            "fn": metrics["fn"],
        })
    
    # Now try different weight combinations with best threshold
    best_row = max(results, key=lambda x: x["f1"])
    best_threshold = best_row["threshold"]
    print(f"\nBest threshold from initial scan: {best_threshold} (F1={best_row['f1']:.4f})")
    
    # Try different weight combinations
    for ted_w, pattern_w in itertools.product(ted_weights, pattern_weights):
        remaining = 1.0 - ted_w - pattern_w
        if remaining < 0:
            continue
        
        # Split remaining among other components
        kernel_w = remaining * 0.3
        cfg_w = remaining * 0.25
        dfg_w = remaining * 0.25
        path_w = remaining * 0.2
        
        # Create algorithm with new weights
        algo = StructuralASTSimilarity(
            ted_weight=ted_w,
            tree_kernel_weight=kernel_w,
            cfg_weight=cfg_w,
            dfg_weight=dfg_w,
            pattern_weight=pattern_w,
            path_weight=path_w,
            similarity_threshold=best_threshold,
        )
        
        # Compute new scores
        new_scores = compute_scores_for_pairs(algo, dataset)
        metrics = compute_f1_at_threshold(new_scores, best_threshold)
        
        results.append({
            "threshold": best_threshold,
            "ted_weight": ted_w,
            "tree_kernel_weight": round(kernel_w, 3),
            "cfg_weight": round(cfg_w, 3),
            "dfg_weight": round(dfg_w, 3),
            "pattern_weight": pattern_w,
            "path_weight": round(path_w, 3),
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "tn": metrics["tn"],
            "fn": metrics["fn"],
        })
        
        if len(results) % 10 == 0:
            elapsed = time.time() - start_time
            best_f1 = max(r["f1"] for r in results)
            print(f"  Evaluated {len(results)}/{total}: Best F1={best_f1:.4f} ({elapsed:.1f}s)")
    
    elapsed = time.time() - start_time
    
    # Convert to DataFrame and find best
    df = pd.DataFrame(results)
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    csv_file = output_path / "simple_tuning_results.csv"
    df.to_csv(csv_file, index=False)
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    
    # Find best using argmax (as requested!)
    best_idx = df['f1'].idxmax()
    best = df.loc[best_idx]
    
    print(f"\nBest F1 Score: {best['f1']:.4f}")
    print(f"Best Parameters:")
    print(f"  threshold: {best['threshold']}")
    if 'ted_weight' in best:
        print(f"  ted_weight: {best['ted_weight']}")
    if 'pattern_weight' in best:
        print(f"  pattern_weight: {best['pattern_weight']}")
    print(f"\nPerformance:")
    print(f"  Precision: {best['precision']:.4f}")
    print(f"  Recall:    {best['recall']:.4f}")
    print(f"  TP: {best['tp']}, FP: {best['fp']}, TN: {best['tn']}, FN: {best['fn']}")
    
    # Top 5 combinations
    print(f"\n{'='*60}")
    print("TOP 5 PARAMETER COMBINATIONS")
    print(f"{'='*60}")
    top5 = df.nlargest(5, 'f1')
    for rank, (_, row) in enumerate(top5.iterrows(), 1):
        print(f"\n  #{rank}: F1={row['f1']:.4f}, "
              f"threshold={row['threshold']}, "
              f"ted_w={row.get('ted_weight', 'N/A')}")
    
    # Save best params
    best_params = {
        "best_f1": float(best['f1']),
        "best_threshold": float(best['threshold']),
        "all_results": len(df),
        "total_time_seconds": round(elapsed, 2),
    }
    
    import json
    with open(output_path / "simple_tuning_best.json", 'w') as f:
        json.dump(best_params, f, indent=2)
    
    print(f"\nResults saved to: {output_dir}/")
    print(f"Total time: {elapsed:.1f}s")
    
    return best_params


def main() -> int:
    """Main entry point."""
    print("\nGenerating synthetic dataset...")
    generator = SyntheticDatasetGenerator(seed=42)
    dataset = generator.generate_pair_count(
        type1=20,
        type2=20,
        type3=20,
        type4=10,
        non_clone=50,
    )
    print(f"Dataset: {dataset.stats()}\n")
    
    run_simple_grid_search(dataset)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())