"""
CodeXGLUE Code Clone Detection Dataset Loader.

Loads Microsoft CodeXGLUE code clone detection dataset.
Contains 1,731,860 Java function pairs with clone labels.

Reference: https://huggingface.co/datasets/code_x_glue_cc_clone_detection_big_clone_bench
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CodeXGLUEClonePair:
    """A clone pair from CodeXGLUE."""
    id: str
    id1: str
    id2: str
    func1: str
    func2: str
    label: int  # 1=clone, 0=non-clone
    split: str = "train"


class CodeXGLUECloneDataset:
    """
    Loads CodeXGLUE code clone detection dataset.
    
    Dataset structure:
        codexglue_clone/
        └── huggingface/
            ├── train/
            │   ├── data-00000-of-0000X.arrow
            │   └── ...
            ├── test/
            └── validation/
    """
    
    # Splits from manifest
    SPLITS = {
        "train": 901028,
        "validation": 415416,
        "test": 415416,
    }
    
    def __init__(self, data_dir: Path = Path("benchmark/data/codexglue_clone")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._pairs: List[CodeXGLUEClonePair] = []
        self._dataset = None
    
    def load(self, split: str = "train", max_pairs: Optional[int] = None) -> List[CodeXGLUEClonePair]:
        """
        Load CodeXGLUE clone pairs from HuggingFace Arrow format.
        
        Args:
            split: Dataset split ('train', 'test', 'validation')
            max_pairs: Maximum number of pairs to load
            
        Returns:
            List of CodeXGLUEClonePair objects
        """
        try:
            from datasets import load_from_disk
        except ImportError:
            raise ImportError(
                "datasets library required. Install with: pip install datasets"
            )
        
        split_dir = self.hf_dir / split
        if not split_dir.exists():
            raise FileNotFoundError(
                f"Split '{split}' not found at {split_dir}. "
                f"Available splits: {self._get_available_splits()}"
            )
        
        # Load dataset from disk
        dataset = load_from_disk(str(split_dir))
        self._dataset = dataset
        
        # Convert to our format
        pairs = []
        for i, item in enumerate(dataset):
            if max_pairs and i >= max_pairs:
                break
            
            pair = CodeXGLUEClonePair(
                id=f"{split}_{i}",
                id1=str(item.get("id1", "")),
                id2=str(item.get("id2", "")),
                func1=item.get("func1", ""),
                func2=item.get("func2", ""),
                label=int(item.get("label", 0)),
                split=split,
            )
            pairs.append(pair)
        
        self._pairs = pairs
        return pairs
    
    def _get_available_splits(self) -> List[str]:
        """Get available dataset splits."""
        if not self.hf_dir.exists():
            return []
        return [d.name for d in self.hf_dir.iterdir() if d.is_dir()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "CodeXGLUE Clone Detection",
            "language": "java",
            "huggingface_dir": str(self.hf_dir),
            "available_splits": self._get_available_splits(),
            "expected_splits": self.SPLITS,
            "pairs_loaded": len(self._pairs),
        }
        
        if self._pairs:
            # Count by split
            split_counts = {}
            for p in self._pairs:
                split_counts[p.split] = split_counts.get(p.split, 0) + 1
            stats["pairs_by_split"] = split_counts
            
            # Count by label
            label_counts = {}
            for p in self._pairs:
                label_counts[p.label] = label_counts.get(p.label, 0) + 1
            stats["pairs_by_label"] = label_counts
            
            stats["avg_func1_length"] = sum(len(p.func1) for p in self._pairs) / len(self._pairs)
            stats["avg_func2_length"] = sum(len(p.func2) for p in self._pairs) / len(self._pairs)
        
        return stats
    
    def check_availability(self) -> Dict[str, bool]:
        """Check dataset availability."""
        return {
            "data_dir": self.data_dir.exists(),
            "huggingface_dir": self.hf_dir.exists(),
            "train_split": (self.hf_dir / "train").exists(),
            "test_split": (self.hf_dir / "test").exists(),
            "validation_split": (self.hf_dir / "validation").exists(),
        }