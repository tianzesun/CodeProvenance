"""
Dataset Builder - Generate training data from classified FNs.

Converts FN classification results into training data format
for model fine-tuning.

From FN.md:
- FNs -> label=1 (positive samples)
- FPs -> label=0 (negative samples)
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class TrainingSample:
    """A single training sample."""
    file1: str
    file2: str
    label: int  # 1=clone, 0=non-clone
    categories: List[str]
    features: Dict[str, float]
    similarity_at_detection: float


class DatasetBuilder:
    """
    Build training datasets from FN analysis results.
    
    Pipeline:
    1. Collect FNs (label=1) and FPs (label=0)
    2. Extract features
    3. Classify FNs
    4. Output training data JSON
    """
    
    def build_from_analysis(self, fn_analysis, fp_list: List[Dict]) -> List[TrainingSample]:
        """
        Build training data from FN analysis and FP list.
        
        Args:
            fn_analysis: FNAnalysis results
            fp_list: List of FP dicts with file1, file2, similarity
        
        Returns:
            List of TrainingSample
        """
        samples = []
        
        # Add FN samples as positive (label=1)
        for r in fn_analysis.results:
            samples.append(TrainingSample(
                file1=r.file1,
                file2=r.file2,
                label=1,
                categories=r.labels,
                features=r.features,
                similarity_at_detection=r.similarity,
            ))
        
        # Add FP samples as negative (label=0)
        for fp in fp_list:
            samples.append(TrainingSample(
                file1=fp.get("file1", ""),
                file2=fp.get("file2", ""),
                label=0,
                categories=["false_positive"],
                features=fp.get("features", {}),
                similarity_at_detection=fp.get("similarity", 0),
            ))
        
        return samples
    
    def save(self, samples: List[TrainingSample], path: Path) -> None:
        """Save training data to JSON file."""
        data = {
            "num_samples": len(samples),
            "num_positive": sum(1 for s in samples if s.label == 1),
            "num_negative": sum(1 for s in samples if s.label == 0),
            "samples": [
                {
                    "file1": s.file1,
                    "file2": s.file2,
                    "label": s.label,
                    "categories": s.categories,
                    "features": s.features,
                    "similarity_at_detection": s.similarity_at_detection,
                }
                for s in samples
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)