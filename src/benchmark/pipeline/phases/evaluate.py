"""Phase 6: Metric Evaluation.

Evaluates aggregated results against ground truth:
- Compute precision, recall, F1
- Compute accuracy, MAP, MRR
- Optimize threshold

Input: AggregatedResult + ground truth
Output: EvaluationResult

Usage:
    from benchmark.pipeline.phases.evaluate import EvaluationPhase

    phase = EvaluationPhase()
    evaluation = phase.execute(aggregated_result, config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvaluationResult:
    """Evaluation result with metrics.
    
    Attributes:
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        accuracy: Accuracy score.
        map_score: Mean Average Precision.
        mrr_score: Mean Reciprocal Rank.
        threshold: Optimized threshold.
        tp: True positives.
        fp: False positives.
        tn: True negatives.
        fn: False negatives.
        metadata: Additional metadata.
    """
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
    map_score: float = 0.0
    mrr_score: float = 0.0
    threshold: float = 0.5
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "EVALUATION RESULT",
            "=" * 70,
            "",
            f"Threshold: {self.threshold:.2f}",
            f"Precision:  {self.precision:.4f}",
            f"Recall:     {self.recall:.4f}",
            f"F1 Score:   {self.f1:.4f}",
            f"Accuracy:   {self.accuracy:.4f}",
            f"MAP Score:  {self.map_score:.4f}",
            f"MRR Score:  {self.mrr_score:.4f}",
            "",
            "CONFUSION MATRIX:",
            f"  TP: {self.tp}  FP: {self.fp}",
            f"  FN: {self.fn}  TN: {self.tn}",
            "",
            "=" * 70,
        ]
        return "\n".join(lines)


class EvaluationPhase:
    """Phase 6: Metric Evaluation.
    
    This phase is responsible for:
    - Computing classification metrics
    - Computing ranking metrics
    - Optimizing decision threshold
    
    Input: AggregatedResult from aggregation phase + ground truth
    Output: EvaluationResult with all metrics
    
    Usage:
        phase = EvaluationPhase()
        evaluation = phase.execute(aggregated_result, config)
    """
    
    def execute(
        self,
        aggregated_result: Any,
        config: Dict[str, Any],
    ) -> EvaluationResult:
        """Execute evaluation phase.
        
        Args:
            aggregated_result: AggregatedResult from aggregation phase.
            config: Configuration for evaluation.
                - ground_truth: Ground truth mapping
                - optimize_threshold: Whether to optimize threshold (default: True)
                - threshold_strategy: Strategy for optimization (default: f1_max)
            
        Returns:
            EvaluationResult with all metrics.
        """
        ground_truth = config.get('ground_truth', {})
        optimize_threshold = config.get('optimize_threshold', True)
        threshold_strategy = config.get('threshold_strategy', 'f1_max')
        
        # Get all results
        all_results = []
        for engine_name, results in getattr(aggregated_result, 'results_by_engine', {}).items():
            all_results.extend(results)
        
        # Optimize threshold if enabled
        if optimize_threshold:
            threshold = self._optimize_threshold(
                all_results, ground_truth, threshold_strategy
            )
        else:
            threshold = config.get('threshold', 0.5)
        
        # Compute confusion matrix
        tp, fp, tn, fn = self._compute_confusion_matrix(
            all_results, ground_truth, threshold
        )
        
        # Compute metrics
        precision = self._precision(tp, fp)
        recall = self._recall(tp, fn)
        f1 = self._f1_score(precision, recall)
        accuracy = self._accuracy(tp, tn, fp, fn)
        
        # Compute ranking metrics
        map_score = self._compute_map(all_results, ground_truth)
        mrr_score = self._compute_mrr(all_results, ground_truth)
        
        return EvaluationResult(
            precision=precision,
            recall=recall,
            f1=f1,
            accuracy=accuracy,
            map_score=map_score,
            mrr_score=mrr_score,
            threshold=threshold,
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            metadata={
                'total_pairs': len(all_results),
                'optimize_threshold': optimize_threshold,
                'threshold_strategy': threshold_strategy,
            },
        )
    
    def _optimize_threshold(
        self,
        results: List[Any],
        ground_truth: Dict,
        strategy: str = 'f1_max',
    ) -> float:
        """Optimize threshold by maximizing F1 or precision.
        
        Args:
            results: List of comparison results.
            ground_truth: Ground truth mapping.
            strategy: Optimization strategy (f1_max or precision_max).
            
        Returns:
            Optimal threshold value.
        """
        best_threshold = 0.5
        best_score = 0.0
        
        for t_int in range(0, 101):
            t = t_int / 100.0
            tp, fp, tn, fn = self._compute_confusion_matrix(results, ground_truth, t)
            
            precision = self._precision(tp, fp)
            recall = self._recall(tp, fn)
            f1 = self._f1_score(precision, recall)
            
            score = f1 if strategy == 'f1_max' else precision
            
            if score > best_score:
                best_score = score
                best_threshold = t
        
        return best_threshold
    
    def _compute_confusion_matrix(
        self,
        results: List[Any],
        ground_truth: Dict,
        threshold: float,
    ) -> tuple:
        """Compute confusion matrix.
        
        Args:
            results: List of comparison results.
            ground_truth: Ground truth mapping.
            threshold: Decision threshold.
            
        Returns:
            Tuple of (tp, fp, tn, fn).
        """
        tp = fp = tn = fn = 0
        
        for result in results:
            code_a_id = getattr(result, 'code_a_id', '')
            code_b_id = getattr(result, 'code_b_id', '')
            score = getattr(result, 'similarity_score', 0.0)
            
            # Get ground truth
            key = (code_a_id, code_b_id)
            label = ground_truth.get(key, ground_truth.get((code_b_id, code_a_id), 0))
            
            # Predict
            predicted = 1 if score >= threshold else 0
            
            # Update confusion matrix
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 0:
                tn += 1
            else:
                fn += 1
        
        return tp, fp, tn, fn
    
    def _precision(self, tp: int, fp: int) -> float:
        """Compute precision.
        
        Args:
            tp: True positives.
            fp: False positives.
            
        Returns:
            Precision score.
        """
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    def _recall(self, tp: int, fn: int) -> float:
        """Compute recall.
        
        Args:
            tp: True positives.
            fn: False negatives.
            
        Returns:
            Recall score.
        """
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    def _f1_score(self, precision: float, recall: float) -> float:
        """Compute F1 score.
        
        Args:
            precision: Precision score.
            recall: Recall score.
            
        Returns:
            F1 score.
        """
        return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    def _accuracy(self, tp: int, tn: int, fp: int, fn: int) -> float:
        """Compute accuracy.
        
        Args:
            tp: True positives.
            tn: True negatives.
            fp: False positives.
            fn: False negatives.
            
        Returns:
            Accuracy score.
        """
        total = tp + tn + fp + fn
        return (tp + tn) / total if total > 0 else 0.0
    
    def _compute_map(self, results: List[Any], ground_truth: Dict) -> float:
        """Compute Mean Average Precision.
        
        Args:
            results: List of comparison results.
            ground_truth: Ground truth mapping.
            
        Returns:
            MAP score.
        """
        # Group by query (code_a_id)
        query_results = {}
        for result in results:
            code_a_id = getattr(result, 'code_a_id', '')
            if code_a_id not in query_results:
                query_results[code_a_id] = []
            query_results[code_a_id].append(result)
        
        # Compute AP for each query
        aps = []
        for query_id, query_result in query_results.items():
            # Sort by score descending
            sorted_results = sorted(
                query_result,
                key=lambda r: getattr(r, 'similarity_score', 0.0),
                reverse=True,
            )
            
            # Compute AP
            ap = 0.0
            relevant_count = 0
            for i, result in enumerate(sorted_results):
                code_b_id = getattr(result, 'code_b_id', '')
                key = (query_id, code_b_id)
                label = ground_truth.get(key, ground_truth.get((code_b_id, query_id), 0))
                
                if label == 1:
                    relevant_count += 1
                    ap += relevant_count / (i + 1)
            
            if relevant_count > 0:
                ap /= relevant_count
            aps.append(ap)
        
        return sum(aps) / len(aps) if aps else 0.0
    
    def _compute_mrr(self, results: List[Any], ground_truth: Dict) -> float:
        """Compute Mean Reciprocal Rank.
        
        Args:
            results: List of comparison results.
            ground_truth: Ground truth mapping.
            
        Returns:
            MRR score.
        """
        # Group by query (code_a_id)
        query_results = {}
        for result in results:
            code_a_id = getattr(result, 'code_a_id', '')
            if code_a_id not in query_results:
                query_results[code_a_id] = []
            query_results[code_a_id].append(result)
        
        # Compute RR for each query
        rrs = []
        for query_id, query_result in query_results.items():
            # Sort by score descending
            sorted_results = sorted(
                query_result,
                key=lambda r: getattr(r, 'similarity_score', 0.0),
                reverse=True,
            )
            
            # Find first relevant result
            rr = 0.0
            for i, result in enumerate(sorted_results):
                code_b_id = getattr(result, 'code_b_id', '')
                key = (query_id, code_b_id)
                label = ground_truth.get(key, ground_truth.get((code_b_id, query_id), 0))
                
                if label == 1:
                    rr = 1.0 / (i + 1)
                    break
            
            rrs.append(rr)
        
        return sum(rrs) / len(rrs) if rrs else 0.0