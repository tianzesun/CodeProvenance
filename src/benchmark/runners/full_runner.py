"""Full benchmark runner - combines all benchmark types."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from benchmark.runners.core_runner import CoreBenchmarkRunner
from benchmark.runners.diagnostic_runner import DiagnosticBenchmarkRunner
from benchmark.runners.comparative_runner import ComparativeBenchmarkRunner
from benchmark.runners.layer_runner import ThreeLayerBenchmarkRunner


class FullBenchmarkRunner:
    """Full benchmark runner combining all benchmark types."""

    def __init__(self, output_dir: str = "reports/full"):
        self.output_dir = output_dir

    def run(
        self,
        type1: int = 50,
        type2: int = 50,
        type3: int = 50,
        type4: int = 50,
        non_clone: int = 200,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Run full benchmark suite."""
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_results: Dict[str, Any] = {}

        # Run core benchmark
        print("\n[1/4] Running Core Benchmark...")
        core_runner = CoreBenchmarkRunner(output_dir=f"{self.output_dir}/core")
        all_results["core"] = core_runner.run(
            engine_name="all", type1=type1, type2=type2, type3=type3, type4=type4, non_clone=non_clone, seed=seed
        )

        # Run diagnostic benchmark
        print("\n[2/4] Running Diagnostic Benchmark...")
        diagnostic_runner = DiagnosticBenchmarkRunner(output_dir=f"{self.output_dir}/diagnostic")
        all_results["diagnostic"] = diagnostic_runner.run(
            type1=type1, type2=type2, type3=type3, type4=type4, non_clone=non_clone, seed=seed
        )

        # Run comparative benchmark
        print("\n[3/4] Running Comparative Benchmark...")
        comparative_runner = ComparativeBenchmarkRunner(output_dir=f"{self.output_dir}/comparative")
        all_results["comparative"] = comparative_runner.run(
            type1=type1 // 2, type2=type2 // 2, type3=type3 // 2, type4=type4 // 2, non_clone=non_clone // 2, seed=seed
        )

        # Run three-layer benchmark
        print("\n[4/4] Running Three-Layer Benchmark...")
        layer_runner = ThreeLayerBenchmarkRunner(output_dir=f"{self.output_dir}/three_layer")
        all_results["three_layer"] = layer_runner.run()

        # Save combined results
        comprehensive = {
            "run_id": f"full_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "type1": type1, "type2": type2, "type3": type3, "type4": type4,
                "non_clone": non_clone, "seed": seed,
            },
            "results": all_results,
        }

        report_file = output_path / f"{comprehensive['run_id']}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive, f, indent=2, default=str)

        print(f"\nFull benchmark results saved to: {report_file}")
        return comprehensive