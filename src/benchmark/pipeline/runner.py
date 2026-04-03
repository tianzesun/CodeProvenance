"""Unified Benchmark Runner.

Single entry point for all benchmark execution.
All runs MUST go through: BenchmarkRunner.run(config)

Canonical pipeline DAG:
    Configuration -> Dataset -> Normalizer -> Parser -> Similarity -> Evaluation -> Metrics -> Reporting

Rules:
1. Single entry point - no bypassing
2. Immutable stages - pure functions, stateless, deterministic
3. One-way data flow - no backward dependencies
4. Parallel execution support for large datasets
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
import random
import os
from threading import Lock

from benchmark.pipeline.config import BenchmarkConfig
from benchmark.pipeline.loader import CanonicalDataset, CodePair, DatasetLoader
from benchmark.pipeline.external_loader import ExternalDatasetLoader
from benchmark.pipeline.stages import (
    NormalizerStage,
    ParserStage,
    SimilarityStage,
    EvaluationStage,
    MetricsStage,
    ReportingStage,
    SimilarityResult,
    MetricsResult,
    ParsedCode,
)
from benchmark.registry import registry
from benchmark.analysis.clone_type_breakdown import (
    CloneTypeBreakdown,
    analyze_clone_type_breakdown,
)


@dataclass
class BenchmarkRunResult:
    """Result of a benchmark run."""
    config_hash: str
    dataset_name: str
    dataset_version: str
    engine_name: str
    metrics: MetricsResult
    report_paths: Dict[str, str] = None
    success: bool = True
    error: str = ""


class BenchmarkRunner:
    """Core benchmark runner - the ONLY entry point for execution.

    Usage:
        config = BenchmarkConfig(...)
        runner = BenchmarkRunner()
        result = runner.run(dataset, config)
    """

    def __init__(self, seed: int = 42):
        """Initialize with fixed seed for determinism.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        random.seed(seed)

    def load_external_dataset(
        self,
        name: str,
        split: str = "test",
        max_pairs: Optional[int] = None,
    ) -> CanonicalDataset:
        """Load an external dataset by name.

        Args:
            name: Dataset name (poj104, codexglue_clone, codexglue_defect,
                  codesearchnet, kaggle).
            split: Dataset split where applicable.
            max_pairs: Maximum number of pairs to load.

        Returns:
            CanonicalDataset for benchmarking.
        """
        loader = ExternalDatasetLoader(seed=self._seed)
        return loader.load_by_name(name, split=split, max_pairs=max_pairs)

    def run(
        self,
        dataset: CanonicalDataset,
        config: BenchmarkConfig,
    ) -> BenchmarkRunResult:
        """Run benchmark through the complete pipeline DAG.

        This is the single authoritative execution path.

        Args:
            dataset: Loaded dataset to evaluate against.
            config: Pipeline configuration.

        Returns:
            BenchmarkRunResult with metrics and report paths.
        """
        try:
            # Stage 1: Get engine from registry
            engine = registry.get_instance(config.engine.name)

            # Stage 2-7: Pipeline stages
            normalizer = self._get_normalizer(config.normalizer.type)
            normalizer_stage = NormalizerStage(normalizer)
            parser_stage = ParserStage()
            similarity_stage = SimilarityStage()
            evaluation_stage = EvaluationStage()
            metrics_stage = MetricsStage()
            reporting_stage = ReportingStage()

            # Ground truth
            ground_truth = dataset.get_ground_truth()

            # Determine parallelism
            num_pairs = len(dataset.pairs)
            num_workers = max(1, min(
                num_pairs,
                getattr(config, 'parallel_workers', None) or (os.cpu_count() or 4),
            ))
            use_parallel = num_pairs > 50

            # ===== Stage 1: Normalize all code =====
            all_code: Dict[str, str] = {}
            all_code_lock = Lock()

            def _normalize_one(pair: CodePair) -> None:
                """Normalize one pair's code."""
                for code_id, raw_code in [(pair.id_a, pair.code_a), (pair.id_b, pair.code_b)]:
                    if code_id not in all_code:
                        normalized = normalizer_stage.execute([raw_code], {})[0]
                        with all_code_lock:
                            all_code[code_id] = normalized

            if use_parallel and num_pairs > 100:
                with ThreadPoolExecutor(max_workers=num_workers) as ex:
                    list(as_completed({
                        ex.submit(_normalize_one, p): p for p in dataset.pairs
                    }))
            else:
                for pair in dataset.pairs:
                    _normalize_one(pair)

            # ===== Stage 2: Parse all code =====
            parsed: Dict[str, ParsedCode] = {}
            parsed_lock = Lock()

            def _parse_one(code_id: str, norm_code: str) -> None:
                """Parse one code snippet."""
                result = parser_stage.execute(
                    (code_id, norm_code),
                    {"type": config.parser.type},
                )
                with parsed_lock:
                    parsed[code_id] = result

            if use_parallel:
                with ThreadPoolExecutor(max_workers=num_workers) as ex:
                    futs = [
                        ex.submit(_parse_one, cid, nc) for cid, nc in all_code.items()
                    ]
                    for f in as_completed(futs):
                        f.result()  # propagate exceptions
            else:
                for cid, nc in all_code.items():
                    _parse_one(cid, nc)

            # ===== Stage 3: Compute similarity =====
            results: List[SimilarityResult] = []
            results_lock = Lock()

            def _similarity_one(pair: CodePair) -> None:
                """Compute similarity for one pair."""
                code_a = parsed.get(pair.id_a)
                code_b = parsed.get(pair.id_b)
                if code_a and code_b:
                    result = similarity_stage.execute(
                        (code_a, code_b, engine),
                        {"clone_type": pair.clone_type},
                    )
                    with results_lock:
                        results.append(result)

            if use_parallel:
                with ThreadPoolExecutor(max_workers=num_workers) as ex:
                    futs = [ex.submit(_similarity_one, p) for p in dataset.pairs]
                    for f in as_completed(futs):
                        f.result()
            else:
                for pair in dataset.pairs:
                    _similarity_one(pair)

            # ===== Stage 4: Optimize threshold =====
            if config.threshold.optimize:
                best_threshold = self._optimize_threshold(
                    results, ground_truth, config.threshold.strategy,
                )
            else:
                best_threshold = 0.5

            # ===== Stage 5: Evaluate =====
            evaluated = evaluation_stage.execute(
                (results, ground_truth),
                {"threshold": best_threshold},
            )

            # ===== Stage 6: Metrics =====
            metrics_config = {
                "threshold": best_threshold,
                "metrics": config.metrics.metrics,
            }
            metrics = metrics_stage.execute(evaluated, metrics_config)
            metrics.threshold = best_threshold

            # Clone type breakdown
            clone_type_map = dataset.get_clone_type_map()
            breakdown = analyze_clone_type_breakdown(
                results=results,
                ground_truth=ground_truth,
                pair_clone_types=clone_type_map,
                threshold=best_threshold,
            )
            breakdown.engine_name = config.engine.name
            clone_type_results = breakdown.summary_dict()

            # ===== Stage 7: Reporting =====
            pipeline_config = {
                "output": {
                    "json": config.output.json,
                    "html": config.output.html,
                    "leaderboard": config.output.leaderboard,
                },
                "output_dir": "reports/json",
                "config_hash": config.config_hash(),
            }
            extra_info = {
                "engine": config.engine.name,
                "dataset": dataset.name,
                "clone_type_breakdown": clone_type_results,
            }
            report_paths = reporting_stage.execute(
                (metrics, extra_info), pipeline_config,
            )

            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name,
                dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=metrics,
                report_paths=report_paths,
                success=True,
            )

        except Exception as e:
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name,
                dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=MetricsResult(),
                success=False,
                error=str(e),
            )

    def _get_normalizer(self, normalizer_type: str) -> Callable[[str], str]:
        """Get normalizer function by type."""
        return lambda code: code.strip()

    def _optimize_threshold(
        self,
        results: List[SimilarityResult],
        ground_truth: Dict,
        strategy: str = "f1_max",
    ) -> float:
        """Find optimal threshold by maximizing F1.

        Args:
            results: List of similarity results.
            ground_truth: Ground truth mapping.
            strategy: Optimization strategy (f1_max or precision_max).

        Returns:
            Optimal threshold value.
        """
        best_threshold = 0.5
        best_score = 0.0

        for t_int in range(0, 101):
            t = t_int / 100.0
            tp = fp = tn = fn = 0

            for r in results:
                key = (r.id_a, r.id_b)
                label = ground_truth.get(key, ground_truth.get((r.id_b, r.id_a), 0))
                predicted = 1 if r.score >= t else 0

                if predicted == 1 and label == 1:
                    tp += 1
                elif predicted == 1 and label == 0:
                    fp += 1
                elif predicted == 0 and label == 0:
                    tn += 1
                else:
                    fn += 1

            from benchmark.metrics import precision, recall, f1_score
            prec = precision(tp, fp)
            rec = recall(tp, fn)
            f1 = f1_score(prec, rec)

            score = f1 if strategy == "f1_max" else prec

            if score > best_score:
                best_score = score
                best_threshold = t

        return best_threshold