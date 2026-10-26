"""Result schema for benchmark outputs.

Provides standardized result format for reproducibility and comparison.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EngineResult:
    """Result from a single engine."""
    engine_name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    map_score: float = 0.0
    mrr_score: float = 0.0
    ndcg_score: float = 0.0
    total_comparisons: int = 0
    threshold: float = 0.5


@dataclass
class DatasetMetadata:
    """Metadata for a benchmark dataset."""
    name: str
    version: str
    size: int
    language: str
    clone_types: list[int] = field(default_factory=list)
    description: str = ""


@dataclass
class BenchmarkResult:
    """Complete benchmark result.
    
    This is the canonical output format for all benchmark runs.
    """
    benchmark_name: str
    dataset: DatasetMetadata
    engine_results: list[EngineResult] = field(default_factory=list)
    timestamp: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def summary(self) -> dict[str, Any]:
        """Get summary of benchmark results.
        
        Returns:
            Summary dict with key metrics.
        """
        if not self.engine_results:
            return {}
        
        best_f1 = max(self.engine_results, key=lambda x: x.f1)
        return {
            "best_engine": best_f1.engine_name,
            "best_f1": best_f1.f1,
            "best_precision": best_f1.precision,
            "best_recall": best_f1.recall,
            "engines_tested": len(self.engine_results),
            "dataset": self.dataset.name,
            "total_comparisons": sum(e.total_comparisons for e in self.engine_results)
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Serializable dict.
        """
        return {
            "benchmark_name": self.benchmark_name,
            "dataset": asdict(self.dataset),
            "engine_results": [asdict(e) for e in self.engine_results],
            "summary": self.summary(),
            "timestamp": self.timestamp,
            "config": self.config
        }