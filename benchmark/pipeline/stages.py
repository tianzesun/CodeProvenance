"""Pipeline stages for the unified evaluation pipeline.

Each stage is a pure function: output = stage(input, config) -> output
No backward dependencies. Only forward flow allowed.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field


# =============================================================================
# Data structures for pipeline flow
# =============================================================================

@dataclass
class ParsedCode:
    """Structured representation of parsed code."""
    code_id: str
    tokens: List[str] = field(default_factory=list)
    ast: Any = None
    raw_code: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if parsed code is valid."""
        return bool(self.tokens) or self.ast is not None


@dataclass
class SimilarityResult:
    """Result of a similarity comparison."""
    id_a: str
    id_b: str
    score: float  # [0, 1]
    label: Optional[int] = None
    engine_name: str = ""


@dataclass
class MetricsResult:
    """Aggregated metrics from evaluation."""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
    map_score: float = 0.0
    mrr_score: float = 0.0
    ndcg: float = 0.0
    top_k_precision: float = 0.0
    threshold: float = 0.5
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0


# =============================================================================
# Pipeline Stage Interface
# =============================================================================

class PipelineStage(ABC):
    """Abstract base for all pipeline stages.
    
    Each stage is:
    - Pure function (no side effects)
    - Stateless (given same inputs -> same outputs)
    - Deterministic
    
    The only allowed flow is forward:
    Config -> Dataset -> Normalizer -> Parser -> Similarity -> Evaluation -> Metrics -> Reporting
    """
    
    @abstractmethod
    def name(self) -> str:
        """Return stage name."""
        pass
    
    @abstractmethod
    def execute(self, input_data: Any, config: Dict[str, Any]) -> Any:
        """Execute stage with input data.
        
        Args:
            input_data: Input from previous stage.
            config: Configuration for this stage.
            
        Returns:
            Output for next stage.
        """
        pass


# =============================================================================
# Stage Implementations
# =============================================================================

class NormalizerStage(PipelineStage):
    """Stage: Normalize raw code before parsing.
    
    Responsibility:
    - Remove comments
    - Normalize whitespace
    - Optionally rename identifiers
    
    Input: List[str] (raw code strings)
    Output: List[str] (normalized code strings)
    """
    
    @property
    def name(self) -> str:
        return "normalizer"
    
    def __init__(self, normalizer_func=None):
        self._normalizer_func = normalizer_func
    
    def execute(self, input_data: List[str], config: Dict[str, Any]) -> List[str]:
        if self._normalizer_func:
            return [self._normalizer_func(code) for code in input_data]
        # Default: strip whitespace
        return [code.strip() for code in input_data]


class ParserStage(PipelineStage):
    """Stage: Parse normalized code into structured representation.
    
    Responsibility:
    - Parse code into tokens and/or AST
    
    Input: str (normalized code)
    Output: ParsedCode (tokens + AST)
    """
    
    @property
    def name(self) -> str:
        return "parser"
    
    def execute(self, input_data: Tuple[str, str], config: Dict[str, Any]) -> ParsedCode:
        code_id, code = input_data
        # Parse into tokens and AST
        return ParsedCode(
            code_id=code_id,
            tokens=code.split(),
            raw_code=code,
            metadata=config.get("metadata", {})
        )


class SimilarityStage(PipelineStage):
    """Stage: Compute similarity between two code samples.
    
    Responsibility:
    - Compare two ParsedCode objects
    - Return similarity score in [0, 1]
    
    Input: (ParsedCode, ParsedCode)
    Output: float [0, 1]
    """
    
    @property
    def name(self) -> str:
        return "similarity"
    
    def execute(
        self,
        input_data: Tuple[ParsedCode, ParsedCode, Any],
        config: Dict[str, Any]
    ) -> SimilarityResult:
        code_a, code_b, engine = input_data
        score = engine.compare(code_a.raw_code, code_b.raw_code)
        
        return SimilarityResult(
            id_a=code_a.code_id,
            id_b=code_b.code_id,
            score=score,
            engine_name=engine.name() if hasattr(engine, 'name') else ""
        )


