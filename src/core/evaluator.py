"""Evaluation Engine - Phase 5. Pure evaluator (compare predictions vs labels)."""
from typing import List, Dict, Optional
from src.core.models import Prediction, MetricsResult, EvaluationReport

class Evaluator:
    """Pure evaluator - NO feature computation, NO fusion, NO threshold logic."""
    
    def evaluate(self, predictions: List[Prediction]) -> EvaluationReport:
        """Compare predictions vs ground truth labels."""
        tp = fp = fn = tn = 0
        preds_labeled = []
        fp_pairs = []
        fn_pairs = []
        
        for pred in predictions:
            if pred.label < 0:
                continue  # Skip unlabeled
            
            is_positive = pred.pred >= 1
            is_true = pred.label >= 1
            
            if is_positive and is_true:
                tp += 1
            elif is_positive and not is_true:
                fp += 1
                fp_pairs.append(pred.pair_id)
            elif not is_positive and is_true:
                fn += 1
                fn_pairs.append(pred.pair_id)
            else:
                tn += 1
            preds_labeled.append(pred)
        
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        
        metrics = MetricsResult(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn, tn=tn)
        
        return EvaluationReport(
            metrics=metrics,
            predictions=predictions,
            fp_pairs=fp_pairs,
            fn_pairs=fn_pairs,
        )
