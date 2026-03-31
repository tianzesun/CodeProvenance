"""Base runner class for benchmark execution."""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import time


@dataclass
class BenchmarkPair:
    id: str
    code_a: str
    code_b: str
    language: str
    is_clone: bool
    clone_type: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    benchmark_name: str
    tool_name: str
    total_pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    execution_time: float
    predictions: List[Tuple[str, float, bool]] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1_score(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def accuracy(self) -> float:
        total = self.true_positives + self.false_positives + self.false_negatives + self.true_negatives
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total

    def summary_dict(self) -> Dict[str, Any]:
        return {
            'benchmark_name': self.benchmark_name,
            'tool_name': self.tool_name,
            'total_pairs': self.total_pairs,
            'precision': round(self.precision, 4),
            'recall': round(self.recall, 4),
            'f1': round(self.f1_score, 4),
            'accuracy': round(self.accuracy, 4),
            'tp': self.true_positives,
            'fp': self.false_positives,
            'fn': self.false_negatives,
            'tn': self.true_negatives,
            'execution_time': round(self.execution_time, 2),
        }


class BaseRunner(ABC):
    def __init__(self, name: str, threshold: float = 0.5):
        self.name = name
        self.threshold = threshold

    @abstractmethod
    def load_dataset(self, dataset_path: Path) -> List[BenchmarkPair]:
        pass

    @abstractmethod
    def preprocess_code(self, code: str) -> str:
        pass

    @abstractmethod
    def run_comparison(self, pair: BenchmarkPair, similarity_threshold: float = 0.5) -> float:
        pass

    def evaluate(self, pairs: List[BenchmarkPair], threshold: Optional[float] = None) -> BenchmarkResult:
        threshold = threshold or self.threshold
        start_time = time.time()
        tp = fp = fn = tn = 0
        predictions = []
        for pair in pairs:
            score = self.run_comparison(pair, threshold)
            predicted_clone = score >= threshold
            predictions.append((pair.id, score, pair.is_clone))
            if pair.is_clone and predicted_clone:
                tp += 1
            elif not pair.is_clone and predicted_clone:
                fp += 1
            elif pair.is_clone and not predicted_clone:
                fn += 1
            else:
                tn += 1
        return BenchmarkResult(
            benchmark_name=self.name,
            tool_name="CodeProvenance",
            total_pairs=len(pairs),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            execution_time=time.time() - start_time,
            predictions=predictions,
        )
