"""EvalForge v2 - Production-grade plagiarism detection benchmarking framework.

Usage:
    python -m evalforge.main --dataset poj104 --detectors integritydesk moss jplag
    python -m evalforge.main --config configs/experiment.yaml
"""
from __future__ import annotations
import argparse
import logging
from pathlib import Path
from datetime import datetime

from src.backend.evalforge.pipelines.runner import run_standard_benchmark, Experiment
from src.backend.evalforge.reporting.generator import generate_standard_report
from src.backend.evalforge.core.dataset import get_available_datasets


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="EvalForge v2 Benchmark Framework")
    
    parser.add_argument("--dataset", type=str, 
                       help=f"Dataset to run: {', '.join(get_available_datasets())}")
    parser.add_argument("--detectors", type=str, nargs="+",
                       help="Detectors to benchmark")
    parser.add_argument("--max-workers", type=int, default=8,
                       help="Maximum parallel workers")
    parser.add_argument("--output-dir", type=str, default="./results",
                       help="Output directory for reports")
    parser.add_argument("--transformations", type=str, nargs="+",
                       help="Transformation chains to test for robustness")
    
    args = parser.parse_args()
    
    if not args.dataset:
        parser.print_help()
        return
    
    logger.info(f"Starting EvalForge v2 benchmark for dataset: {args.dataset}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"{args.dataset}_{timestamp}"
    
    if args.transformations:
        # Run full experiment with robustness testing
        logger.info(f"Running robustness experiment with transformations: {args.transformations}")
        
        from src.backend.evalforge.detectors import get_detector
        from src.backend.evalforge.core.dataset import Dataset
        
        if args.dataset == "poj104":
            dataset = Dataset.load_poj104()
        elif args.dataset == "bigclonebench":
            dataset = Dataset.load_bigclonebench()
        else:
            raise ValueError(f"Unknown dataset: {args.dataset}")
        
        detectors = [d for d in [get_detector(name) for name in args.detectors] if d]
        
        # Parse transformation chains
        transform_chains = [t.split(",") for t in args.transformations]
        
        experiment = Experiment(
            name=f"{args.dataset}_robustness",
            dataset=dataset,
            detectors=detectors,
            transformations=transform_chains,
            max_workers=args.max_workers
        )
        
        results = experiment.run()
        
        # Save all results
        output_dir.mkdir(parents=True, exist_ok=True)
        import json
        (output_dir / "experiment_results.json").write_text(
            json.dumps({k: v for k, v in results.items() if k != "results"}, indent=2)
        )
        
        logger.info(f"Experiment complete. Results saved to: {output_dir}")
        
    else:
        # Run standard benchmark
        runner = run_standard_benchmark(args.dataset, args.detectors)
        
        # Generate reports
        generate_standard_report(runner, output_dir)


if __name__ == "__main__":
    main()