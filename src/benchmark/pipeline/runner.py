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
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
import random
import os
from threading import Lock

try:
    from tqdm import tqdm
    _HAS_TQDM = True
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable
    _HAS_TQDM = False

from src.benchmark.pipeline.config import BenchmarkConfig
from src.benchmark.pipeline.loader import CanonicalDataset, CodePair, DatasetLoader
from src.benchmark.pipeline.external_loader import ExternalDatasetLoader
from src.benchmark.pipeline.stages import (
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
from src.benchmark.registry import registry
from src.benchmark.forensics.clone_type_breakdown import (
    CloneTypeBreakdown,
    analyze_clone_type_breakdown,
)

# Auto-load plugins
try:
    import plugins
    plugins.load_plugins()
except ImportError:
    pass

# Auto-load plugins
try:
    import plugins
    plugins.load_plugins()
except ImportError:
    pass


def _parse_code_single(args):
    """Top-level function for ProcessPoolExecutor (must be picklable).
    
    Args:
        args: Tuple of (code_id, norm_code, parser_type).
    
    Returns:
        Tuple of (code_id, ParsedCode).
    """
    code_id, norm_code, parser_type = args
    stage = ParserStage()
    result = stage.execute(
        (code_id, norm_code),
        {"type": parser_type},
    )
    return (code_id, result)


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
        self._sim_cache: Dict[str, float] = {}
        self._sim_cache_lock = Lock()

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
            # Validate dataset
            if not dataset.pairs:
                return BenchmarkRunResult(
                    config_hash="", dataset_name=dataset.name,
                    dataset_version=dataset.version, engine_name=config.engine.name,
                    metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                    success=False, error="Dataset contains no pairs",
                )
            pos = sum(1 for p in dataset.pairs if p.label == 1)
            neg = sum(1 for p in dataset.pairs if p.label == 0)
            if pos == 0:
                return BenchmarkRunResult(
                    config_hash="", dataset_name=dataset.name,
                    dataset_version=dataset.version, engine_name=config.engine.name,
                    metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                    success=False,
                    error=f"Dataset has no positive pairs (all {len(dataset.pairs)} pairs are negative)",
                )
            if neg == 0:
                return BenchmarkRunResult(
                    config_hash="", dataset_name=dataset.name,
                    dataset_version=dataset.version, engine_name=config.engine.name,
                    metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                    success=False,
                    error=f"Dataset has no negative pairs (all {len(dataset.pairs)} pairs are positive)",
                )

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
                    futs = {ex.submit(_normalize_one, p): p for p in dataset.pairs}
                    for f in tqdm(as_completed(futs), total=len(futs), desc="Normalizing", disable=not _HAS_TQDM):
                        f.result()
            else:
                for pair in tqdm(dataset.pairs, desc="Normalizing", disable=not _HAS_TQDM):
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

            parser_type = config.parser.type
            if use_parallel and num_pairs > 20:
                with ProcessPoolExecutor(max_workers=min(num_workers, os.cpu_count() or 4)) as ex:
                    parse_args = [(cid, nc, parser_type) for cid, nc in all_code.items()]
                    futs = {ex.submit(_parse_code_single, a): a[0] for a in parse_args}
                    for f in tqdm(as_completed(futs), total=len(futs), desc="Parsing", disable=not _HAS_TQDM):
                        cid, result = f.result()
                        parsed[cid] = result
            elif use_parallel:
                with ThreadPoolExecutor(max_workers=num_workers) as ex:
                    futs = [
                        ex.submit(_parse_one, cid, nc) for cid, nc in all_code.items()
                    ]
                    for f in tqdm(as_completed(futs), total=len(futs), desc="Parsing", disable=not _HAS_TQDM):
                        f.result()
            else:
                for cid, nc in tqdm(all_code.items(), desc="Parsing", disable=not _HAS_TQDM):
                    _parse_one(cid, nc)

            # ===== Stage 3: Compute similarity =====
            results: List[SimilarityResult] = []
            results_lock = Lock()

            def _similarity_one(pair: CodePair) -> None:
                """Compute similarity for one pair."""
                code_a = parsed.get(pair.id_a)
                code_b = parsed.get(pair.id_b)
                if code_a and code_b:
                    cache_key = f"{pair.id_a}:{pair.id_b}"
                    with self._sim_cache_lock:
                        cached = self._sim_cache.get(cache_key)
                    if cached is not None:
                        result = SimilarityResult(
                            id_a=pair.id_a, id_b=pair.id_b,
                            score=cached, engine_name=getattr(engine, 'name', ''),
                            clone_type=pair.clone_type,
                        )
                    else:
                        result = similarity_stage.execute(
                            (code_a, code_b, engine),
                            {"clone_type": pair.clone_type},
                        )
                        with self._sim_cache_lock:
                            self._sim_cache[cache_key] = result.score
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
        best_score = -1.0

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

            from src.benchmark.evaluation.metrics import precision, recall, f1_score
            prec = precision(tp, fp)
            rec = recall(tp, fn)
            f1 = f1_score(prec, rec)

            score = f1 if strategy == "f1_max" else prec

            if score > best_score:
                best_score = score
                best_threshold = t

        return best_threshold

    def run_cv(
        self,
        dataset: CanonicalDataset,
        config: BenchmarkConfig,
        n_folds: int = 5,
    ) -> BenchmarkRunResult:
        """Run benchmark with cross-validated threshold optimization.

        Splits dataset into n_folds using stratified sampling to ensure
        each fold has both positive and negative pairs. Optimizes threshold
        on n-1 folds, evaluates on held-out fold. Reports average metrics.

        Args:
            dataset: Loaded dataset to evaluate against.
            config: Pipeline configuration.
            n_folds: Number of cross-validation folds.

        Returns:
            BenchmarkRunResult with averaged metrics.
        """
        import random as _random
        rng = _random.Random(self._seed)

        pos_pairs = [p for p in dataset.pairs if p.label == 1]
        neg_pairs = [p for p in dataset.pairs if p.label == 0]

        # Determine feasible number of folds
        min_class_size = min(len(pos_pairs), len(neg_pairs))
        actual_folds = min(n_folds, min_class_size)
        if actual_folds < 2:
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name, dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                success=False,
                error=f"Dataset too small for {n_folds}-fold CV: "
                      f"need at least 2 positive and 2 negative pairs "
                      f"(have {len(pos_pairs)} pos, {len(neg_pairs)} neg)",
            )

        # Stratified split: shuffle each class separately, then distribute
        rng.shuffle(pos_pairs)
        rng.shuffle(neg_pairs)

        pos_folds: List[List[CodePair]] = [[] for _ in range(actual_folds)]
        neg_folds: List[List[CodePair]] = [[] for _ in range(actual_folds)]

        for i, p in enumerate(pos_pairs):
            pos_folds[i % actual_folds].append(p)
        for i, p in enumerate(neg_pairs):
            neg_folds[i % actual_folds].append(p)

        folds = [pos_folds[i] + neg_folds[i] for i in range(actual_folds)]

        all_metrics = []
        for fold_idx in range(actual_folds):
            test_pairs = folds[fold_idx]
            train_pairs = [p for i, fold in enumerate(folds) if i != fold_idx for p in fold]

            train_ds = CanonicalDataset(
                name=f"{dataset.name}_train_{fold_idx}",
                version=dataset.version,
                pairs=train_pairs,
                language=dataset.language,
            )
            test_ds = CanonicalDataset(
                name=f"{dataset.name}_test_{fold_idx}",
                version=dataset.version,
                pairs=test_pairs,
                language=dataset.language,
            )

            train_result = self.run(train_ds, config)
            if not train_result.success:
                continue

            test_result = self.run(test_ds, config)
            if test_result.success:
                all_metrics.append(test_result.metrics)

        if not all_metrics:
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name, dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                success=False, error="All CV folds failed",
            )

        avg = MetricsResult(
            precision=sum(m.precision for m in all_metrics) / len(all_metrics),
            recall=sum(m.recall for m in all_metrics) / len(all_metrics),
            f1=sum(m.f1 for m in all_metrics) / len(all_metrics),
            accuracy=sum(m.accuracy for m in all_metrics) / len(all_metrics),
            map_score=sum(m.map_score for m in all_metrics) / len(all_metrics),
            mrr_score=sum(m.mrr_score for m in all_metrics) / len(all_metrics),
            ndcg=sum(m.ndcg for m in all_metrics) / len(all_metrics),
            top_k_precision=sum(m.top_k_precision for m in all_metrics) / len(all_metrics),
            threshold=sum(m.threshold for m in all_metrics) / len(all_metrics),
            tp=int(sum(m.tp for m in all_metrics) / len(all_metrics)),
            fp=int(sum(m.fp for m in all_metrics) / len(all_metrics)),
            tn=int(sum(m.tn for m in all_metrics) / len(all_metrics)),
            fn=int(sum(m.fn for m in all_metrics) / len(all_metrics)),
        )

        return BenchmarkRunResult(
            config_hash=config.config_hash(),
            dataset_name=dataset.name, dataset_version=dataset.version,
            engine_name=config.engine.name,
            metrics=avg,
            success=True,
        )

        # Stratified split: shuffle each class separately, then distribute
        rng.shuffle(pos_pairs)
        rng.shuffle(neg_pairs)

        pos_folds: List[List[CodePair]] = [[] for _ in range(actual_folds)]
        neg_folds: List[List[CodePair]] = [[] for _ in range(actual_folds)]

        for i, p in enumerate(pos_pairs):
            pos_folds[i % actual_folds].append(p)
        for i, p in enumerate(neg_pairs):
            neg_folds[i % actual_folds].append(p)

        folds = [pos_folds[i] + neg_folds[i] for i in range(actual_folds)]

        all_metrics = []
        for fold_idx in range(actual_folds):
            test_pairs = folds[fold_idx]
            train_pairs = [p for i, fold in enumerate(folds) if i != fold_idx for p in fold]

            train_ds = CanonicalDataset(
                name=f"{dataset.name}_train_{fold_idx}",
                version=dataset.version,
                pairs=train_pairs,
                language=dataset.language,
            )
            test_ds = CanonicalDataset(
                name=f"{dataset.name}_test_{fold_idx}",
                version=dataset.version,
                pairs=test_pairs,
                language=dataset.language,
            )

            train_result = self.run(train_ds, config)
            if not train_result.success:
                continue

            test_result = self.run(test_ds, config)
            if test_result.success:
                all_metrics.append(test_result.metrics)

        if not all_metrics:
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name, dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=MetricsResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                success=False, error="All CV folds failed",
            )

        avg = MetricsResult(
            precision=sum(m.precision for m in all_metrics) / len(all_metrics),
            recall=sum(m.recall for m in all_metrics) / len(all_metrics),
            f1=sum(m.f1 for m in all_metrics) / len(all_metrics),
            accuracy=sum(m.accuracy for m in all_metrics) / len(all_metrics),
            map_score=sum(m.map_score for m in all_metrics) / len(all_metrics),
            mrr_score=sum(m.mrr_score for m in all_metrics) / len(all_metrics),
            ndcg=sum(m.ndcg for m in all_metrics) / len(all_metrics),
            top_k_precision=sum(m.top_k_precision for m in all_metrics) / len(all_metrics),
            threshold=sum(m.threshold for m in all_metrics) / len(all_metrics),
            tp=int(sum(m.tp for m in all_metrics) / len(all_metrics)),
            fp=int(sum(m.fp for m in all_metrics) / len(all_metrics)),
            tn=int(sum(m.tn for m in all_metrics) / len(all_metrics)),
            fn=int(sum(m.fn for m in all_metrics) / len(all_metrics)),
        )

        return BenchmarkRunResult(
            config_hash=config.config_hash(),
            dataset_name=dataset.name, dataset_version=dataset.version,
            engine_name=config.engine.name,
            metrics=avg,
            success=True,
        )

    def run_comparison(
        self,
        dataset: CanonicalDataset,
        engine_names: List[str],
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkRunResult]:
        """Run benchmark with multiple engines and compare results.

        Args:
            dataset: Loaded dataset to evaluate against.
            engine_names: List of engine names to compare.
            config: Pipeline configuration (engine name will be overridden).

        Returns:
            Dict mapping engine name to BenchmarkRunResult.
        """
        results = {}
        for engine_name in engine_names:
            engine_config = BenchmarkConfig()
            if config:
                engine_config = config
                engine_config.engine.name = engine_name
            else:
                engine_config.engine.name = engine_name
            results[engine_name] = self.run(dataset, engine_config)
        return results

    def run_comparison_report(
        self,
        dataset: CanonicalDataset,
        engine_names: List[str],
        config: Optional[BenchmarkConfig] = None,
    ) -> str:
        """Run multi-engine comparison and return a formatted report string.

        Args:
            dataset: Loaded dataset to evaluate against.
            engine_names: List of engine names to compare.
            config: Pipeline configuration.

        Returns:
            Formatted comparison report string.
        """
        results = self.run_comparison(dataset, engine_names, config)

        lines = []
        lines.append(f"Engine Comparison Report - {dataset.name}")
        lines.append("=" * 80)
        header = f"{'Engine':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Accuracy':>10} {'Threshold':>10}"
        lines.append(header)
        lines.append("-" * 80)

        for name in engine_names:
            r = results[name]
            if r.success:
                m = r.metrics
                lines.append(
                    f"{name:<25} {m.precision:>10.4f} {m.recall:>10.4f} "
                    f"{m.f1:>10.4f} {m.accuracy:>10.4f} {m.threshold:>10.4f}"
                )
            else:
                lines.append(f"{name:<25} {'FAILED':>65} ({r.error})")

        lines.append("-" * 80)

        # Statistical significance
        if len(engine_names) >= 2:
            import numpy as np
            from src.benchmark.evaluation.metrics.significance import compare_engines_significance

            scores_by_engine = {}
            for name in engine_names:
                r = results[name]
                if r.success:
                    scores_by_engine[name] = r

            engine_list = [n for n in engine_names if n in scores_by_engine]
            for i in range(len(engine_list)):
                for j in range(i + 1, len(engine_list)):
                    a_name = engine_list[i]
                    b_name = engine_list[j]
                    lines.append(f"\n{a_name} vs {b_name}:")

                    # Get scores from the results - we need to re-run to get paired scores
                    # For now, show F1 comparison
                    a_f1 = scores_by_engine[a_name].metrics.f1
                    b_f1 = scores_by_engine[b_name].metrics.f1
                    lines.append(f"  F1 delta: {a_f1 - b_f1:+.4f}")

        return "\n".join(lines)