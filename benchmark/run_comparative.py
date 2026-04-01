"""Comparative benchmark: Before vs After Canonicalization.

Demonstrates the impact of the canonicalization layer on Type-2 clone detection.

Usage:
    python -m benchmark.run_comparative
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from benchmark.normalization.canonicalizer import CanonicalComparePipeline, Canonicalizer
from benchmark.analysis.error_attribution import ErrorAttributionModel


def _print_table(title: str, headers: List[str], rows: List[List[str]]) -> None:
    """Print formatted table."""
    widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    
    print(f"\n{title}")
    print("-" * (sum(widths) + 3 * len(headers)))
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-" * (sum(widths) + 3 * len(headers)))
    for row in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))


def run_comparative_benchmark() -> Dict[str, Any]:
    """Run benchmark comparing before/after canonicalization.
    
    Returns:
        Comprehensive comparison results.
    """
    print("=" * 70)
    print("COMPARATIVE BENCHMARK: Before vs After Canonicalization")
    print("=" * 70)
    
    # Generate dataset
    print("\n[1/4] Generating synthetic dataset...")
    generator = SyntheticDatasetGenerator(seed=42)
    dataset = generator.generate_pair_count(
        type1=30, type2=30, type3=30, type4=30, non_clone=100
    )
    print(f"  Stats: {dataset.stats()}")
    
    # Base engines
    base_engines = {
        "token": TokenWinnowingEngine(),
        "ast": ASTEngine(),
        "hybrid": HybridEngine(),
    }
    
    # Canonicalized engines
    canonicalizer = Canonicalizer()
    canon_engines = {
        f"{name}_canon": CanonicalComparePipeline(engine, canonicalizer)
        for name, engine in base_engines.items()
    }
    
    # Combine all engines
    all_engines: Dict[str, Any] = {**base_engines, **canon_engines}
    
    # Run evaluation
    print(f"\n[2/4] Running evaluation on {len(all_engines)} engine variants...")
    results: Dict[str, Dict[str, Any]] = {}
    
    for engine_name, engine in all_engines.items():
        tp = fp = tn = fn = 0
        type_tp: Dict[int, int] = {}
        type_fn: Dict[int, int] = {}
        
        for pair in dataset.pairs:
            score = engine.compare(pair.code_a, pair.code_b)
            threshold = 0.5
            
            predicted = 1 if score >= threshold else 0
            
            if predicted == 1 and pair.label == 1:
                tp += 1
                type_tp[pair.clone_type] = type_tp.get(pair.clone_type, 0) + 1
            elif predicted == 0 and pair.label == 0:
                tn += 1
            elif predicted == 1 and pair.label == 0:
                fp += 1
            else:
                fn += 1
                type_fn[pair.clone_type] = type_fn.get(pair.clone_type, 0) + 1
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        
        # Per-type recall
        type_pairs: Dict[int, int] = {}
        for p in dataset.pairs:
            if p.label == 1:
                type_pairs[p.clone_type] = type_pairs.get(p.clone_type, 0) + 1
        
        type_recall: Dict[int, float] = {}
        for ct, total in type_pairs.items():
            ct_tp = type_tp.get(ct, 0)
            type_recall[ct] = ct_tp / total if total > 0 else 0.0
        
        results[engine_name] = {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "type_recall": {k: round(v, 4) for k, v in sorted(type_recall.items())},
            "type_tp": type_tp,
            "type_fn": type_fn,
        }
    
    # Print results
    print(f"\n[3/4] Printing comparison results...")
    
    # Overall metrics
    _print_table(
        "OVERALL METRICS",
        ["Engine", "Precision", "Recall", "F1", "FP", "FN"],
        [
            [
                name,
                f"{r['precision']:.4f}",
                f"{r['recall']:.4f}",
                f"{r['f1']:.4f}",
                str(r['fp']),
                str(r['fn']),
            ]
            for name, r in sorted(results.items())
        ]
    )
    
    # Clone-type recall matrix
    clone_names = {1: "T1", 2: "T2", 3: "T3", 4: "T4"}
    _print_table(
        "CLONE-TYPE RECALL MATRIX",
        ["Engine"] + list(clone_names.values()),
        [
            [name] + [
                f"{r['type_recall'].get(t, 0.0):.4f}"
                for t in sorted(clone_names.keys())
            ]
            for name, r in sorted(results.items())
        ]
    )
    
    # Type-2 improvement analysis
    print(f"\n[4/4] Canonicalization Impact Analysis...")
    print("-" * 60)
    
    for base_name in ["token", "ast", "hybrid"]:
        canon_name = f"{base_name}_canon"
        if base_name in results and canon_name in results:
            base_t2 = results[base_name]["type_recall"].get(2, 0.0)
            canon_t2 = results[canon_name]["type_recall"].get(2, 0.0)
            base_f1 = results[base_name]["f1"]
            canon_f1 = results[canon_name]["f1"]
            
            print(f"\n  {base_name.upper()}:")
            print(f"    Type-2 Recall: {base_t2:.4f} → {canon_t2:.4f} ({canon_t2 - base_t2:+.4f})")
            print(f"    Overall F1:    {base_f1:.4f} → {canon_f1:.4f} ({canon_f1 - base_f1:+.4f})")
            print(f"    False Negatives: {results[base_name]['fn']} → {results[canon_name]['fn']}")
    
    # Save results
    output_path = Path("reports/comparative")
    output_path.mkdir(parents=True, exist_ok=True)
    
    comprehensive = {
        "run_id": f"comparative_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "overall": results,
    }
    
    report_file = output_path / f"{comprehensive['run_id']}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive, f, indent=2)
    
    print(f"\n  Results saved to: {report_file}")
    print(f"\n{'='*70}")
    
    return comprehensive


if __name__ == "__main__":
    run_comparative_benchmark()