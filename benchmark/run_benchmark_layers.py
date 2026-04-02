#!/usr/bin/env python3
"""Three-Layer Benchmark Runner.

Usage:
    python -m benchmark.run_benchmark_layers
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from benchmark.registry import registry
from benchmark.pipeline.evaluation_framework import (
    ThreeLayerBenchmarkRunner, StudentAssignment,
    RenameVariables, RestructureStatements, AddComments, AddDeadCode
)


def get_base_codes() -> List[str]:
    """Get base code templates."""
    gen = SyntheticDatasetGenerator(seed=42)
    return gen._get_default_templates("python")


def run_full_benchmark() -> Dict[str, Any]:
    """Run full three-layer benchmark for all registered engines."""
    base_codes = get_base_codes()
    engines = registry.list_engines()
    results = {}
    
    for name in engines:
        engine = registry.get_instance(name)
        runner = ThreeLayerBenchmarkRunner(engine, seed=42)
        
        try:
            result = runner.run(base_codes)
            results[name] = {
                "layer1_sensitivity": result.layer1_sensitivity,
                "layer2_precision": result.layer2_precision,
                "layer3_generalization": result.layer3_generalization,
                "overall_score": result.overall_score,
            }
            l1 = result.layer1_sensitivity
            l2 = result.layer2_precision
            print(f"✅ {name}: L1 F1={l1.get('overall_f1', 0)*100:.1f}%, "
                  f"L2 Precision={l2.get('precision', 0)*100:.1f}%, "
                  f"L3 Gen={result.layer3_generalization.get('generalization_score', 0)*100:.1f}%, "
                  f"Overall={result.overall_score*100:.1f}%")
        except Exception as e:
            print(f"❌ {name}: {str(e)[:100]}")
            results[name] = {"error": str(e)}
    
    return results


if __name__ == "__main__":
    print("="*60)
    print("THREE-LAYER AUTHORITY BENCHMARK")
    print("="*60)
    
    results = run_full_benchmark()
    
    # Save results
    output_path = Path("reports/three_layer_benchmark.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_path}")
    print("\n=== RANKING BY OVERALL SCORE ===")
    ranked = sorted(
        [(k, v.get("overall_score", 0)*100) for k, v in results.items()],
        key=lambda x: x[1], reverse=True
    )
    for i, (name, score) in enumerate(ranked):
        print(f"  {i+1}. {name}: {score:.1f}%")