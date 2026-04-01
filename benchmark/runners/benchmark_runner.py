"""Main benchmark orchestrator.

Coordinates the execution of benchmark runs across datasets and engines.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from benchmark.registry import registry
from benchmark.reporting import JSONReportWriter, Leaderboard, LeaderboardEntry
from benchmark.schemas.result_schema import BenchmarkResult, DatasetMetadata, EngineResult
from benchmark.evaluation.pairwise import evaluate_pairwise, aggregate_pairwise_results
from benchmark.evaluation.ranking import mean_average_precision, mean_reciprocal_rank


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    dataset_name: str
    dataset_version: str
    engines: List[str]
    threshold: float = 0.5
    ground_truth_path: Optional[str] = None


class BenchmarkRunner:
    """Main benchmark runner that orchestrates evaluation.
    
    Usage:
        config = BenchmarkConfig(
            dataset_name="bigclonebench",
            dataset_version="v1",
            engines=["similarity", "ast"]
        )
        runner = BenchmarkRunner(config)
        result = runner.run(data_pairs, ground_truth)
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.report_writer = JSONReportWriter(f"reports/json/benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self.leaderboard = Leaderboard()
    
    def run(
        self,
        data_pairs: List[Dict[str, Any]],
        ground_truth: Dict
    ) -> BenchmarkResult:
        """Run benchmark with configured engines.
        
        Args:
            data_pairs: List of data pair dicts with file1, file2, code1, code2.
            ground_truth: Ground truth dict.
            
        Returns:
            BenchmarkResult with all engine results.
        """
        dataset_meta = DatasetMetadata(
            name=self.config.dataset_name,
            version=self.config.dataset_version,
            size=len(data_pairs),
            language="java"
        )
        
        result = BenchmarkResult(
            benchmark_name="code_similarity",
            dataset=dataset_meta,
            config={"threshold": self.config.threshold}
        )
        
        for engine_name in self.config.engines:
            engine_result = self._run_engine(engine_name, data_pairs, ground_truth)
            result.engine_results.append(engine_result)
            
            # Update leaderboard
            lb_entry = LeaderboardEntry(
                engine=engine_name,
                dataset=self.config.dataset_name,
                precision=engine_result.precision,
                recall=engine_result.recall,
                f1=engine_result.f1,
                map_score=engine_result.map_score,
                mrr_score=engine_result.mrr_score,
                config={"threshold": self.config.threshold}
            )
            self.leaderboard.add(lb_entry)
        
        # Save outputs
        self.report_writer.write(result.to_dict())
        self.leaderboard.save()
        
        return result
    
    def _run_engine(
        self,
        engine_name: str,
        data_pairs: List[Dict[str, Any]],
        ground_truth: Dict
    ) -> EngineResult:
        """Run a single engine and evaluate results.
        
        Args:
            engine_name: Registered engine name.
            data_pairs: Data pairs to evaluate.
            ground_truth: Ground truth for evaluation.
            
        Returns:
            EngineResult with metrics.
        """
        engine = registry.get_instance(engine_name)
        
        scores_and_labels = []
        predictions = []
        
        for pair in data_pairs:
            score = engine.compare(pair['code1'], pair['code2'])
            f1, f2 = pair['file1'], pair['file2']
            predictions.append({
                'file1': f1,
                'file2': f2,
                'score': score,
                'engine': engine_name
            })
            
            actual = ground_truth.get((f1, f2), ground_truth.get((f2, f1), 0))
            scores_and_labels.append((score, actual))
        
        pairwise_results = evaluate_pairwise(predictions, ground_truth, self.config.threshold)
        aggregated = aggregate_pairwise_results(pairwise_results)
        
        return EngineResult(
            engine_name=engine_name,
            precision=aggregated['precision'],
            recall=aggregated['recall'],
            f1=aggregated['f1'],
            accuracy=aggregated['accuracy'],
            total_comparisons=len(data_pairs),
            threshold=self.config.threshold
        )