class EvaluationStage(PipelineStage):
    """Stage: Evaluate similarity results against ground truth.
    
    Responsibility:
    - Convert similarity scores to predictions
    - Compare with ground truth labels
    
    Two modes:
    - Pairwise: (code_a, code_b, label) -> (score, prediction)
    - Ranking: query -> ranked candidates
    
    Input: List[SimilarityResult] + ground truth
    Output: List[SimilarityResult] with labels
    """
    
    @property
    def name(self) -> str:
        return "evaluation"
    
    def execute(
        self,
        input_data: Tuple[List[SimilarityResult], Dict[Tuple[str, str], int]],
        config: Dict[str, Any]
    ) -> List[SimilarityResult]:
        results, ground_truth = input_data
        threshold = config.get("threshold", 0.5)
        
        for result in results:
            key = (result.id_a, result.id_b)
            result.label = ground_truth.get(key, ground_truth.get((result.id_b, result.id_a), 0))
        
        return results


class MetricsStage(PipelineStage):
    """Stage: Compute aggregate metrics from evaluation results.
    
    Responsibility:
    - Convert predictions into statistics
    - Compute precision, recall, F1, MAP, MRR
    
    Input: List[SimilarityResult]
    Output: MetricsResult
    """
    
    @property
    def name(self) -> str:
        return "metrics"
    
    def execute(
        self,
        input_data: List[SimilarityResult],
        config: Dict[str, Any]
    ) -> MetricsResult:
        from benchmark.metrics import precision, recall, f1_score, accuracy
        from benchmark.metrics import mean_average_precision, mean_reciprocal_rank
        
        # Classification metrics
        tp = sum(1 for r in input_data if r.score >= config.get("threshold", 0.5) and r.label == 1)
        fp = sum(1 for r in input_data if r.score >= config.get("threshold", 0.5) and r.label == 0)
        tn = sum(1 for r in input_data if r.score < config.get("threshold", 0.5) and r.label == 0)
        fn = sum(1 for r in input_data if r.score < config.get("threshold", 0.5) and r.label == 1)
        
        prec = precision(tp, fp)
        rec = recall(tp, fn)
        f1 = f1_score(prec, rec)
        acc = accuracy(tp, tn, fp, fn)
        
        # Ranking metrics
        query_results = {}
        for r in input_data:
            if r.id_a not in query_results:
                query_results[r.id_a] = []
            query_results[r.id_a].append((r.id_b, r.score, r.label or 0))
        
        map_score = mean_average_precision(query_results)
        mrr_score = mean_reciprocal_rank(query_results)
        
        return MetricsResult(
            precision=prec,
            recall=rec,
            f1=f1,
            accuracy=acc,
            map_score=map_score,
            mrr_score=mrr_score,
            threshold=config.get("threshold", 0.5),
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn
        )


class ReportingStage(PipelineStage):
    """Stage: Generate reports from metrics.
    
    Responsibility:
    - Write JSON (authoritative)
    - Write HTML (human readable)
    - Update leaderboard
    
    Input: MetricsResult + config
    Output: Report file paths
    """
    
    @property
    def name(self) -> str:
        return "reporting"
    
    def execute(
        self,
        input_data: Tuple[MetricsResult, Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, str]:
        from datetime import datetime
        
        metrics, extra_info = input_data
        output_dir = config.get("output_dir", "reports/json")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        paths = {}
        
        if config.get("output", {}).get("json", True):
            from benchmark.reporting import JSONReportWriter
            writer = JSONReportWriter(f"{output_dir}/benchmark_{timestamp}.json")
            paths["json"] = writer.write(
                results={
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "accuracy": metrics.accuracy,
                },
                metadata={"threshold": metrics.threshold, "config_hash": config.get("config_hash", "")}
            )
        
        return paths