"""Enhanced benchmark runner with full diagnostic intelligence.

Runs the complete diagnostic loop:
1. Generate synthetic dataset
2. Run all engines
3. Compute metrics
4. Run Error Attribution Model (EAM)
5. Run Clone-Type Sensitivity Matrix
6. Run Threshold Stability Analysis
7. Run Failure Clustering
8. Store comprehensive results

Usage:
    python -m benchmark.run_diagnostic
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator, SyntheticDataset
from benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from benchmark.analysis.error_attribution import ErrorAttributionModel
from benchmark.analysis.stability_analysis import ThresholdStabilityAnalyzer, FailureClusterAnalyzer


def _print_matrix(title: str, header: str, matrix: Dict[str, Dict[int, float]]) -> None:
    """Print a formatted matrix table."""
    clone_type_names = {1: "T1", 2: "T2", 3: "T3", 4: "T4"}
    all_types = sorted({t for types in matrix.values() for t in types})
    
    print(f"\n{title}")
    print("-" * 60)
    print(f"{'Engine':<25}", end="")
    for t in all_types:
        print(f"  {clone_type_names.get(t, f'T{t}')}", end="")
    print()
    print("-" * 60)
    
    for engine_name, type_scores in sorted(matrix.items()):
        print(f"{engine_name:<25}", end="")
        for t in all_types:
            print(f"  {type_scores.get(t, 0.0):.2f}", end="")
        print()


def run_diagnostic_benchmark(
    type1: int = 50,
    type2: int = 50,
    type3: int = 50,
    type4: int = 50,
    non_clone: int = 200,
    seed: int = 42,
    output_dir: str = "reports/diagnostics",
) -> Dict[str, Any]:
    """Run full diagnostic benchmark.
    
    Args:
        type1: Number of Type-1 pairs.
        type2: Number of Type-2 pairs.
        type3: Number of Type-3 pairs.
        type4: Number of Type-4 pairs.
        non_clone: Number of non-clone pairs.
        seed: Random seed.
        output_dir: Output directory.
        
    Returns:
        Comprehensive results dictionary.
    """
    print("=" * 70)
    print("CODEPROVENANCE DIAGNOSTIC BENCHMARK")
    print("=" * 70)
    
    # Generate dataset
    print(f"\n[1/6] Generating synthetic dataset...")
    generator = SyntheticDatasetGenerator(seed=seed)
    dataset = generator.generate_pair_count(
        type1=type1, type2=type2, type3=type3, type4=type4, non_clone=non_clone
    )
    print(f"  Stats: {dataset.stats()}")
    
    # Initialize engines
    engines = {
        "token_winnowing": TokenWinnowingEngine(),
        "ast_structural": ASTEngine(),
        "hybrid": HybridEngine(),
    }
    
    # Run EAM and clone-type sensitivity for each engine
    print(f"\n[2/6] Running Error Attribution Model (EAM)...")
    eam = ErrorAttributionModel()
    
    all_engine_results: Dict[str, Dict[str, Any]] = {}
    
    for engine_name, engine in engines.items():
        print(f"\n  --- Engine: {engine_name} ---")
        
        # EAM analysis
        eam_report = eam.analyze(dataset.pairs, engine)
        print(f"    TP={eam_report.true_positives}, FP={eam_report.false_positives}, "
              f"FN={eam_report.false_negatives}")
        print(f"    Primary causes: {eam_report.primary_cause_distribution}")
        
        # Threshold stability
        results = [
            (engine.compare(p.code_a, p.code_b), p.label, p.clone_type, p.code_a, p.code_b)
            for p in dataset.pairs
        ]
        stability = ThresholdStabilityAnalyzer(results).analyze()
        print(f"    Stability: robustness={stability.robustness_score:.3f}, "
              f"sensitivity={stability.avg_sensitivity:.3f}")
        
        # Failure clustering
        component_scores = [a.component_scores for a in eam_report.top_failures]
        cluster = FailureClusterAnalyzer(results).cluster()
        print(f"    Failure clusters: {cluster.num_clusters}")
        for surface, count in cluster.attack_surfaces.items():
            print(f"      {surface}: {count}")
        
        all_engine_results[engine_name] = {
            "eam_report": {
                "tp": eam_report.true_positives,
                "fp": eam_report.false_positives,
                "fn": eam_report.false_negatives,
                "tn": eam_report.true_negatives,
                "primary_causes": eam_report.primary_cause_distribution,
                "component_losses": eam_report.component_losses,
                "component_effectiveness": {
                    k: {"correlation": v.correlation, "discrimination": v.discrimination}
                    for k, v in eam_report.component_effectiveness.items()
                },
                "top_failures_count": len(eam_report.top_failures),
            },
            "stability": {
                "optimal_threshold": stability.optimal_threshold,
                "optimal_f1": stability.optimal_f1,
                "robustness_score": stability.robustness_score,
                "avg_sensitivity": stability.avg_sensitivity,
                "working_range_width": stability.working_range_width,
            },
            "clustering": {
                "num_clusters": cluster.num_clusters,
                "total_failures": cluster.total_failures,
                "attack_surfaces": cluster.attack_surfaces,
                "cluster_details": [
                    {
                        "id": c.cluster_id,
                        "size": c.size,
                        "avg_error": c.avg_error,
                        "pattern": c.dominant_pattern,
                        "fix": c.recommended_fix,
                    }
                    for c in cluster.clusters
                ],
            },
        }
    
    # Clone-Type Sensitivity Matrix
    print(f"\n[3/6] Computing Clone-Type Sensitivity Matrix...")
    sensitivity_matrix = eam.compute_clone_type_sensitivity(dataset.pairs, engines)
    _print_matrix("CLONE-TYPE SENSITIVITY MATRIX (Recall per Clone Type)", "T(1-4)", sensitivity_matrix)
    
    # Stability comparison
    print(f"\n[4/6] Threshold Stability Comparison...")
    print(f"{'Engine':<25} {'Robustness':>12} {'Sensitivity':>13} {'Optimal T':>11}")
    print("-" * 60)
    for engine_name, data in all_engine_results.items():
        s = data["stability"]
        print(
            f"{engine_name:<25} "
            f"{s['robustness_score']:>12.4f} "
            f"{s['avg_sensitivity']:>13.4f} "
            f"{s['optimal_threshold']:>11.2f}"
        )
    
    # Error attribution comparison
    print(f"\n[5/6] Error Attribution Comparison...")
    print(f"{'Engine':<25} {'Token Loss':>12} {'AST Loss':>10} {'Struct Loss':>12}")
    print("-" * 60)
    for engine_name, data in all_engine_results.items():
        losses = data["eam_report"].get("component_losses", {})
        print(
            f"{engine_name:<25} "
            f"{losses.get('token', 0.0):>12.4f} "
            f"{losses.get('ast', 0.0):>10.4f} "
            f"{losses.get('structure', 0.0):>12.4f}"
        )
    
    # Save comprehensive results
    print(f"\n[6/6] Saving diagnostic results...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    comprehensive = {
        "run_id": f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "dataset": {
            "name": dataset.name,
            "version": dataset.version,
            "stats": dataset.stats(),
            "seed": seed,
            "pair_config": {
                "type1": type1, "type2": type2, "type3": type3,
                "type4": type4, "non_clone": non_clone,
            },
        },
        "clone_type_sensitivity": sensitivity_matrix,
        "engines": all_engine_results,
    }
    
    report_file = output_path / f"{comprehensive['run_id']}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive, f, indent=2)
    
    print(f"  Results saved to: {report_file}")
    
    # Print top recommendations
    print(f"\n{'='*70}")
    print("TOP IMPROVEMENT RECOMMENDATIONS")
    print(f"{'='*70}")
    
    for engine_name, data in all_engine_results.items():
        causes = data["eam_report"]["primary_causes"]
        if causes:
            top_cause = max(causes, key=causes.get)
            top_count = causes[top_cause]
            print(f"\n  {engine_name}:")
            print(f"    Primary attack surface: {top_cause} ({top_count} failures)")
            
            # Find matching cluster fix
            for cluster_detail in data["clustering"]["cluster_details"]:
                if cluster_detail["fix"] and cluster_detail["size"] == top_count:
                    print(f"    Recommended fix: {cluster_detail['fix']}")
                    break
    
    print(f"\n{'='*70}")
    return comprehensive


if __name__ == "__main__":
    run_diagnostic_benchmark()