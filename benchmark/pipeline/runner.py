"""Unified Benchmark Runner.

Single entry point for all benchmark execution.
All runs MUST go through: BenchmarkRunner.run(config)

Canonical pipeline DAG:
    Configuration -> Dataset -> Normalizer -> Parser -> Similarity -> Evaluation -> Metrics -> Reporting

Rules:
1. Single entry point - no bypassing
2. Immutable stages - pure functions, stateless, deterministic
3. One-way data flow - no backward dependencies
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import random

from benchmark.pipeline.config import BenchmarkConfig
from benchmark.pipeline.loader import CanonicalDataset, CodePair, DatasetLoader
from benchmark.pipeline.stages import (
    NormalizerStage,
    ParserStage,
    SimilarityStage,
    EvaluationStage,
    MetricsStage,
    ReportingStage,
    SimilarityResult,
    MetricsResult,
    ParsedCode
)
from benchmark.registry import registry


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
    
    def run(
        self,
        dataset: CanonicalDataset,
        config: BenchmarkConfig
    ) -> BenchmarkRunResult:
        """Run benchmark through the complete pipeline DAG.
        
        This is the single authoritative execution path.
        NO shortcuts, NO bypassing.
        
        Args:
            dataset: Loaded dataset to evaluate against.
            config: Pipeline configuration.
            
        Returns:
            BenchmarkRunResult with metrics and report paths.
        """
        try:
            # Stage 1: Get engine from registry (enforced)
            engine = registry.get_instance(config.engine.name)
            
            # Stage 2: Get normalizer (config-driven)
            normalizer = self._get_normalizer(config.normalizer.type)
            normalizer_stage = NormalizerStage(normalizer)
            
            # Stage 3: Get parser (config-driven)
            parser_stage = ParserStage()
            
            # Stage 4: Similarity (core computation)
            similarity_stage = SimilarityStage()
            
            # Stage 5: Evaluation (pure comparison against truth)
            evaluation_stage = EvaluationStage()
            
            # Stage 6: Metrics (pure aggregation)
            metrics_stage = MetricsStage()
            
            # Stage 7: Reporting (pure output)
            reporting_stage = ReportingStage()
            
            # ===== Execute Pipeline DAG =====
            
            # Ground truth
            ground_truth = dataset.get_ground_truth()
            
            # For each pair, run through pipeline
            results: List[SimilarityResult] = []
            
            if config.threshold.optimize:
                # Stage 1: Normalize all code
                all_code = {}
                for pair in dataset.pairs:
                    if pair.id_a not in all_code:
                        raw_a = pair.code_a
                        normalized_a = normalizer_stage.execute([raw_a], {})[0]
                        all_code[pair.id_a] = normalized_a
                    if pair.id_b not in all_code:
                        raw_b = pair.code_b
                        normalized_b = normalizer_stage.execute([raw_b], {})[0]
                        all_code[pair.id_b] = normalized_b
                
                # Stage 2: Parse all code
                parsed: Dict[str, ParsedCode] = {}
                for code_id, normalized_code in all_code.items():
                    parsed[code_id] = parser_stage.execute(
                        (code_id, normalized_code),
                        {"type": config.parser.type}
                    )
                
                # Stage 3: Compute similarity for all pairs
                for pair in dataset.pairs:
                    code_a = parsed.get(pair.id_a)
                    code_b = parsed.get(pair.id_b)
                    if code_a and code_b:
                        result = similarity_stage.execute(
                            (code_a, code_b, engine),
                            {}
                        )
                        results.append(result)
                
                # Stage 4: Optimize threshold
                best_threshold = self._optimize_threshold(results, ground_truth, config.threshold.strategy)
            else:
                best_threshold = 0.5
                
                for pair in dataset.pairs:
                    raw_a = pair.code_a
                    raw_b = pair.code_b
                    
                    # Normalize
                    norm_a = normalizer_stage.execute([raw_a], {})[0]
                    norm_b = normalizer_stage.execute([raw_b], {})[0]
                    
                    # Parse
                    parsed_a = parser_stage.execute((pair.id_a, norm_a), {})
                    parsed_b = parser_stage.execute((pair.id_b, norm_b), {})
                    
                    # Similarity
                    result = similarity_stage.execute((parsed_a, parsed_b, engine), {})
                    results.append(result)
            
            # Stage 5: Evaluate against ground truth
            evaluated = evaluation_stage.execute(
                (results, ground_truth),
                {"threshold": best_threshold}
            )
            
            # Stage 6: Compute metrics
            metrics_config = {"threshold": best_threshold, "metrics": config.metrics.metrics}
            metrics = metrics_stage.execute(evaluated, metrics_config)
            metrics.threshold = best_threshold
            
            # Stage 7: Reporting
            pipeline_config = {
                "output": {
                    "json": config.output.json,
                    "html": config.output.html,
                    "leaderboard": config.output.leaderboard
                },
                "output_dir": "reports/json",
                "config_hash": config.config_hash()
            }
            report_paths = reporting_stage.execute(
                (metrics, {"engine": config.engine.name, "dataset": dataset.name}),
                pipeline_config
            )
            
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name,
                dataset_version=dataset.version,
                engine_name=config.engine.name,
                metrics=metrics,
                report_paths=report_paths,
                success=True
            )
            
        except Exception as e:
            return BenchmarkRunResult(
                config_hash=config.config_hash(),
                dataset_name=dataset.name,
                engine_name=config.engine.name,
                metrics=MetricsResult(),
                success=False,
                error=str(e)
            )
    
    def _get_normalizer(self, normalizer_type: str) -> Optional[Callable]:
        """Get normalizer function by type.
        
        Args:
            normalizer_type: Normalizer type string.
            
        Returns:
            Normalizer function.
        """
        # Default: identity function
        return lambda code: code.strip()
    
    def _optimize_threshold(
        self,
        results: List[SimilarityResult],
        ground_truth: Dict,
        strategy: str = "f1_max"
    ) -> float:
        """Find optimal threshold.
        
        Args:
            results: List of similarity results.
            ground_truth: Ground truth mapping.
            strategy: Optimization strategy.
            
        Returns:
            Optimal threshold value.
        """
        best_threshold = 0.5
        best_score = 0.0
        
        for t_int in range(0, 101):
            t = t_int / 100
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