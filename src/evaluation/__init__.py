"""
Evaluation Module - Metrics Only (No Execution Engines)

This module computes metrics and analysis only.
It does NOT contain execution engines or business logic.

Responsibility: Metrics computation, analysis, reporting, statistical testing
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np
from scipy import stats


class MetricType(Enum):
    """Types of metrics."""
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    ACCURACY = "accuracy"
    MAP = "map"
    MRR = "mrr"
    AUC = "auc"
    CUSTOM = "custom"


@dataclass
class MetricResult:
    """Result of a metric computation."""
    metric_type: MetricType
    value: float
    confidence_interval: Optional[Tuple[float, float]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Metric(ABC):
    """Base class for metrics."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def compute(self, predictions: List[Any], ground_truth: List[Any]) -> MetricResult:
        """Compute the metric."""
        pass
    
    def validate_inputs(self, predictions: List[Any], ground_truth: List[Any]) -> List[str]:
        """Validate inputs."""
        errors = []
        
        if len(predictions) != len(ground_truth):
            errors.append("Predictions and ground truth must have same length")
        
        if not predictions:
            errors.append("Predictions cannot be empty")
        
        return errors


class PrecisionMetric(Metric):
    """Precision metric."""
    
    def compute(self, predictions: List[Any], ground_truth: List[Any]) -> MetricResult:
        """Compute precision."""
        errors = self.validate_inputs(predictions, ground_truth)
        if errors:
            raise ValueError(f"Validation failed: {errors}")
        
        true_positives = sum(1 for p, gt in zip(predictions, ground_truth) if p == gt == 1)
        predicted_positives = sum(1 for p in predictions if p == 1)
        
        if predicted_positives == 0:
            precision = 0.0
        else:
            precision = true_positives / predicted_positives
        
        return MetricResult(
            metric_type=MetricType.PRECISION,
            value=precision,
            metadata={
                "true_positives": true_positives,
                "predicted_positives": predicted_positives,
            }
        )


class RecallMetric(Metric):
    """Recall metric."""
    
    def compute(self, predictions: List[Any], ground_truth: List[Any]) -> MetricResult:
        """Compute recall."""
        errors = self.validate_inputs(predictions, ground_truth)
        if errors:
            raise ValueError(f"Validation failed: {errors}")
        
        true_positives = sum(1 for p, gt in zip(predictions, ground_truth) if p == gt == 1)
        actual_positives = sum(1 for gt in ground_truth if gt == 1)
        
        if actual_positives == 0:
            recall = 0.0
        else:
            recall = true_positives / actual_positives
        
        return MetricResult(
            metric_type=MetricType.RECALL,
            value=recall,
            metadata={
                "true_positives": true_positives,
                "actual_positives": actual_positives,
            }
        )


class F1ScoreMetric(Metric):
    """F1 score metric."""
    
    def compute(self, predictions: List[Any], ground_truth: List[Any]) -> MetricResult:
        """Compute F1 score."""
        errors = self.validate_inputs(predictions, ground_truth)
        if errors:
            raise ValueError(f"Validation failed: {errors}")
        
        # Compute precision and recall
        precision_metric = PrecisionMetric("precision")
        recall_metric = RecallMetric("recall")
        
        precision_result = precision_metric.compute(predictions, ground_truth)
        recall_result = recall_metric.compute(predictions, ground_truth)
        
        precision = precision_result.value
        recall = recall_result.value
        
        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)
        
        return MetricResult(
            metric_type=MetricType.F1_SCORE,
            value=f1,
            metadata={
                "precision": precision,
                "recall": recall,
            }
        )


class MAPMetric(Metric):
    """Mean Average Precision metric."""
    
    def compute(self, predictions: List[List[Any]], ground_truth: List[List[Any]]) -> MetricResult:
        """Compute MAP."""
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")
        
        average_precisions = []
        
        for pred_list, gt_list in zip(predictions, ground_truth):
            if not pred_list or not gt_list:
                continue
            
            # Compute average precision for this query
            relevant_count = 0
            precision_sum = 0.0
            
            for i, pred in enumerate(pred_list):
                if pred in gt_list:
                    relevant_count += 1
                    precision_at_i = relevant_count / (i + 1)
                    precision_sum += precision_at_i
            
            if relevant_count > 0:
                average_precision = precision_sum / relevant_count
                average_precisions.append(average_precision)
        
        if not average_precisions:
            map_score = 0.0
        else:
            map_score = sum(average_precisions) / len(average_precisions)
        
        return MetricResult(
            metric_type=MetricType.MAP,
            value=map_score,
            metadata={
                "num_queries": len(average_precisions),
                "average_precisions": average_precisions,
            }
        )


class StatisticalTest:
    """Statistical testing utilities."""
    
    @staticmethod
    def paired_t_test(scores1: List[float], scores2: List[float]) -> Dict[str, Any]:
        """Perform paired t-test."""
        if len(scores1) != len(scores2):
            raise ValueError("Score lists must have same length")
        
        t_stat, p_value = stats.ttest_rel(scores1, scores2)
        
        return {
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "mean_diff": np.mean(scores1) - np.mean(scores2),
        }
    
    @staticmethod
    def wilcoxon_test(scores1: List[float], scores2: List[float]) -> Dict[str, Any]:
        """Perform Wilcoxon signed-rank test."""
        if len(scores1) != len(scores2):
            raise ValueError("Score lists must have same length")
        
        statistic, p_value = stats.wilcoxon(scores1, scores2)
        
        return {
            "statistic": statistic,
            "p_value": p_value,
            "significant": p_value < 0.05,
        }
    
    @staticmethod
    def bootstrap_confidence_interval(
        scores: List[float],
        n_bootstrap: int = 1000,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Compute bootstrap confidence interval."""
        bootstrap_means = []
        
        for _ in range(n_bootstrap):
            sample = np.random.choice(scores, size=len(scores), replace=True)
            bootstrap_means.append(np.mean(sample))
        
        alpha = 1 - confidence
        lower = np.percentile(bootstrap_means, 100 * alpha / 2)
        upper = np.percentile(bootstrap_means, 100 * (1 - alpha / 2))
        
        return (lower, upper)


class MetricRegistry:
    """Registry for metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
    
    def register(self, name: str, metric: Metric) -> None:
        """Register a metric."""
        self._metrics[name] = metric
    
    def get(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        return self._metrics.get(name)
    
    def list_metrics(self) -> List[str]:
        """List all registered metrics."""
        return list(self._metrics.keys())


# Global metric registry
registry = MetricRegistry()


def get_metric(name: str) -> Optional[Metric]:
    """Get a metric by name."""
    return registry.get(name)


def register_metric(name: str):
    """Decorator to register a metric."""
    def decorator(metric_class):
        registry.register(name, metric_class())
        return metric_class
    return decorator