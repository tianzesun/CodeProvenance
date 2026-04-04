#!/usr/bin/env python3
"""Run benchmark with external datasets.

Usage:
    python run_external_benchmark.py [dataset_name] [max_pairs]
    
Examples:
    python run_external_benchmark.py poj104 500
    python run_external_benchmark.py codexglue_clone 1000
    python run_external_benchmark.py codesearchnet 200
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from benchmark.pipeline.runner import BenchmarkRunner
from benchmark.pipeline.config import BenchmarkConfig


def run_benchmark(dataset_name: str, max_pairs: int = 500):
    """Run benchmark on external dataset.
    
    Args:
        dataset_name: Name of dataset (poj104, codexglue_clone, codesearchnet, kaggle)
        max_pairs: Maximum number of pairs to evaluate
    """
    print(f"\n{'='*60}")
    print(f"Running benchmark on: {dataset_name}")
    print(f"Max pairs: {max_pairs}")
    print(f"{'='*60}\n")
    
    # Load dataset directly with correct path
    print(f"[1/3] Loading dataset '{dataset_name}'...")
    try:
        from benchmark.pipeline.external_loader import ExternalDatasetLoader
        loader = ExternalDatasetLoader(data_root="data/datasets", seed=42)
        dataset = loader.load_by_name(
            name=dataset_name,
            split="test",
            max_pairs=max_pairs,
        )
        print(f"      Loaded {len(dataset.pairs)} pairs")
        
        # Debug: Show sample of loaded data
        if len(dataset.pairs) > 0:
            print(f"      Sample pair 0:")
            print(f"        ID A: {dataset.pairs[0].id_a}")
            print(f"        ID B: {dataset.pairs[0].id_b}")
            print(f"        Label: {dataset.pairs[0].label}")
            print(f"        Clone type: {dataset.pairs[0].clone_type}")
            print(f"        Code A length: {len(dataset.pairs[0].code_a)}")
            print(f"        Code B length: {len(dataset.pairs[0].code_b)}")
    except FileNotFoundError as e:
        print(f"      Error: Dataset not found - {e}")
        print(f"      Try running: bash data/datasets/download_external.sh")
        return None
    except Exception as e:
        print(f"      Error loading dataset: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Initialize runner
    runner = BenchmarkRunner(seed=42)
    
    # Configure benchmark
    print(f"[2/3] Configuring benchmark...")
    from benchmark.pipeline.config import (
        DatasetConfig, EngineConfig, NormalizerConfig, 
        ParserConfig, MetricsConfig, ThresholdConfig, OutputConfig
    )
    config = BenchmarkConfig(
        dataset=DatasetConfig(name=dataset_name, version="1.0"),
        engine=EngineConfig(name="hybrid", version="1.0"),
        normalizer=NormalizerConfig(type="moss"),
        parser=ParserConfig(type="ast", max_ast_depth=10),
        metrics=MetricsConfig(metrics=["precision", "recall", "f1"]),
        threshold=ThresholdConfig(optimize=True, strategy="f1_max"),
        output=OutputConfig(json=True, html=True),
    )
    
    # Run benchmark
    print(f"[3/3] Running benchmark...")
    try:
        result = runner.run(dataset, config)
        
        # Debug: Check if result is valid
        print(f"      Result success: {result.success}")
        print(f"      Result error: {result.error if hasattr(result, 'error') else 'None'}")
        print(f"      Metrics object: {result.metrics}")
        
        # Print results
        print(f"\n{'='*60}")
        print(f"RESULTS - {dataset_name.upper()}")
        print(f"{'='*60}")
        print(f"Precision: {result.metrics.precision:.4f}")
        print(f"Recall:    {result.metrics.recall:.4f}")
        print(f"F1 Score:  {result.metrics.f1:.4f}")
        print(f"Accuracy:  {result.metrics.accuracy:.4f}")
        print(f"TP: {result.metrics.tp}")
        print(f"FP: {result.metrics.fp}")
        print(f"TN: {result.metrics.tn}")
        print(f"FN: {result.metrics.fn}")
        print(f"{'='*60}\n")
        
        if result.report_paths:
            print(f"Reports saved to:")
            for key, path in result.report_paths.items():
                print(f"  {key}: {path}")
        
        return result
    except Exception as e:
        print(f"      Error during benchmark: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    # Parse arguments
    dataset_name = "poj104"
    max_pairs = 500
    
    if len(sys.argv) > 1:
        dataset_name = sys.argv[1]
    if len(sys.argv) > 2:
        max_pairs = int(sys.argv[2])
    
    # Available datasets
    available = [
        "poj104",
        "codexglue_clone", 
        "codexglue_defect",
        "codesearchnet",
        "codesearchnet_java",
        "kaggle",
    ]
    
    if dataset_name not in available:
        print(f"Error: Unknown dataset '{dataset_name}'")
        print(f"Available datasets: {', '.join(available)}")
        sys.exit(1)
    
    # Run benchmark
    result = run_benchmark(dataset_name, max_pairs)
    
    if result and result.success:
        print("✅ Benchmark completed successfully!")
    else:
        print("❌ Benchmark failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()