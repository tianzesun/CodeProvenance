"""Dataset engine for EvalForge v2.

Handles loading, transformation, and sampling of labeled code pairs.
"""
from __future__ import annotations
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Iterator

from src.evalforge.core import CodePair, CloneType, Transformer

# Add project root to path for relative imports
import sys
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from src.benchmark.generators.utils.rename_utils import rename_identifiers
from src.benchmark.generators.utils.transform_utils import (
    reorder_statements,
    add_dead_code,
    convert_loops,
)


TRANSFORMATIONS: Dict[str, Transformer] = {
    "rename_vars": type('RenameVarsTransformer', (Transformer,), {
        'name': property(lambda self: "rename_vars"),
        'apply': lambda self, code: rename_identifiers(code)
    })(),
    "reorder_blocks": type('ReorderBlocksTransformer', (Transformer,), {
        'name': property(lambda self: "reorder_blocks"),
        'apply': lambda self, code: reorder_statements(code)
    })(),
    "loop_convert": type('LoopConvertTransformer', (Transformer,), {
        'name': property(lambda self: "loop_convert"),
        'apply': lambda self, code: convert_loops(code)
    })(),
    "dead_code": type('DeadCodeTransformer', (Transformer,), {
        'name': property(lambda self: "dead_code"),
        'apply': lambda self, code: add_dead_code(code)
    })(),
}


@dataclass
class Dataset:
    """Labeled dataset for plagiarism detection evaluation."""
    
    name: str
    pairs: List[CodePair] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def load(cls, path: Path) -> 'Dataset':
        """Load dataset from JSON file."""
        data = json.loads(path.read_text())
        pairs = []
        
        for p in data.get("pairs", []):
            pairs.append(CodePair(
                id=p["id"],
                code_a=p["code_a"],
                code_b=p["code_b"],
                label=CloneType(p["label"]),
                transform_path=p.get("transform_path", []),
                metadata=p.get("metadata", {})
            ))
        
        return cls(
            name=data["name"],
            pairs=pairs,
            metadata=data.get("metadata", {})
        )
    
    def save(self, path: Path) -> None:
        """Save dataset to JSON file."""
        data = {
            "name": self.name,
            "metadata": self.metadata,
            "pairs": [
                {
                    "id": p.id,
                    "code_a": p.code_a,
                    "code_b": p.code_b,
                    "label": p.label.value,
                    "transform_path": p.transform_path,
                    "metadata": p.metadata,
                }
                for p in self.pairs
            ]
        }
        path.write_text(json.dumps(data, indent=2))
    
    def apply_transformations(self, 
                             transformations: List[str],
                             seed: int = 42) -> 'Dataset':
        """Apply semantic-preserving transformations to all positive pairs.
        
        Creates new pairs by applying transformation chains to code_b.
        """
        rng = random.Random(seed)
        new_pairs = []
        
        for pair in self.pairs:
            if not pair.is_positive:
                new_pairs.append(pair)
                continue
            
            # Apply transformation chain
            transformed_b = pair.code_b
            path = []
            
            for t_name in transformations:
                if t_name in TRANSFORMATIONS:
                    transformed_b = TRANSFORMATIONS[t_name].apply(transformed_b)
                    path.append(t_name)
            
            new_pairs.append(CodePair(
                id=f"{pair.id}_{'_'.join(transformations)}",
                code_a=pair.code_a,
                code_b=transformed_b,
                label=pair.label,
                transform_path=path,
                metadata={**pair.metadata, "transform_seed": seed}
            ))
        
        return Dataset(
            name=f"{self.name}_transformed",
            pairs=new_pairs,
            metadata={**self.metadata, "transformations": transformations}
        )
    
    def sample_balanced(self, 
                       positive_ratio: float = 0.5,
                       max_pairs: Optional[int] = None,
                       seed: int = 42) -> 'Dataset':
        """Sample balanced dataset with given positive/negative ratio."""
        rng = random.Random(seed)
        
        positives = [p for p in self.pairs if p.is_positive]
        negatives = [p for p in self.pairs if not p.is_positive]
        
        n_pos = int((max_pairs or len(self.pairs)) * positive_ratio)
        n_neg = (max_pairs or len(self.pairs)) - n_pos
        
        sampled = []
        sampled.extend(rng.sample(positives, min(n_pos, len(positives))))
        sampled.extend(rng.sample(negatives, min(n_neg, len(negatives))))
        
        rng.shuffle(sampled)
        
        return Dataset(
            name=f"{self.name}_sampled",
            pairs=sampled,
            metadata={
                **self.metadata,
                "positive_ratio": positive_ratio,
                "max_pairs": max_pairs,
                "sampling_seed": seed
            }
        )
    
    def stratified_split(self, 
                        train_ratio: float = 0.7,
                        seed: int = 42) -> Tuple['Dataset', 'Dataset']:
        """Split dataset into train/test with stratified sampling per clone type."""
        rng = random.Random(seed)
        
        # Group by label
        by_label = {}
        for pair in self.pairs:
            by_label.setdefault(pair.label, []).append(pair)
        
        train_pairs = []
        test_pairs = []
        
        for label, pairs in by_label.items():
            rng.shuffle(pairs)
            split_idx = int(len(pairs) * train_ratio)
            train_pairs.extend(pairs[:split_idx])
            test_pairs.extend(pairs[split_idx:])
        
        return (
            Dataset(name=f"{self.name}_train", pairs=train_pairs, metadata=self.metadata),
            Dataset(name=f"{self.name}_test", pairs=test_pairs, metadata=self.metadata)
        )
    
    def __iter__(self) -> Iterator[CodePair]:
        return iter(self.pairs)
    
    def __len__(self) -> int:
        return len(self.pairs)


# Load standard benchmark datasets
def load_poj104() -> Dataset:
    """Load POJ-104 dataset."""
    path = Path("/home/tsun/CodeProvenance/benchmark/data/poj104")
    # Implementation would load from actual dataset
    return Dataset(name="poj104", pairs=[])


def load_bigclonebench() -> Dataset:
    """Load BigCloneBench dataset."""
    path = Path("/home/tsun/CodeProvenance/benchmark/data/bigclonebench")
    return Dataset(name="bigclonebench", pairs=[])


def load_codesearchnet(language: str = "python") -> Dataset:
    """Load CodeSearchNet dataset."""
    path = Path(f"/home/tsun/CodeProvenance/benchmark/data/codesearchnet_{language}")
    return Dataset(name=f"codesearchnet_{language}", pairs=[])


def load_codexglue_clone() -> Dataset:
    """Load CodeXGLUE clone detection dataset."""
    path = Path("/home/tsun/CodeProvenance/benchmark/data/codexglue_clone")
    return Dataset(name="codexglue_clone", pairs=[])


def get_available_datasets() -> List[str]:
    """List available datasets."""
    return ["poj104", "bigclonebench", "codesearchnet_python", "codesearchnet_java", "codexglue_clone"]