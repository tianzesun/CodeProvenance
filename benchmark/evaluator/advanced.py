"""
Advanced Evaluation Metrics - PRO5 Enhancements.

Adds:
1. Fixed-threshold multi-point evaluation (F1@0.5, F1@0.6, F1@0.7)
2. Top-K Precision/Recall
3. MAP (Mean Average Precision) / MRR (Mean Reciprocal Rank)
4. FN category analysis for training data
"""
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class FixedThresholdResult:
    """Result at multiple fixed thresholds."""
    thresholds: Dict[str, Dict[str, float]]  # threshold -> {precision, recall, f1}


@dataclass
class TopKResult:
    """Top-K evaluation result."""
    k: int
    precision: float
    recall: float
    tp: int
    hits: List[Tuple[str, str, float]]  # top-k hits


@dataclass
class MapResult:
    """MAP/MRR evaluation result."""
    map_score: float
    mrr: float
    ap_per_query: Dict[str, float] = field(default_factory=dict)


@dataclass
class FNAnalysis:
    """False negative analysis by category."""
    fn_list: List[Tuple[str, str, float]] = field(default_factory=list)
    categories: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)


class AdvancedEvaluator:
    """
    Extended evaluator with industry-standard metrics.
    
    Adds:
    - Fixed-threshold multi-point evaluation
    - Top-K Precision/Recall
    - MAP/MRR ranking metrics
    - FN category analysis
    """
    
    @staticmethod
    def fixed_threshold_report(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        thresholds: List[float] = None
    ) -> FixedThresholdResult:
        """
        Evaluate at multiple fixed thresholds for fair comparison.
        
        Args:
            predictions: List of {"file1", "file2", "similarity"}
            ground_truth: {"pairs": [{"file1", "file2", "label"}]}
            thresholds: List of fixed thresholds (default [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
            
        Returns:
            FixedThresholdResult with metrics at each threshold
        """
        if thresholds is None:
            thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        
        from benchmark.evaluator.standard import BenchmarkEvaluator
        results = {}
        
        for th in thresholds:
            r = BenchmarkEvaluator.evaluate(predictions, ground_truth, threshold=th, include_details=False)
            results[f"F1@{th:.1f}"] = {
                "threshold": th,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "tp": r.tp,
                "fp": r.fp,
                "fn": r.fn,
            }
        
        return FixedThresholdResult(thresholds=results)
    
    @staticmethod
    def top_k_evaluation(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        k_values: List[int] = None
    ) -> Dict[int, TopKResult]:
        """
        Evaluate Top-K Precision and Recall.
        
        Args:
            predictions: List of {"file1", "file2", "similarity"}
            ground_truth: {"pairs": [{"file1", "file2", "label"}]}
            k_values: List of K values (default [5, 10, 20, 50])
            
        Returns:
            Dict mapping K to TopKResult
        """
        if k_values is None:
            k_values = [5, 10, 20, 50]
        
        # Build truth set
        truth_pairs = set()
        for gt in ground_truth.get("pairs", []):
            if gt.get("label", 0) == 1:
                f1, f2 = gt["file1"].strip(), gt["file2"].strip()
                truth_pairs.add(tuple(sorted([f1, f2])))
        
        # Sort predictions by similarity descending
        sorted_preds = sorted(predictions, key=lambda x: x.get("similarity", 0), reverse=True)
        
        # Deduplicate
        seen = set()
        unique_preds = []
        for p in sorted_preds:
            key = tuple(sorted([p.get("file1", ""), p.get("file2", "")]))
            if key not in seen:
                seen.add(key)
                unique_preds.append(p)
        
        results = {}
        for k in k_values:
            top_k = unique_preds[:k]
            hits = []
            for p in top_k:
                key = tuple(sorted([p.get("file1", ""), p.get("file2", "")]))
                if key in truth_pairs:
                    hits.append((p.get("file1"), p.get("file2"), p.get("similarity")))
            
            tp = len(hits)
            precision = tp / k if k else 0
            recall = tp / len(truth_pairs) if truth_pairs else 0
            
            results[k] = TopKResult(k=k, precision=round(precision, 4),
                                    recall=round(recall, 4), tp=tp, hits=hits)
        
        return results
    
    @staticmethod
    def map_mrr_evaluation(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any]
    ) -> MapResult:
        """
        Compute MAP and MRR for ranking evaluation.
        
        Treats each unique file as a "query" and evaluates ranking of its clones.
        
        Args:
            predictions: List of {"file1", "file2", "similarity"}
            ground_truth: {"pairs": [{"file1", "file2", "label"}]}
            
        Returns:
            MapResult with MAP and MRR scores
        """
        # Build truth per file
        truth_per_file = {}
        for gt in ground_truth.get("pairs", []):
            if gt.get("label", 0) == 1:
                f1, f2 = gt["file1"].strip(), gt["file2"].strip()
                truth_per_file.setdefault(f1, set()).add(f2)
                truth_per_file.setdefault(f2, set()).add(f1)
        
        # Sort all predictions by similarity
        sorted_preds = sorted(predictions, key=lambda x: x.get("similarity", 0), reverse=True)
        
        ap_scores = {}
        rr_scores = {}
        
        for query_file, relevant_files in truth_per_file.items():
            # Get sorted candidate files for this query
            candidates = []
            for p in sorted_preds:
                if p.get("file1", "") == query_file:
                    candidates.append(p.get("file2", ""))
                elif p.get("file2", "") == query_file:
                    candidates.append(p.get("file1", ""))
            
            # Unique ranked list
            seen = set()
            ranked = []
            for c in candidates:
                if c and c not in seen:
                    seen.add(c)
                    ranked.append(c)
            
            if not ranked:
                ap_scores[query_file] = 0.0
                rr_scores[query_file] = 0.0
                continue
            
            # Compute AP
            num_relevant = 0
            sum_precisions = 0.0
            first_rank = -1
            
            for i, candidate in enumerate(ranked):
                if candidate in relevant_files:
                    num_relevant += 1
                    precision_at_i = num_relevant / (i + 1)
                    sum_precisions += precision_at_i
                    if first_rank == -1:
                        first_rank = i + 1
            
            ap = sum_precisions / len(relevant_files) if relevant_files else 0
            ap_scores[query_file] = round(ap, 4)
            rr_scores[query_file] = round(1.0 / first_rank if first_rank > 0 else 0, 4)
        
        map_score = sum(ap_scores.values()) / len(ap_scores) if ap_scores else 0
        mrr = sum(rr_scores.values()) / len(rr_scores) if rr_scores else 0
        
        return MapResult(
            map_score=round(map_score, 4),
            mrr=round(mrr, 4),
            ap_per_query=ap_scores,
        )
    
    @staticmethod
    def analyze_false_negatives(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        threshold: float = 0.5
    ) -> FNAnalysis:
        """
        Analyze false negatives with category hints.
        
        Categories (based on similarity proximity to threshold):
        - "boundary": similarity in [threshold - 0.1, threshold) - near miss
        - "low_similar": similarity < threshold - 0.1 - far miss
        - "not_predicted": pair not in predictions at all
        
        Args:
            predictions: List of {"file1", "file2", "similarity"}
            ground_truth: {"pairs": [{"file1", "file2", "label"}]}
            threshold: Detection threshold
            
        Returns:
            FNAnalysis with categorized FN list
        """
        from benchmark.evaluator.standard import BenchmarkEvaluator
        
        # Get FN pairs
        r = BenchmarkEvaluator.evaluate(predictions, ground_truth, threshold, include_details=True)
        
        # Build similarity lookup for FN pairs
        sim_lookup = {}
        for p in predictions:
            key = BenchmarkEvaluator._normalize_pair(p.get("file1", ""), p.get("file2", ""))
            sim = p.get("similarity", 0)
            if key not in sim_lookup or sim > sim_lookup[key]:
                sim_lookup[key] = sim
        
        analysis = FNAnalysis()
        for fn_pair in r.false_negatives:
            sim = sim_lookup.get(fn_pair, -1)
            analysis.fn_list.append((fn_pair[0], fn_pair[1], sim))
            
            if sim < 0:
                cat = "not_predicted"
            elif sim >= threshold - 0.1:
                cat = "boundary"  # Near miss
            else:
                cat = "low_similar"  # Far miss
            
            analysis.categories.setdefault(cat, []).append(fn_pair)
        
        return analysis