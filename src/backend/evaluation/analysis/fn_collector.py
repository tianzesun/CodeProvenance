"""FN Collector - Collects false negatives from benchmark results."""
from typing import Dict, List, Any, Tuple
from pathlib import Path
import json

from benchmark.evaluator.standard import BenchmarkEvaluator


class FNCollector:
    """
    Collects FN pairs from benchmark evaluation results.
    
    Inputs benchmark predictions and ground truth, outputs
    structured FN list with code samples for classification.
    """
    
    def collect(
        self,
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        threshold: float = 0.5,
        code_store: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        Collect all false negative pairs.
        
        Args:
            predictions: [{"file1", "file2", "similarity"}, ...]
            ground_truth: {"pairs": [{"file1", "file2", "label"}, ...]}
            threshold: detection threshold
            code_store: {filepath: code_content} for feature extraction
        
        Returns:
            List of FN dicts with file1, file2, similarity, code1, code2
        """
        r = BenchmarkEvaluator.evaluate(predictions, ground_truth, threshold)
        
        # Build similarity lookup
        sim_lookup = {}
        for p in predictions:
            f1, f2 = p.get("file1", ""), p.get("file2", "")
            if f1 and f2:
                key = tuple(sorted([f1.strip(), f2.strip()]))
                sim = p.get("similarity", 0)
                if key not in sim_lookup or sim > sim_lookup[key]:
                    sim_lookup[key] = sim
        
        fn_list = []
        for fn_pair in r.false_negatives:
            code1 = (code_store or {}).get(fn_pair[0], "")
            code2 = (code_store or {}).get(fn_pair[1], "")
            
            fn_entry = {
                "file1": fn_pair[0],
                "file2": fn_pair[1],
                "similarity": sim_lookup.get(fn_pair, -1),
                "code1": code1,
                "code2": code2,
            }
            fn_list.append(fn_entry)
        
        return fn_list
    
    def collect_from_file(
        self, pred_path: Path, truth_path: Path,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Collect FNs from JSON files."""
        with open(pred_path) as f:
            predictions = json.load(f).get("pairs", json.load(f))
        with open(truth_path) as f:
            ground_truth = json.load(f)
        return self.collect(predictions, ground_truth, threshold)