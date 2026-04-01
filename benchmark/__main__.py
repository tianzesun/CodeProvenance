"""Benchmark entry point.

Usage:
    python -m benchmark run --config config/benchmark.yaml
    python -m benchmark generate --dataset synthetic --output data/synthetic_v1.json
    python -m benchmark compare --engine token_winnowing --config config/benchmark.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _load_config(config_path: str) -> Dict[str, Any]:
    """Load benchmark configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file.
        
    Returns:
        Configuration dictionary.
    """
    import yaml
    
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _load_config_json(config_path: str) -> Dict[str, Any]:
    """Load benchmark configuration from JSON file.
    
    Args:
        config_path: Path to JSON config file.
        
    Returns:
        Configuration dictionary.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _run_benchmark(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run a benchmark with the given configuration.
    
    Args:
        config: Benchmark configuration dictionary.
        
    Returns:
        Results dictionary with metrics and metadata.
    """
    from benchmark.pipeline.config import BenchmarkConfig
    from benchmark.pipeline.loader import CanonicalDataset, CodePair
    from benchmark.pipeline.runner import BenchmarkRunner
    from benchmark.registry import registry
    
    # Build BenchmarkConfig from dict
    bench_config = BenchmarkConfig.from_dict(config)
    
    # Load dataset
    dataset_config = config.get("dataset", {})
    dataset_name = dataset_config.get("name", "synthetic")
    
    if dataset_name == "synthetic":
        return _run_synthetic_benchmark(bench_config, dataset_config)
    else:
        return _run_dataset_benchmark(bench_config, dataset_config)


def _run_synthetic_benchmark(
    config: "BenchmarkConfig",
    dataset_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Run benchmark on synthetic dataset.
    
    Args:
        config: BenchmarkConfig instance.
        dataset_config: Dataset configuration from config file.
        
    Returns:
        Results dictionary.
    """
    from benchmark.datasets.synthetic_generator import (
        SyntheticDatasetGenerator,
    )
    from benchmark.pipeline.loader import CodePair, CanonicalDataset
    
    # Generate synthetic dataset
    gen_config = dataset_config.get("generator", {})
    generator = SyntheticDatasetGenerator(
        seed=gen_config.get("seed", 42),
        language=gen_config.get("language", "python"),
    )
    
    pair_counts = gen_config.get("pair_counts", {
        "type1": 50,
        "type2": 50,
        "type3": 50,
        "type4": 50,
        "non_clone": 200,
    })
    
    synthetic = generator.generate_pair_count(
        type1=pair_counts.get("type1", 50),
        type2=pair_counts.get("type2", 50),
        type3=pair_counts.get("type3", 50),
        type4=pair_counts.get("type4", 50),
        non_clone=pair_counts.get("non_clone", 200),
    )
    
    # Convert to CanonicalDataset
    pairs = [
        CodePair(
            id_a=p.id + "_a",
            code_a=p.code_a,
            id_b=p.id + "_b",
            code_b=p.code_b,
            label=p.label,
            clone_type=p.clone_type,
        )
        for p in synthetic.pairs
    ]
    dataset = CanonicalDataset(
        name=f"{synthetic.name}_v{synthetic.version}",
        version=synthetic.version,
        pairs=pairs,
    )
    
    # Run benchmark
    runner = BenchmarkRunner(seed=config.threshold.optimize and 42 or 42)
    result = runner.run(dataset, config)
    
    # Build return dict
    output = {
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "config_hash": config.config_hash(),
        "engine": config.engine.name,
        "dataset": dataset_name,
        "dataset_stats": synthetic.stats(),
        "success": result.success,
    }
    
    if result.success:
        output["metrics"] = {
            "precision": result.metrics.precision,
            "recall": result.metrics.recall,
            "f1": result.metrics.f1,
            "accuracy": result.metrics.accuracy,
            "map_score": result.metrics.map_score,
            "mrr_score": result.metrics.mrr_score,
            "threshold": result.metrics.threshold,
            "tp": result.metrics.tp,
            "fp": result.metrics.fp,
            "tn": result.metrics.tn,
            "fn": result.metrics.fn,
        }
        output["report_paths"] = result.report_paths or {}
    else:
        output["error"] = result.error
    
    return output


def _run_dataset_benchmark(
    config: "BenchmarkConfig",
    dataset_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Run benchmark on an external dataset.
    
    Args:
        config: BenchmarkConfig instance.
        dataset_config: Dataset configuration from config file.
        
    Returns:
        Results dictionary.
    """
    # TODO: Implement external dataset loading
    raise NotImplementedError(
        "External dataset benchmarking not yet implemented. "
        "Use synthetic dataset for now."
    )


def _generate_dataset(args: argparse.Namespace) -> None:
    """Generate a synthetic dataset and save it.
    
    Args:
        args: Parsed command line arguments.
    """
    from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
    
    generator = SyntheticDatasetGenerator(
        seed=args.seed if hasattr(args, 'seed') else 42,
        language=args.language if hasattr(args, 'language') else "python",
    )
    
    pair_counts = {
        "type1": args.type1 if hasattr(args, 'type1') else 50,
        "type2": args.type2 if hasattr(args, 'type2') else 50,
        "type3": args.type3 if hasattr(args, 'type3') else 50,
        "type4": args.type4 if hasattr(args, 'type4') else 50,
        "non_clone": args.non_clone if hasattr(args, 'non_clone') else 200,
    }
    
    dataset = generator.generate_pair_count(**pair_counts)
    
    output_path = args.output if hasattr(args, 'output') else "data/synthetic_v1.json"
    saved_path = dataset.save(output_path)
    
    stats = dataset.stats()
    print(f"Generated synthetic dataset: {saved_path}")
    print(f"Dataset statistics:")
    for key, count in stats.items():
        print(f"  {key}: {count}")


def _compare_single(args: argparse.Namespace) -> None:
    """Run a single code comparison.
    
    Args:
        args: Parsed command line arguments.
    """
    from benchmark.registry import registry
    
    engine = registry.get_instance(args.engine)
    with open(args.file_a, 'r', encoding='utf-8') as f:
        code_a = f.read()
    with open(args.file_b, 'r', encoding='utf-8') as f:
        code_b = f.read()
    
    score = engine.compare(code_a, code_b)
    print(f"Engine: {engine.name()}")
    print(f"Similarity: {score:.4f}")


def main() -> int:
    """Main entry point for benchmark CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="CodeProvenance Benchmark System",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a benchmark experiment")
    run_parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to benchmark config YAML file",
    )
    run_parser.add_argument(
        "--output", "-o",
        help="Path to write results JSON (default: print to stdout)",
    )
    
    # Generate command
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate a synthetic dataset",
    )
    gen_parser.add_argument(
        "--output", "-o",
        default="data/synthetic_v1.json",
        help="Output path for dataset JSON",
    )
    gen_parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility",
    )
    gen_parser.add_argument(
        "--language",
        default="python",
        help="Programming language",
    )
    gen_parser.add_argument(
        "--type1", type=int, default=50,
        help="Number of Type-1 (identical) pairs",
    )
    gen_parser.add_argument(
        "--type2", type=int, default=50,
        help="Number of Type-2 (renamed) pairs",
    )
    gen_parser.add_argument(
        "--type3", type=int, default=50,
        help="Number of Type-3 (restructured) pairs",
    )
    gen_parser.add_argument(
        "--type4", type=int, default=50,
        help="Number of Type-4 (semantic) pairs",
    )
    gen_parser.add_argument(
        "--non-clone", type=int, default=200,
        help="Number of non-clone pairs",
    )
    
    # Compare command
    cmp_parser = subparsers.add_parser(
        "compare",
        help="Compare two code files",
    )
    cmp_parser.add_argument("--engine", required=True, help="Engine name")
    cmp_parser.add_argument("--file-a", "-a", required=True, help="First code file")
    cmp_parser.add_argument("--file-b", "-b", required=True, help="Second code file")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    if args.command == "run":
        config = _load_config(args.config)
        results = _run_benchmark(config)
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"Results written to: {output_path}")
        else:
            print(json.dumps(results, indent=2))
        
        return 0 if results.get("success", False) else 1
    
    elif args.command == "generate":
        _generate_dataset(args)
        return 0
    
    elif args.command == "compare":
        _compare_single(args)
        return 0
    
    return 1


if __name__ == "__main__":
    sys.exit(main())