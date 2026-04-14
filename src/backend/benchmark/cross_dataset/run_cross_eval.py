#!/usr/bin/env python3
"""Cross-dataset benchmark runner.

Usage:
    python -m benchmark.cross_dataset.run_cross_eval [--datasets DS1 DS2] [--tools T1 T2]

Example:
    python -m benchmark.cross_dataset.run_cross_eval --tools moss jplag dolos integritydesk
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description="Cross-dataset benchmark runner")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Dataset names to evaluate (default: all registered)",
    )
    parser.add_argument(
        "--tools",
        nargs="*",
        default=None,
        help="Tool names to evaluate (default: all registered)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Classification threshold (default: 0.5)",
    )
    parser.add_argument(
        "--optimize-threshold",
        action="store_true",
        help="Optimize threshold per tool per dataset",
    )
    parser.add_argument(
        "--threshold-strategy",
        default="f1_max",
        choices=["f1_max", "precision_max", "recall_max"],
        help="Strategy for threshold optimization",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON report path",
    )
    parser.add_argument(
        "--data-root",
        default="data/datasets",
        help="Root directory for external datasets",
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        help="Maximum pairs per dataset",
    )
    parser.add_argument(
        "--include-baselines",
        action="store_true",
        default=True,
        help="Include baseline tools (jaccard, line_overlap)",
    )
    parser.add_argument(
        "--significance",
        action="store_true",
        help="Run statistical significance tests (McNemar)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    args = parser.parse_args()

    from src.backend.benchmark.cross_dataset.dataset_registry import DatasetRegistry
    from src.backend.benchmark.cross_dataset.dataset_catalog import DatasetCatalog
    from src.backend.benchmark.cross_dataset.tool_adapters import ALL_TOOLS
    from src.backend.benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator

    DatasetCatalog.register_all()

    registry = DatasetRegistry.get_instance()
    evaluator = CrossDatasetEvaluator(registry=registry)

    external_datasets = [
        "poj104",
        "codexglue_clone",
        "codexglue_defect",
        "codesearchnet_python",
        "kaggle",
        "human_eval",
        "mbpp",
    ]
    for ds_name in external_datasets:
        try:
            registry.register_external_loader(
                name=ds_name,
                data_root=args.data_root,
                max_pairs=args.max_pairs,
            )
        except Exception:
            pass

    if args.include_baselines or not args.tools:
        for tool_name, tool_cls in ALL_TOOLS.items():
            try:
                evaluator.register_tool(tool_name, tool_cls())
            except Exception:
                pass

    if args.tools:
        for tool_name in args.tools:
            if tool_name in ALL_TOOLS:
                try:
                    evaluator.register_tool(tool_name, ALL_TOOLS[tool_name]())
                except Exception:
                    pass

    report = evaluator.run(
        dataset_names=args.datasets,
        tool_names=args.tools,
        threshold=args.threshold,
        optimize_thresholds=args.optimize_threshold,
        threshold_strategy=args.threshold_strategy,
        output_path=args.output,
        verbose=True,
    )

    if args.significance and len(report.all_results) > 1:
        sig_results = evaluator.run_significance_tests()
        if sig_results:
            print("\n--- Statistical Significance Tests (McNemar) ---")
            for s in sig_results:
                marker = " *" if s["significant"] else ""
                print(f"  {s['tool_a']} vs {s['tool_b']}: chi2={s['chi2']:.2f}, p={s['p_value']:.4f}{marker}")

    return 0 if report.num_datasets > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
