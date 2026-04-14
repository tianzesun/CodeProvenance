"""Ground truth labeled dataset for benchmark evaluation.

Creates labeled code pair datasets for evaluating plagiarism detectors
using formal metrics: precision, recall, F1, ROC-AUC, PR-AUC, and robustness.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json

from src.backend.benchmark.datasets.schema import CodePair, GroundTruthLabel


# Ground truth labels: 0=unrelated, 1=weak, 2=semantic clone, 3=exact clone
class Label:
    UNRELATED = 0
    WEAK_SIMILARITY = 1
    SEMANTIC_CLONE = 2
    EXACT_CLONE = 3


@dataclass
class BenchmarkGroundTruth:
    """Ground truth for benchmark evaluation.
    
    Each pair has a label indicating the type of similarity:
    - 0 (UNRELATED): Completely different code
    - 1 (WEAK_SIMILARITY): Some lexical similarity but independent work
    - 2 (SEMANTIC_CLONE): Same logic, different implementation  
    - 3 (EXACT_CLONE): Identical or near-identical code
    """
    name: str
    version: str
    language: str
    pairs: List[CodePair] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def binary_labels(self) -> List[int]:
        """Convert to binary: clone (1) vs non-clone (0)."""
        return [1 if p.label >= Label.SEMANTIC_CLONE else 0 for p in self.pairs]
    
    @property
    def multi_class_labels(self) -> List[int]:
        """Multi-class labels (0-3)."""
        return [p.label for p in self.pairs]
    
    def get_scores_by_label(self) -> Dict[int, List[int]]:
        """Group labels for analysis."""
        result = {0: [], 1: [], 2: [], 3: []}
        for p in self.pairs:
            result[p.label].append(p)
        return result
    
    def save(self, path: Path):
        """Save to JSON."""
        data = {
            "name": self.name,
            "version": self.version,
            "language": self.language,
            "metadata": self.metadata,
            "pairs": [
                {
                    "id_a": p.id_a,
                    "id_b": p.id_b,
                    "label": p.label,
                    "code_a": p.code_a[:500] if len(p.code_a) > 500 else p.code_a,
                    "code_b": p.code_b[:500] if len(p.code_b) > 500 else p.code_b,
                }
                for p in self.pairs
            ],
        }
        path.write_text(json.dumps(data, indent=2))
    
    @classmethod
    def load(cls, path: Path) -> 'BenchmarkGroundTruth':
        """Load from JSON."""
        data = json.loads(path.read_text())
        pairs = [
            CodePair(
                id_a=p["id_a"],
                id_b=p["id_b"],
                code_a=p.get("code_a", ""),
                code_b=p.get("code_b", ""),
                label=p["label"],
            )
            for p in data.get("pairs", [])
        ]
        return cls(
            name=data["name"],
            version=data["version"],
            language=data["language"],
            metadata=data.get("metadata", {}),
            pairs=pairs,
        )


def create_builtin_ground_truth() -> BenchmarkGroundTruth:
    """Create ground truth from built-in test cases.
    
    Maps the existing DATASETS test cases to labeled pairs:
    - identical -> 3 (exact clone)
    - renamed -> 3 (exact clone - same logic)
    - reordered -> 2 (semantic clone)
    - similar -> 2 (semantic clone)
    - unrelated -> 0 (unrelated)
    - obfuscation cases -> 2 (semantic clone - same logic, different style)
    """
    pairs = []
    
    # Basic Clone Detection - 5 pairs
    pairs.extend([
        CodePair(id_a="identical_a", id_b="identical_b", 
                 label=3, code_a="", code_b=""),  # exact clone
        CodePair(id_a="renamed_a", id_b="renamed_b", 
                 label=3, code_a="", code_b=""),   # exact clone
        CodePair(id_a="reordered_a", id_b="reordered_b", 
                 label=2, code_a="", code_b=""), # semantic clone
        CodePair(id_a="similar_a", id_b="similar_b", 
                 label=2, code_a="", code_b=""),  # semantic clone
        CodePair(id_a="unrelated_a", id_b="unrelated_b", 
                 label=0, code_a="", code_b=""),  # unrelated
    ])
    
    # Obfuscation Resistance - 3 pairs
    pairs.extend([
        CodePair(id_a="obf_rename_a", id_b="obf_rename_b", 
                 label=2, code_a="", code_b=""),   # semantic clone
        CodePair(id_a="obf_reorder_a", id_b="obf_reorder_b", 
                 label=2, code_a="", code_b=""),  # semantic clone
        CodePair(id_a="obf_comments_a", id_b="obf_comments_b", 
                 label=3, code_a="", code_b=""), # exact clone
    ])
    
    # Multi-File Class - 3 pairs  
    pairs.extend([
        CodePair(id_a="class_1_2_a", id_b="class_1_2_b", 
                 label=3, code_a="", code_b=""),   # exact clone
        CodePair(id_a="class_3_4_a", id_b="class_3_4_b", 
                 label=2, code_a="", code_b=""),  # semantic clone
        CodePair(id_a="class_5_6_a", id_b="class_5_6_b", 
                 label=0, code_a="", code_b=""),  # unrelated
    ])
    
    # Java Clone Detection - 2 pairs
    pairs.extend([
        CodePair(id_a="java_identical_a", id_b="java_identical_b", 
                 label=3, code_a="", code_b=""),  # exact clone
        CodePair(id_a="java_renamed_a", id_b="java_renamed_b", 
                 label=2, code_a="", code_b=""),  # semantic clone
    ])
    
    return BenchmarkGroundTruth(
        name="builtin-test-cases",
        version="1.0",
        language="mixed",
        metadata={
            "total_pairs": len(pairs),
            "label_distribution": {
                "unrelated": sum(1 for p in pairs if p.label == 0),
                "weak_similarity": sum(1 for p in pairs if p.label == 1),
                "semantic_clone": sum(1 for p in pairs if p.label == 2),
                "exact_clone": sum(1 for p in pairs if p.label == 3),
            }
        },
        pairs=pairs,
    )


# Ground truth for larger benchmark datasets
def get_poj104_ground_truth() -> BenchmarkGroundTruth:
    """Get POJ-104 ground truth labels.
    
    POJ-104 has 104 problems, each with multiple solutions.
    Same problem = potential clone (label >= 2)
    Different problems = unrelated (label 0)
    """
    # This would need to be loaded from actual dataset
    # For now, return placeholder structure
    return BenchmarkGroundTruth(
        name="poj104",
        version="1.0", 
        language="c",
        metadata={"note": "Labels derived from problem ID: same problem = clone"},
        pairs=[],
    )


def get_bigclonebench_ground_truth() -> BenchmarkGroundTruth:
    """Get BigCloneBench ground truth.
    
    BigCloneBench has labeled clone pairs with 4 types:
    - Type-1: identical
    - Type-2: renamed  
    - Type-3: restructured
    - Type-4: semantic
    
    Maps to: 3, 3, 2, 2 respectively
    """
    return BenchmarkGroundTruth(
        name="bigclonebench",
        version="bceval",
        language="java",
        metadata={"note": "Clone types 1-4 mapped to labels 3,3,2,2"},
        pairs=[],
    )