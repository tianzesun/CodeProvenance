"""Entry point for running benchmarks via ``python -m src.backend.benchmark``."""

from __future__ import annotations

import argparse
import logging
import sys
import time

logger = logging.getLogger(__name__)


def _artifact_sha256() -> str | None:
    """Return the shipped learned-fusion artifact hash, or None when absent."""
    import hashlib

    from src.backend.engines.scoring.learned_fusion import ARTIFACT_NAME, MODELS_DIR

    path = MODELS_DIR / ARTIFACT_NAME
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="CodeProvenance Benchmark System",
    )

    subparsers = parser.add_subparsers(dest="command", help="Benchmark command")

    # Core benchmark
    core_parser = subparsers.add_parser("core", help="Run core benchmark (Layer A)")
    core_parser.add_argument(
        "--engine", choices=["token", "ast", "hybrid", "all"], default="all"
    )
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

    # Competitor benchmark (head-to-head vs MOSS, JPlag, Dolos, etc.)
    comp_vs_parser = subparsers.add_parser(
        "competitor",
        help="Run head-to-head benchmark vs MOSS, JPlag, Dolos, Copyleaks, Turnitin",
    )
    comp_vs_parser.add_argument("--type1", type=int, default=50)
    comp_vs_parser.add_argument("--type2", type=int, default=50)
    comp_vs_parser.add_argument("--type3", type=int, default=50)
    comp_vs_parser.add_argument("--type4", type=int, default=50)
    comp_vs_parser.add_argument("--negative", type=int, default=200)
    comp_vs_parser.add_argument(
        "--bootstrap", type=int, default=1000, help="Bootstrap samples for CIs"
    )
    comp_vs_parser.add_argument(
        "--threshold", type=float, default=0.50, help="Classification threshold"
    )
    comp_vs_parser.add_argument("--seed", type=int, default=42)
    comp_vs_parser.add_argument("--output", default="reports/competitor")
    comp_vs_parser.add_argument(
        "--format",
        choices=["all", "json", "markdown", "html"],
        default="all",
        help="Report output format",
    )

    # Full benchmark
    full_parser = subparsers.add_parser("full", help="Run full benchmark suite")
    full_parser.add_argument("--type1", type=int, default=50)
    full_parser.add_argument("--type2", type=int, default=50)
    full_parser.add_argument("--type3", type=int, default=50)
    full_parser.add_argument("--type4", type=int, default=50)
    full_parser.add_argument("--non-clone", type=int, default=200)
    full_parser.add_argument("--output", default="reports/full")

    # PAN benchmark
    pan_parser = subparsers.add_parser(
        "pan", help="Run PAN plagiarism detection benchmark"
    )
    pan_parser.add_argument(
        "--tools", nargs="+", help="Specific tools to run (default: all)"
    )
    pan_parser.add_argument(
        "--datasets",
        nargs="+",
        help="Specific datasets to run (default: all supported datasets)",
    )
    pan_parser.add_argument("--dataset-path", help="Path for custom dataset")
    pan_parser.add_argument(
        "--threshold", type=float, default=0.5, help="Similarity threshold"
    )
    pan_parser.add_argument(
        "--micro-average",
        action="store_true",
        help="Use micro averaging instead of macro",
    )
    pan_parser.add_argument(
        "--output", default="reports/pan_benchmark", help="Output directory"
    )
    pan_parser.add_argument(
        "--format",
        choices=["all", "json", "markdown"],
        default="all",
        help="Report output format",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run the production plagiarism benchmark end-to-end",
    )
    run_parser.add_argument(
        "--tools", nargs="+", help="Specific tools to run (default: all)"
    )
    run_parser.add_argument(
        "--datasets",
        nargs="+",
        help="Specific datasets to run (default: all supported datasets)",
    )
    run_parser.add_argument(
        "--output", default="reports/pan_benchmark", help="Output directory"
    )
    run_parser.add_argument(
        "--threshold", type=float, default=0.5, help="Similarity threshold"
    )
    run_parser.add_argument(
        "--micro-average",
        action="store_true",
        help="Use micro averaging instead of macro averaging",
    )
    run_parser.add_argument("--dataset-path", help="Path for a custom dataset")
    run_parser.add_argument(
        "--format",
        choices=["all", "json", "markdown"],
        default="all",
        help="Report output format",
    )

    fusion_parser = subparsers.add_parser(
        "fusion-optimize",
        help="Run validation-set fusion optimization on PROGpedia",
    )
    fusion_parser.add_argument(
        "--dataset-root",
        default="data/datasets/progpedia",
        help="Path to the PROGpedia dataset root",
    )
    fusion_parser.add_argument(
        "--verdicts",
        nargs="+",
        default=["ACCEPTED"],
        help="Submission verdict folders to include",
    )
    fusion_parser.add_argument(
        "--trials",
        type=int,
        default=80,
        help="Optimization trials for Optuna or fallback random search",
    )
    fusion_parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.02,
        help="Threshold sweep step size",
    )
    fusion_parser.add_argument(
        "--max-submissions",
        type=int,
        default=4,
        help="Maximum submissions per problem/language group",
    )
    fusion_parser.add_argument(
        "--max-positive-pairs",
        type=int,
        default=6,
        help="Maximum positive pairs per problem/language group",
    )
    fusion_parser.add_argument(
        "--negative-ratio",
        type=float,
        default=1.0,
        help="Negative-to-positive ratio",
    )
    fusion_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    fusion_parser.add_argument(
        "--output",
        default="reports/fusion_optimization",
        help="Output directory",
    )

    fusion_train_parser = subparsers.add_parser(
        "fusion-train",
        help="Train and evaluate supervised fusion models on local datasets",
    )
    fusion_train_parser.add_argument(
        "--train-datasets",
        nargs="+",
        default=["conplag", "codexglue_clone"],
        help="Datasets to use for training",
    )
    fusion_train_parser.add_argument(
        "--eval-datasets",
        nargs="+",
        default=["IR-Plag-Dataset", "conplag_classroom_java"],
        help="Datasets to use for evaluation",
    )
    fusion_train_parser.add_argument(
        "--dataset-roots",
        nargs="+",
        help="Optional dataset root directories to search before built-in defaults",
    )

    weight_tune_parser = subparsers.add_parser(
        "weight-tune",
        help="Run the DOCX weight tuning plan on a scored pair export",
    )
    weight_tune_parser.add_argument(
        "--input",
        required=True,
        help="JSON or CSV scored pairs with label plus ast/fingerprint/embedding/execution/ngram scores",
    )
    weight_tune_parser.add_argument(
        "--output",
        default="results/weight_tuning",
        help="Output directory for plan artifacts",
    )
    weight_tune_parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Locked train split ratio",
    )
    weight_tune_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    weight_tune_parser.add_argument(
        "--threshold",
        type=float,
        default=0.50,
        help="Initial decision threshold used for baseline, solo, and weight search",
    )
    weight_tune_parser.add_argument(
        "--grid-step",
        type=float,
        default=0.05,
        help="Grid-search step for normalized weights",
    )
    weight_tune_parser.add_argument(
        "--fpr-limit",
        type=float,
        default=0.03,
        help="False-positive-rate limit used by the precision-sensitive objective",
    )
    weight_tune_parser.add_argument(
        "--max-grid-runs",
        type=int,
        help="Optional cap for smoke tests or quick exploratory runs",
    )
    fusion_train_parser.add_argument(
        "--train-pairs",
        type=int,
        help="Optional cap for total training pairs",
    )
    fusion_train_parser.add_argument(
        "--eval-pairs",
        type=int,
        help="Optional cap for total evaluation pairs",
    )
    fusion_train_parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.02,
        help="Threshold sweep step size",
    )
    fusion_train_parser.add_argument(
        "--optuna-trials",
        type=int,
        default=40,
        help="Optuna tuning trials for the tuned Random Forest model",
    )
    fusion_train_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    fusion_train_parser.add_argument(
        "--output",
        default="reports/fusion_training",
        help="Output directory",
    )

    engine_eval_parser = subparsers.add_parser(
        "engine-eval",
        help=(
            "Score all IntegrityDesk engines plus real MOSS/JPlag/Dolos on the "
            "same labeled pairs (IR-Plag, conplag or kaggle_student_code)"
        ),
    )
    engine_eval_parser.add_argument(
        "--dataset",
        choices=["IR-Plag-Dataset", "conplag", "kaggle_student_code"],
        default="IR-Plag-Dataset",
        help=(
            "Corpus to evaluate (default: IR-Plag-Dataset). Pairs and labels "
            "come from the same loaders as fusion-train-learned."
        ),
    )
    engine_eval_parser.add_argument(
        "--dataset-roots",
        nargs="+",
        help="Directories searched for the corpus folders (default: data/datasets)",
    )
    engine_eval_parser.add_argument(
        "--external-batch-size",
        type=int,
        default=80,
        help=(
            "Pairs per external-tool invocation (default: 80). JPlag/Dolos are "
            "quadratic in submissions, so large sets are scored in batches."
        ),
    )
    engine_eval_parser.add_argument(
        "--dataset-root",
        help="Path to the IR-Plag dataset root (default: data/datasets/IR-Plag-Dataset)",
    )
    engine_eval_parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.02,
        help="Threshold sweep step size",
    )
    engine_eval_parser.add_argument(
        "--moss-user-id",
        help="Stanford MOSS user id (required to run real MOSS jobs)",
    )
    engine_eval_parser.add_argument(
        "--tools",
        nargs="+",
        choices=["moss", "jplag", "dolos"],
        default=None,
        help="External tools to attempt (default: all available)",
    )
    engine_eval_parser.add_argument(
        "--pair-limit",
        type=int,
        help="Optional cap on labeled pairs scored (for quick verification runs)",
    )
    engine_eval_parser.add_argument(
        "--output",
        default="reports/engine_evaluation",
        help="Output directory",
    )
    engine_eval_parser.add_argument(
        "--no-prewarm-embeddings",
        action="store_true",
        help=(
            "Skip the one-pass encode of distinct submissions before pairwise "
            "scoring. Only useful to reproduce an old timing; on a GPU the "
            "prewarm is what keeps the device busy"
        ),
    )

    learned_train_parser = subparsers.add_parser(
        "fusion-train-learned",
        help=(
            "Train the production learned-fusion scoring model on combined "
            "labeled datasets and save the JSON artifact consumed by "
            "BatchDetectionService"
        ),
    )
    learned_train_parser.add_argument(
        "--datasets",
        nargs="+",
        default=["IR-Plag-Dataset", "conplag"],
        help=(
            "Labeled datasets to train on (supported: IR-Plag-Dataset, "
            "conplag, kaggle_student_code, poolc_600k_python)"
        ),
    )
    learned_train_parser.add_argument(
        "--dataset-roots",
        nargs="+",
        default=None,
        help=(
            "Directories holding the corpora; defaults to <repo>/data/datasets "
            "and <repo>/data/bigger_datasets. The corpora are gitignored, so "
            "point this at whichever checkout actually has them (e.g. the main "
            "checkout, while running the code from elsewhere)"
        ),
    )
    learned_train_parser.add_argument(
        "--artifact",
        help="Optional output path for the trained JSON artifact",
    )
    learned_train_parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        help=(
            "Per-dataset cap on loaded pairs (balanced across classes). PoolC "
            "alone holds ~600k pairs, so extraction is unbounded without it; "
            "PoolC defaults to 20000 when this is omitted."
        ),
    )
    learned_train_parser.add_argument(
        "--cv-folds",
        type=int,
        default=0,
        help=(
            "Grouped k-fold cross-validation count. 0 keeps "
            "leave-one-group-out, which is only affordable for few groups."
        ),
    )
    learned_train_parser.add_argument(
        "--poolc-negative-ratio",
        type=float,
        default=0.0,
        help=(
            "Admit at most ratio*positives PoolC cross-problem pairs. Those "
            "negatives are different problems, not independent solutions of "
            "the same assignment, so 0 (positives only) is the default."
        ),
    )
    learned_train_parser.add_argument(
        "--cache",
        help="JSONL feature cache path; makes a long extraction resumable",
    )
    learned_train_parser.add_argument(
        "--dataset-weighting",
        choices=("proportional", "equal"),
        default="proportional",
        help=(
            "How much each corpus contributes to the fit. 'equal' gives every "
            "corpus the same total weight, which keeps the small "
            "product-realistic corpora relevant next to a large sample"
        ),
    )
    learned_train_parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.02,
        help="Threshold sweep step size",
    )
    learned_train_parser.add_argument(
        "--seed", type=int, default=42, help="Random seed"
    )
    learned_train_parser.add_argument(
        "--output",
        default="reports/learned_fusion",
        help="Output directory for training reports",
    )
    learned_train_parser.add_argument(
        "--no-prewarm-embeddings",
        action="store_true",
        help=(
            "Skip the one-pass encode of distinct submissions before pairwise "
            "scoring. Pairwise calls hand the model two texts at a time, so "
            "this is what leaves a GPU idle; only use it to reproduce old timings"
        ),
    )

    cache_parser = subparsers.add_parser(
        "feature-cache-check",
        help=(
            "Re-extract a sample of cached feature rows and compare them with "
            "the cache; exits non-zero when the cache is stale"
        ),
    )
    cache_parser.add_argument(
        "--cache",
        required=True,
        help="JSONL feature cache written by fusion-train-learned --cache",
    )
    cache_parser.add_argument(
        "--datasets",
        nargs="+",
        default=["IR-Plag-Dataset", "conplag"],
        help="Datasets whose cached rows should be sampled",
    )
    cache_parser.add_argument(
        "--dataset-roots",
        nargs="+",
        default=None,
        help="Directories holding the corpora (default: data/datasets and data/bigger_datasets)",
    )
    cache_parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="How many cached rows to re-extract (default: 5)",
    )
    cache_parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Largest per-value difference still considered equal (default: 1e-6)",
    )
    cache_parser.add_argument(
        "--seed", type=int, default=0, help="Sampling seed (default: 0)"
    )
    cache_parser.add_argument(
        "--output",
        help="Optional path for a JSON copy of the check report",
    )

    gate_parser = subparsers.add_parser(
        "fusion-gate",
        help=(
            "Compare a retrain or engine-eval report against the shipped "
            "artifact per corpus; exits non-zero when any corpus regresses"
        ),
    )
    gate_parser.add_argument(
        "--report",
        nargs="+",
        required=True,
        help=(
            "Report file(s) or directory(ies). Training reports carry every "
            "corpus; engine-eval writes one file per corpus and the newest wins"
        ),
    )
    gate_parser.add_argument(
        "--scorer",
        default="fused",
        help="Scorer to read from engine-eval reports (default: fused)",
    )
    gate_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="Allowed AUC shortfall per corpus (default: 0.0, no regression)",
    )
    gate_parser.add_argument(
        "--baseline",
        nargs="+",
        metavar="DATASET=AUC",
        help=(
            "Override the shipped-artifact bar, e.g. "
            "--baseline IR-Plag-Dataset=0.6184 conplag=0.8134 "
            "kaggle_student_code=0.8833"
        ),
    )
    gate_parser.add_argument(
        "--baseline-report",
        nargs="+",
        metavar="PATH",
        help=(
            "engine-eval report(s) or directory(ies) that measured the SHIPPED "
            "artifact on this host. Their fused AUC replaces the built-in bar, "
            "which was measured on another machine and corpus copy"
        ),
    )
    gate_parser.add_argument(
        "--allow-stale-baseline",
        action="store_true",
        help=(
            "judge against a host baseline that was measured with a different "
            "shipped artifact instead of stopping; the numbers then belong to the "
            "old artifact"
        ),
    )
    gate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the verdict as JSON instead of a table",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "core":
        from src.backend.benchmark.runners.core_runner import CoreBenchmarkRunner

        runner = CoreBenchmarkRunner(output_dir=args.output)
        runner.run(
            engine_name=args.engine,
            type1=args.type1,
            type2=args.type2,
            type3=args.type3,
            type4=args.type4,
            non_clone=args.non_clone,
        )

    elif args.command == "diagnostic":
        from src.backend.benchmark.runners.diagnostic_runner import (
            DiagnosticBenchmarkRunner,
        )

        runner = DiagnosticBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1,
            type2=args.type2,
            type3=args.type3,
            type4=args.type4,
            non_clone=args.non_clone,
        )

    elif args.command == "comparative":
        from src.backend.benchmark.runners.comparative_runner import (
            ComparativeBenchmarkRunner,
        )

        runner = ComparativeBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1,
            type2=args.type2,
            type3=args.type3,
            type4=args.type4,
            non_clone=args.non_clone,
        )

    elif args.command == "layers":
        from src.backend.benchmark.runners.layer_runner import ThreeLayerBenchmarkRunner

        runner = ThreeLayerBenchmarkRunner(output_dir=args.output)
        runner.run()

    elif args.command == "competitor":
        from src.backend.benchmark.competitors.report import CompetitorComparisonReport
        from src.backend.benchmark.competitors.runner import CompetitorBenchmarkRunner

        runner = CompetitorBenchmarkRunner(
            output_dir=args.output,
            threshold=args.threshold,
        )
        result = runner.run(
            n_type1=args.type1,
            n_type2=args.type2,
            n_type3=args.type3,
            n_type4=args.type4,
            n_negative=args.negative,
            seed=args.seed,
            n_bootstrap=args.bootstrap,
        )
        # Generate reports
        report = CompetitorComparisonReport(result)
        fmt = args.format
        if fmt in ("all", "markdown"):
            md_path = report.save_markdown(f"{args.output}/comparison_report.md")
            print(f"  Markdown report: {md_path}")
        if fmt in ("all", "html"):
            html_path = report.save_html(f"{args.output}/comparison_report.html")
            print(f"  HTML report:     {html_path}")
        if fmt == "all":
            print(f"  JSON data:       {args.output}/{result.run_id}.json")

    elif args.command == "full":
        from src.backend.benchmark.runners.full_runner import FullBenchmarkRunner

        runner = FullBenchmarkRunner(output_dir=args.output)
        runner.run(
            type1=args.type1,
            type2=args.type2,
            type3=args.type3,
            type4=args.type4,
            non_clone=args.non_clone,
        )

    elif args.command in {"pan", "run"}:
        from pathlib import Path

        from src.backend.benchmark.runners.pan_benchmark_runner import (
            PANBenchmarkRunner,
        )

        logger.info("Starting PAN benchmark runner")
        runner = PANBenchmarkRunner(
            output_dir=args.output,
            threshold=args.threshold,
            use_micro_average=args.micro_average,
        )

        if args.tools:
            logger.info("Selected tools: %s", ", ".join(args.tools))
        else:
            logger.info("Available tools: %s", ", ".join(runner.get_available_tools()))

        if args.datasets:
            logger.info("Selected datasets: %s", ", ".join(args.datasets))
        else:
            logger.info(
                "Available datasets: %s", ", ".join(runner.get_available_datasets())
            )

        report = runner.run_benchmark(
            tools=args.tools,
            datasets=args.datasets,
            custom_dataset_path=Path(args.dataset_path) if args.dataset_path else None,
        )

        print("\nPAN Benchmark Completed!\n")
        print(report.generate_comparison_table())
        print()

        timestamp = int(time.time())
        if args.format in ("all", "markdown"):
            md_path = f"{args.output}/pan_benchmark_report_{timestamp}.md"
            report.save_markdown(md_path)
            print(f"Markdown report: {md_path}")
        if args.format in ("all", "json"):
            json_path = f"{args.output}/pan_benchmark_results_{timestamp}.json"
            report.save_json(json_path)
            print(f"JSON results: {json_path}")

    elif args.command == "fusion-optimize":
        from pathlib import Path

        from src.backend.benchmark.runners.fusion_optimization_runner import (
            run_fusion_optimization,
        )

        logger.info("Starting fusion optimization benchmark")
        report = run_fusion_optimization(
            output_dir=Path(args.output),
            dataset_root=Path(args.dataset_root),
            verdicts=args.verdicts,
            trials=args.trials,
            threshold_step=args.threshold_step,
            max_submissions_per_problem_language=args.max_submissions,
            max_positive_pairs_per_problem_language=args.max_positive_pairs,
            negative_ratio=args.negative_ratio,
            seed=args.seed,
        )
        timestamp = int(time.time())
        markdown_path = Path(args.output) / f"fusion_optimization_report_{timestamp}.md"
        json_path = Path(args.output) / f"fusion_optimization_results_{timestamp}.json"
        report.save_markdown(markdown_path)
        report.save_json(json_path)
        print("\nFusion Optimization Completed!\n")
        print(f"Pairs: {report.pair_count}")
        print(
            f"Best weighted F1: {max(item.best_metrics.f1_score for item in report.experiments):.4f}"
        )
        print(f"Markdown report: {markdown_path}")
        print(f"JSON results: {json_path}")
    elif args.command == "weight-tune":
        from pathlib import Path

        from src.backend.benchmark.runners.weight_tuning_plan_runner import (
            run_weight_tuning_plan,
        )

        summary = run_weight_tuning_plan(
            scored_pairs_path=Path(args.input),
            output_dir=Path(args.output),
            train_ratio=args.train_ratio,
            seed=args.seed,
            threshold=args.threshold,
            grid_step=args.grid_step,
            fpr_limit=args.fpr_limit,
            max_grid_runs=args.max_grid_runs,
        )
        print("\nWeight Tuning Plan Completed!\n")
        print(f"Artifacts: {summary['output_dir']}")
        print(f"Pairs: {summary['pair_count']}")
        print(f"Baseline F1: {summary['baseline_f1']:.4f}")
        print(f"Training F1: {summary['best_training_f1']:.4f}")
        print(f"Final test F1: {summary['final_test_f1']:.4f}")
        print(f"Best threshold: {summary['best_threshold']:.2f}")

    elif args.command == "fusion-train":
        from pathlib import Path

        from src.backend.benchmark.runners.fusion_training_runner import (
            run_supervised_fusion_training,
        )

        logger.info("Starting supervised fusion training workflow")
        report = run_supervised_fusion_training(
            output_dir=Path(args.output),
            train_datasets=args.train_datasets,
            eval_datasets=args.eval_datasets,
            dataset_roots=(
                [Path(root) for root in args.dataset_roots]
                if args.dataset_roots
                else None
            ),
            train_pair_limit=args.train_pairs,
            eval_pair_limit=args.eval_pairs,
            threshold_step=args.threshold_step,
            optuna_trials=args.optuna_trials,
            seed=args.seed,
        )
        timestamp = int(time.time())
        markdown_path = Path(args.output) / f"fusion_training_report_{timestamp}.md"
        json_path = Path(args.output) / f"fusion_training_results_{timestamp}.json"
        report.save_markdown(markdown_path)
        report.save_json(json_path)
        print("\nFusion Training Completed!\n")
        print(f"Train pairs: {report.train_pair_count}")
        print(f"Eval pairs: {report.eval_pair_count}")
        print(f"Best overall result: {report.best_experiment_name}")
        print(f"Best model: {report.best_model_name}")
        print(f"Model artifact: {report.best_model_path}")
        print(f"Markdown report: {markdown_path}")
        print(f"JSON results: {json_path}")

    elif args.command == "engine-eval":
        from pathlib import Path

        from src.backend.benchmark.runners.engine_evaluation_runner import (
            run_engine_evaluation,
        )

        logger.info("Starting engine evaluation harness")
        report = run_engine_evaluation(
            output_dir=Path(args.output),
            dataset_root=Path(args.dataset_root) if args.dataset_root else None,
            threshold_step=args.threshold_step,
            moss_user_id=args.moss_user_id or "",
            enabled_tools=args.tools,
            pair_limit=args.pair_limit,
            dataset_name=args.dataset,
            dataset_roots=(
                [Path(root) for root in args.dataset_roots]
                if args.dataset_roots
                else None
            ),
            external_batch_size=args.external_batch_size,
            prewarm_embeddings=not args.no_prewarm_embeddings,
        )
        print("\nEngine Evaluation Completed!\n")
        print(f"Dataset: {report.dataset_name} ({report.language})")
        print(
            f"Pairs: {report.pair_count} "
            f"({report.positive_pairs} positive, {report.negative_pairs} negative)"
        )
        for scorer in sorted(
            [item for item in report.scorers if item.available],
            key=lambda item: item.auc_roc,
            reverse=True,
        ):
            print(
                f"  {scorer.name:14} {scorer.kind:16} "
                f"AUC={scorer.auc_roc:.4f}  F1@best={scorer.best_f1:.4f}  "
                f"ECE={scorer.ece:.3f}  Brier={scorer.brier:.3f}"
            )
        for scorer in report.scorers:
            if not scorer.available:
                print(f"  {scorer.name:14} UNAVAILABLE: {scorer.error}")
        print(f"\nJSON report: {args.output}/{report.run_id}.json")
        print(f"Markdown report: {args.output}/{report.run_id}.md")

    elif args.command == "fusion-train-learned":
        from pathlib import Path

        from src.backend.benchmark.runners.learned_fusion_training_runner import (
            run_learned_fusion_training,
        )

        logger.info("Starting learned fusion training workflow")
        report = run_learned_fusion_training(
            output_dir=Path(args.output),
            artifact_path=Path(args.artifact) if args.artifact else None,
            threshold_step=args.threshold_step,
            seed=args.seed,
            enabled_datasets=args.datasets,
            dataset_roots=(
                [Path(root) for root in args.dataset_roots]
                if args.dataset_roots
                else None
            ),
            max_pairs_per_dataset=args.max_pairs,
            cv_folds=args.cv_folds,
            poolc_negative_ratio=args.poolc_negative_ratio,
            cache_path=Path(args.cache) if args.cache else None,
            dataset_weighting=args.dataset_weighting,
            prewarm_embeddings=not args.no_prewarm_embeddings,
        )
        print("\nLearned Fusion Training Completed!\n")
        print(
            f"Pairs: {report.pair_count} "
            f"({report.positive_pairs} positive, {report.negative_pairs} negative)"
        )
        print(f"Production fused AUC: {report.production_fused_auc:.4f}")
        print(f"Learned fusion {report.cv_mode} AUC: {report.cv_auc:.4f}")
        for dataset_name in sorted(report.per_dataset_auc):
            rule = report.per_dataset_production_auc.get(dataset_name, 0.0)
            print(
                f"  {dataset_name}: rule {rule:.4f} -> "
                f"learned {report.per_dataset_auc[dataset_name]:.4f} "
                f"({report.pairs_per_dataset.get(dataset_name, 0)} pairs)"
            )
        print(f"Model artifact: {report.artifact_path}")
        print(f"Markdown report: {args.output}/learned_fusion_report_*.md")

    elif args.command == "feature-cache-check":
        import json
        from pathlib import Path

        from src.backend.benchmark.runners.learned_fusion_training_runner import (
            LearnedFusionTrainingRunner,
        )

        runner = LearnedFusionTrainingRunner(
            output_dir=Path("reports/feature_cache_check"),
            dataset_roots=(
                [Path(root) for root in args.dataset_roots]
                if args.dataset_roots
                else None
            ),
            cache_path=Path(args.cache),
        )
        try:
            report = runner.verify_feature_cache(
                dataset_names=args.datasets,
                sample=args.sample,
                seed=args.seed,
                tolerance=args.tolerance,
            )
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))

        print(f"cache:    {report.cache_path}")
        print(f"recipe:   {report.recipe}")
        print(f"entries:  {report.cached_entries}")
        print(
            f"sampled:  {report.sampled_pairs} pairs "
            f"({report.compared_values} feature values)"
        )
        print(f"max diff: {report.max_abs_diff:.6g} (tolerance {report.tolerance:g})")
        for name in sorted(report.per_feature_max):
            print(f"  {name:12} {report.per_feature_max[name]:.6g}")
        if report.mismatched_pairs:
            print("mismatched pairs:")
            for pair_id in report.mismatched_pairs:
                print(f"  {pair_id}")
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report.to_json_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"report:   {path}")
        if report.sampled_pairs == 0:
            print("the cache has no rows for these datasets; nothing to compare")
            return 1
        if report.stale:
            print(
                "\nSTALE: the cache disagrees with live extraction. Re-extract it "
                "(delete the file) before trusting any retrain. If the difference "
                "is legitimate, the cache recipe should have changed: check "
                "FEATURE_CACHE_VERSION, the embedding model and the feature list."
            )
            return 1
        print("\nOK: the cache matches live extraction.")
        return 0

    elif args.command == "fusion-gate":
        import json
        from pathlib import Path

        from src.backend.benchmark.gate import (
            collect_scores,
            evaluate_gate,
            load_baseline_metadata,
        )

        baselines = None
        if args.baseline:
            baselines = {}
            for item in args.baseline:
                name, _, value = item.partition("=")
                if not name.strip() or not value.strip():
                    parser.error(f"--baseline expects DATASET=AUC, got {item!r}")
                baselines[name.strip()] = float(value)

        baseline_files = []
        if args.baseline_report:
            from src.backend.benchmark.gate import SHIPPED_BASELINE

            host_baseline, baseline_files = collect_scores(
                [Path(path) for path in args.baseline_report], scorer=args.scorer
            )
            if not host_baseline:
                parser.error(
                    "no usable baseline report under: "
                    + ", ".join(args.baseline_report)
                )
            # Keep every corpus in the verdict: a host baseline that covers one
            # corpus must not silently shrink the gate to one corpus.
            for missing in sorted(set(SHIPPED_BASELINE) - set(host_baseline)):
                print(
                    f"warning: host baseline has no measurement for {missing}; "
                    "falling back to the built-in constant"
                )
            for dataset, host_value in sorted(host_baseline.items()):
                reference = SHIPPED_BASELINE.get(dataset)
                if reference is not None and abs(host_value - reference) > 0.002:
                    print(
                        f"note: host baseline {dataset} is {host_value:.4f} vs "
                        f"constant {reference:.4f} "
                        f"({host_value - reference:+.4f}); using the host value"
                    )
            baselines = {**SHIPPED_BASELINE, **host_baseline, **(baselines or {})}

            metadata = load_baseline_metadata(
                [Path(path) for path in args.baseline_report]
            )
            if metadata:
                print(
                    "baseline measured "
                    f"{metadata.get('created_at') or 'at an unknown time'}"
                    + (
                        f" at commit {metadata['commit']}"
                        if metadata.get("commit")
                        else ""
                    )
                )
                recorded = metadata.get("artifact_sha256")
                current = _artifact_sha256()
                if recorded and current and recorded != current:
                    message = (
                        "the baseline was measured with a different shipped artifact "
                        f"(baseline sha256={recorded[:12]}, now {current[:12]}). "
                        "Re-measure it with scripts/gpu/baseline.sh, or pass "
                        "--allow-stale-baseline to judge against the old bar anyway"
                    )
                    if args.allow_stale_baseline:
                        print(f"warning: {message}")
                    else:
                        parser.error(message)

        scores, used_files = collect_scores(
            [Path(path) for path in args.report], scorer=args.scorer
        )
        if baseline_files and set(used_files) & set(baseline_files):
            parser.error(
                "the baseline report is also the candidate report: "
                + ", ".join(
                    str(path) for path in sorted(set(used_files) & set(baseline_files))
                )
            )
        result = evaluate_gate(scores, baselines=baselines, tolerance=args.tolerance)
        if args.json:
            print(
                json.dumps(
                    {
                        **result.to_dict(),
                        "baseline_files": [str(path) for path in baseline_files],
                    },
                    indent=2,
                )
            )
        else:
            if baseline_files:
                for path in baseline_files:
                    print(f"baseline {path}")
            else:
                print("baseline: built-in shipped-artifact constants (2026-10-22)")
            for path in used_files:
                print(f"read {path}")
            if used_files or baseline_files:
                print()
            print(result.format_table())
        return 0 if result.passed else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
