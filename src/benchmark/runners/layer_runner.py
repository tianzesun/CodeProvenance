"""Three-layer benchmark runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from benchmark.registry import registry
from benchmark.pipeline.evaluation_framework import ThreeLayerBenchmarkRunner as ThreeLayerFramework


class ThreeLayerBenchmarkRunner:
    """Three-layer benchmark runner."""

    def __init__(self, output_dir: str = "reports/three_layer"):
        self.output_dir = output_dir

    def run(self) -> Dict[str, Any]:
        """Run full three-layer benchmark for all registered engines."""
        gen = SyntheticDatasetGenerator(seed=42)
        base_codes = gen._get_default_templates("python")
        engines = registry.list_engines()
        results = {}

        for name in engines:
            engine = registry.get_instance(name)
            runner = ThreeLayerFramework(engine, seed=42)

            try:
                result = runner.run(base_codes)
                results[name] = {
                    "layer1_sensitivity": result.layer1_sensitivity,
                    "layer2_precision": result.layer2_precision,
                    "layer3_generalization": result.layer3_generalization,
                    "overall_score": result.overall_score,
                }
            except Exception as e:
                results[name] = {"error": str(e)}

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report = {
            "run_id": f"three_layer_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "results": results,
        }

        report_file = output_path / f"{report['run_id']}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return report