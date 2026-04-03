#!/usr/bin/env python3
"""Cross-dataset benchmark runner.

Usage:
    python -m benchmark.cross_dataset.run_cross_eval [--datasets DS1 DS2] [--tools T1 T2]

Example:
    python -m benchmark.cross_dataset.run_cross_eval --tools jaccard line_overlap
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_ROOT))


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
    args = parser.parse_args()

    from benchmark.cross_dataset.unified_format import DatasetRegistry
    from benchmark.cross_dataset.tool_adapters import JaccardToolAdapter, LineOverlapToolAdapter
    from benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator

    registry = DatasetRegistry.get_instance()
    evaluator = CrossDatasetEvaluator(registry=registry)

    external_datasets = [
        "poj104",
        "codexglue_clone",
        "codexglue_defect",
        "codesearchnet_python",
        "kaggle",
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

    if args.include_baselines:
        evaluator.register_tool("jaccard", JaccardToolAdapter())
        evaluator.register_tool("line_overlap", LineOverlapToolAdapter())

    try:
        from benchmark.cross_dataset.tool_adapters import EngineToolAdapter
        from src.engines.base_engine import BaseEngine
        from src.engines.registry import registry as engine_registry

        for engine_name in engine_registry.list_engines():
            try:
                engine = engine_registry.get(engine_name)
                if engine is not None:
                    evaluator.register_tool_from_engine(engine, name=engine_name)
            except Exception:
                pass
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

    return 0 if report.num_datasets > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
