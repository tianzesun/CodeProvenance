"""Diagnostic benchmark runner with full diagnostic intelligence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from src.benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from src.benchmark.forensics import ErrorAttributionModel, ThresholdStabilityAnalyzer, FailureClusterAnalyzer


class DiagnosticBenchmarkRunner:
    """Full diagnostic benchmark runner."""

    def __init__(self, output_dir: str = "reports/diagnostics"):
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
        """Run full diagnostic benchmark."""
        generator = SyntheticDatasetGenerator(seed=seed)
        dataset = generator.generate_pair_count(type1, type2, type3, type4, non_clone)

        engines = {
            "token_winnowing": TokenWinnowingEngine(),
            "ast_structural": ASTEngine(),
            "hybrid": HybridEngine(),
        }

        eam = ErrorAttributionModel()
        all_engine_results: Dict[str, Dict[str, Any]] = {}

        for engine_name, engine in engines.items():
            eam_report = eam.analyze(dataset.pairs, engine)

            results = [
                (engine.compare(p.code_a, p.code_b), p.label, p.clone_type, p.code_a, p.code_b)
                for p in dataset.pairs
            ]
            stability = ThresholdStabilityAnalyzer(results).analyze()
            cluster = FailureClusterAnalyzer(results).cluster()

            all_engine_results[engine_name] = {
                "eam_report": {
                    "tp": eam_report.true_positives,
                    "fp": eam_report.false_positives,
                    "fn": eam_report.false_negatives,
                    "tn": eam_report.true_negatives,
                    "primary_causes": eam_report.primary_cause_distribution,
                    "component_losses": eam_report.component_losses,
                },
                "stability": {
                    "optimal_threshold": stability.optimal_threshold,
                    "optimal_f1": stability.optimal_f1,
                    "robustness_score": stability.robustness_score,
                    "avg_sensitivity": stability.avg_sensitivity,
                },
                "clustering": {
                    "num_clusters": cluster.num_clusters,
                    "total_failures": cluster.total_failures,
                    "attack_surfaces": cluster.attack_surfaces,
                },
            }

        sensitivity_matrix = eam.compute_clone_type_sensitivity(dataset.pairs, engines)

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        comprehensive = {
            "run_id": f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "dataset": {
                "name": dataset.name,
                "version": dataset.version,
                "stats": dataset.stats(),
                "seed": seed,
            },
            "clone_type_sensitivity": sensitivity_matrix,
            "engines": all_engine_results,
        }

        report_file = output_path / f"{comprehensive['run_id']}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive, f, indent=2)

        return comprehensive