"""
Advanced Evaluation Metrics - PRO5/topK.md spec.

- Top-K Precision/Recall: Precision@K = hits_in_top_K / K
- MAP (Mean Average Precision): ranking quality metric
- Fixed-threshold evaluation for fair tool comparison
- FN category analysis for training data
"""
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
import json


@dataclass
class TopKResults:
    """Results for Top-K evaluation."""
    precision_at_k: Dict[int, float]  # K -> Precision@K
    recall_at_k: Dict[int, float]     # K -> Recall@K
    hits_at_k: Dict[int, int]         # K -> number of hits


@dataclass
class MapResults:
    """Results for MAP/MRR evaluation."""
    map_score: float                  # Mean Average Precision
    mrr: float                        # Mean Reciprocal Rank
    ap_per_query: Dict[str, float]    # per-file AP scores


class AdvancedEvaluator:
    """
    Implements Top-K and MAP evaluation following topK.md spec.
    
    System output is: [(file1, file2, similarity)] sorted list
    Evaluates as a RANKING system, not binary classifier.
    """
    
    @staticmethod
    def _normalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        """Canonicalize: (A,B) == (B,A) -> sorted tuple."""
        f1 = f1.strip() if f1 else ""
        f2 = f2.strip() if f2 else ""
        return tuple(sorted([f1, f2]))
    
    @staticmethod
    def _build_truth_set(ground_truth: Dict[str, Any]) -> Set[Tuple[str, str]]:
        """Build set of relevant pairs (label=1)."""
        truth = set()
        for gt in ground_truth.get("pairs", []):
            if gt.get("label", 0) == 1:
                f1, f2 = gt.get("file1", ""), gt.get("file2", "")
                if f1 and f2:
                    truth.add(AdvancedEvaluator._normalize_pair(f1, f2))
        return truth
    
    @staticmethod
    def _sorted_and_deduped(predictions: List[Dict[str, Any]]) -> List[Tuple[str, str, float]]:
        """
        Sort by similarity desc, deduplicate by canonicalized pair.
        Returns list of (file1, file2, similarity).
        """
        sorted_preds = sorted(predictions, key=lambda x: x.get("similarity", 0), reverse=True)
        
        seen = set()
        result = []
        for p in sorted_preds:
            key = AdvancedEvaluator._normalize_pair(p.get("file1", ""), p.get("file2", ""))
            if key not in seen:
                seen.add(key)
                result.append((p.get("file1", ""), p.get("file2", ""), p.get("similarity", 0)))
        return result
    
    @staticmethod
    def top_k_evaluation(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        k_values: List[int] = None
    ) -> TopKResults:
        """
        Compute Top-K Precision and Recall.
        
        Top-K Precision = (# relevant in Top-K) / K
        Top-K Recall = (# relevant in Top-K) / (total relevant)
        
        Args:
            predictions: [{"file1", "file2", "similarity"}, ...]
            ground_truth: {"pairs": [{"file1", "file2", "label"}, ...]}
            k_values: List of K values (default [5, 10, 20, 50])
        """
        if k_values is None:
            k_values = [5, 10, 20, 50]
        
        truth_set = AdvancedEvaluator._build_truth_set(ground_truth)
        total_relevant = len(truth_set)
        
        sorted_pairs = AdvancedEvaluator._sorted_and_deduped(predictions)
        # Filter k_values to only those within data range
        max_k = len(sorted_pairs)
        k_values = [k for k in k_values if k <= max_k]
        
        # If no k_values are valid, add the last available k
        if not k_values and max_k > 0:
            k_values = [max_k]
        elif not k_values:
            return TopKResults(precision_at_k={}, recall_at_k={}, hits_at_k={})
        
        prec_at_k = {}
        rec_at_k = {}
        hits_at_k = {}
        
        cumulative_hits = 0
        for i, (f1, f2, sim) in enumerate(sorted_pairs):
            pair_key = AdvancedEvaluator._normalize_pair(f1, f2)
            if pair_key in truth_set:
                cumulative_hits += 1
            
            current_k = i + 1
            if current_k in k_values:
                prec_at_k[current_k] = round(cumulative_hits / current_k, 4)
                rec_at_k[current_k] = round(cumulative_hits / total_relevant, 4) if total_relevant else 0
                hits_at_k[current_k] = cumulative_hits
        
        return TopKResults(
            precision_at_k=prec_at_k,
            recall_at_k=rec_at_k,
            hits_at_k=hits_at_k,
        )
    
    @staticmethod
    def map_mrr_evaluation(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any]
    ) -> MapResults:
        """
        Compute MAP and MRR.
        
        Each unique file = one query.
        Candidates = all pairs involving that file, ranked by similarity.
        
        AP for query = sum(Precision@rank_k where hit) / total_relevant_for_query
        MAP = average AP across all queries with relevant results.
        MRR = average 1/first_relevant_rank.
        """
        truth_set = AdvancedEvaluator._build_truth_set(ground_truth)
        
        # Build truth per file (query -> set of relevant files)
        truth_per_file = {}
        for gt in ground_truth.get("pairs", []):
            if gt.get("label", 0) == 1:
                f1, f2 = gt.get("file1", ""), gt.get("file2", "")
                if f1 and f2:
                    truth_per_file.setdefault(f1, set()).add(f2)
                    truth_per_file.setdefault(f2, set()).add(f1)
        
        # Build per-file candidate lists (sorted by similarity desc)
        candidates_per_file = {}
        for p in predictions:
            f1, f2, sim = p.get("file1", ""), p.get("file2", ""), p.get("similarity", 0)
            if f1:
                candidates_per_file.setdefault(f1, []).append((f2, sim))
            if f2:
                candidates_per_file.setdefault(f2, []).append((f1, sim))
        
        # Sort each candidate list by similarity desc
        for qry in candidates_per_file:
            candidates_per_file[qry].sort(key=lambda x: x[1], reverse=True)
            # Deduplicate
            seen = set()
            unique = []
            for c, s in candidates_per_file[qry]:
                if c and c not in seen:
                    seen.add(c)
                    unique.append((c, s))
            candidates_per_file[qry] = unique
        
        ap_scores = {}
        rr_scores = {}
        
        for query_file, relevant_files in truth_per_file.items():
            if not relevant_files:
                continue  # skip queries with no relevant files
            
            candidates = candidates_per_file.get(query_file, [])
            if not candidates:
                ap_scores[query_file] = 0.0
                rr_scores[query_file] = 0.0
                continue
            
            # Compute AP
            num_relevant = 0
            sum_precisions = 0.0
            first_rank = -1
            
            for i, (candidate_file, sim) in enumerate(candidates):
                if candidate_file in relevant_files:
                    num_relevant += 1
                    prec_at_i = num_relevant / (i + 1)
                    sum_precisions += prec_at_i
                    if first_rank == -1:
                        first_rank = i + 1
            
            total_rel = len(relevant_files)
            ap = sum_precisions / total_rel if total_rel else 0
            ap_scores[query_file] = round(ap, 4)
            rr_scores[query_file] = round(1.0 / first_rank if first_rank > 0 else 0, 4)
        
        # MAP = mean of AP scores (only for queries with relevant results)
        map_score = sum(ap_scores.values()) / len(ap_scores) if ap_scores else 0
        mrr = sum(rr_scores.values()) / len(rr_scores) if rr_scores else 0
        
        return MapResults(
            map_score=round(map_score, 4),
            mrr=round(mrr, 4),
            ap_per_query=ap_scores,
        )
    
    @staticmethod
    def fixed_threshold_report(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        thresholds: List[float] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Evaluate at multiple fixed thresholds for fair tool comparison.
        
        Returns dict like:
        {
            "F1@0.3": {"precision": ..., "recall": ..., "f1": ..., "tp": ..., "fp": ..., "fn": ...},
            "F1@0.5": ...,
            ...
        }
        """
        if thresholds is None:
            thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        
        from benchmark.evaluator.standard import BenchmarkEvaluator
        results = {}
        
        for th in thresholds:
            r = BenchmarkEvaluator.evaluate(predictions, ground_truth, threshold=th, include_details=False)
            label = f"F1@{th:.1f}"
            results[label] = {
                "threshold": th,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "tp": r.tp,
                "fp": r.fp,
                "fn": r.fn,
            }
        
        return results
    
    @staticmethod
    def analyze_false_negatives(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        threshold: float = 0.5
    ) -> Dict[str, List[Tuple[str, str, float]]]:
        """
        Analyze false negatives by category.
        
        Categories:
        - "boundary": sim in [threshold-0.1, threshold) -> near miss
        - "low_similar": sim < threshold-0.1 -> far miss
        - "not_predicted": pair not in predictions at all
        """
        from benchmark.evaluator.standard import BenchmarkEvaluator
        
        r = BenchmarkEvaluator.evaluate(predictions, ground_truth, threshold, include_details=True)
        
        # Build similarity lookup
        sim_lookup = {}
        for p in predictions:
            key = BenchmarkEvaluator._normalize_pair(p.get("file1", ""), p.get("file2", ""))
            sim = p.get("similarity", 0)
            if key not in sim_lookup or sim > sim_lookup[key]:
                sim_lookup[key] = sim
        
        categories = {"boundary": [], "low_similar": [], "not_predicted": []}
        
        for fn_pair in r.false_negatives:
            sim = sim_lookup.get(fn_pair, -1)
            entry = (fn_pair[0], fn_pair[1], sim)
            if sim < 0:
                categories["not_predicted"].append(entry)
            elif sim >= threshold - 0.1:
                categories["boundary"].append(entry)
            else:
                categories["low_similar"].append(entry)
        
        return categories