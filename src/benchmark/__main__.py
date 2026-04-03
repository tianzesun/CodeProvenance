"""Entry point for running benchmarks via `python -m benchmark`."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="CodeProvenance Benchmark System",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Benchmark command")
    
    # Core benchmark
    core_parser = subparsers.add_parser("core", help="Run core benchmark (Layer A)")
    core_parser.add_argument("--engine", choices=["token", "ast", "hybrid", "all"], default="all")
    core_parser.add_argument("--type1", type=int, default=50)
    core_parser.add_argument("--type2", type=int, default=50)
    core_parser.add_argument("--type3", type=int, default=50)
    core_parser.add_argument("--type4", type=int, default=50)
    core_parser.add_argument("--non-clone", type=int, default=200)
    core_parser.add_argument("--output", default="reports/core")
    
    # Diagnostic benchmark
    diag_parser = subparsers.add_parser("diagnostic", help="Run diagnostic benchmark")
    diag_parser.add_argument("--type1", type=int, default=50)
    diag_parser.add_argument("--type2", type=int, default=50)
    diag_parser.add_argument("--type3", type=int, default=50)
    diag_parser.add_argument("--type4", type=int, default=50)
    diag_parser.add_argument("--non-clone", type=int, default=200)
    diag_parser.add_argument("--output", default="reports/diagnostics")
    
    # Comparative benchmark
    comp_parser = subparsers.add_parser("comparative", help="Run comparative benchmark")
    comp_parser.add_argument("--type1", type=int, default=30)
    comp_parser.add_argument("--type2", type=int, default=30)
    comp_parser.add_argument("--type3", type=int, default=30)
    comp_parser.add_argument("--type4", type=int, default=30)
    comp_parser.add_argument("--non-clone", type=int, default=100)
    comp_parser.add_argument("--output", default="reports/comparative")
    
    # Three-layer benchmark
    layer_parser = subparsers.add_parser("layers", help="Run three-layer benchmark")
    layer_parser.add_argument("--output", default="reports/three_layer")
    
    # Full benchmark
    full_parser = subparsers.add_parser("full", help="Run full benchmark suite")
    full_parser.add_argument("--type1", type=int, default=50)
    full_parser.add_argument("--type2", type=int, default=50)
    full_parser.add_argument("--type3", type=int, default=50)
    full_parser.add_argument("--type4", type=int, default=50)
    full_parser.add_argument("--non-clone", type=int, default=200)
    full_parser.add_argument("--output", default="reports/full")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "core":
        from benchmark.runners.core_runner import CoreBenchmarkRunner
        runner = CoreBenchmarkRunner(output_dir=args.output)
        runner.run(
            engine_name=args.engine,
            type1=args.type1, type2=args.type2, type3=args.type3, type4=args.type4,
            non_clone=args.non_clone,
        )
    
    elif args.command == "diagnostic":
        from benchmark.runners.diagnostic_runner import DiagnosticBenchmarkRunner
        runner = DiagnosticBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1, type2=args.type2, type3=args.type3, type4=args.type4,
            non_clone=args.non_clone,
        )
    
    elif args.command == "comparative":
        from benchmark.runners.comparative_runner import ComparativeBenchmarkRunner
        runner = ComparativeBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1, type2=args.type2, type3=args.type3, type4=args.type4,
            non_clone=args.non_clone,
        )
    
    elif args.command == "layers":
        from benchmark.runners.layer_runner import ThreeLayerBenchmarkRunner
        runner = ThreeLayerBenchmarkRunner(output_dir=args.output)
        runner.run()
    
    elif args.command == "full":
        from benchmark.runners.full_runner import FullBenchmarkRunner
        runner = FullBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1, type2=args.type2, type3=args.type3, type4=args.type4,
            non_clone=args.non_clone,
        )
    
    return 0


if __name__ == "__main__":
    sys.exit(main())