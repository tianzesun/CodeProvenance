"""
CodeXGLUE Defect Detection Dataset Loader.

Loads Microsoft CodeXGLUE defect detection dataset.
Contains 27,318 C functions with vulnerability labels.

Reference: https://huggingface.co/datasets/code_x_glue_cc_defect_detection
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CodeXGLUEDefectSample:
    """A code sample from CodeXGLUE defect detection."""
    id: str
    func: str
    target: int  # 1=defective, 0=non-defective
    project: str = ""
    commit_id: str = ""
    split: str = "train"


class CodeXGLUEDefectDataset:
    """
    Loads CodeXGLUE defect detection dataset.
    
    Dataset structure:
        codexglue_defect/
        └── huggingface/
            ├── train/
            │   ├── data-00000-of-0000X.arrow
            │   └── ...
            ├── test/
            └── validation/
    """
    
    # Splits from manifest
    SPLITS = {
        "train": 21854,
        "validation": 2732,
        "test": 2732,
    }
    
    def __init__(self, data_dir: Path = Path("benchmark/data/codexglue_defect")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[CodeXGLUEDefectSample] = []
        self._dataset = None
    
    def load(self, split: str = "train", max_samples: Optional[int] = None) -> List[CodeXGLUEDefectSample]:
        """
        Load CodeXGLUE defect samples from HuggingFace Arrow format.
        
        Args:
            split: Dataset split ('train', 'test', 'validation')
            max_samples: Maximum number of samples to load
            
        Returns:
            List of CodeXGLUEDefectSample objects
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
        samples = []
        for i, item in enumerate(dataset):
            if max_samples and i >= max_samples:
                break
            
            sample = CodeXGLUEDefectSample(
                id=f"{split}_{i}",
                func=item.get("func", ""),
                target=int(item.get("target", 0)),
                project=item.get("project", ""),
                commit_id=item.get("commit_id", ""),
                split=split,
            )
            samples.append(sample)
        
        self._samples = samples
        return samples
    
    def _get_available_splits(self) -> List[str]:
        """Get available dataset splits."""
        if not self.hf_dir.exists():
            return []
        return [d.name for d in self.hf_dir.iterdir() if d.is_dir()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "CodeXGLUE Defect Detection",
            "language": "c",
            "huggingface_dir": str(self.hf_dir),
            "available_splits": self._get_available_splits(),
            "expected_splits": self.SPLITS,
            "samples_loaded": len(self._samples),
        }
        
        if self._samples:
            # Count by split
            split_counts = {}
            for s in self._samples:
                split_counts[s.split] = split_counts.get(s.split, 0) + 1
            stats["samples_by_split"] = split_counts
            
            # Count by target (defective vs non-defective)
            target_counts = {}
            for s in self._samples:
                target_counts[s.target] = target_counts.get(s.target, 0) + 1
            stats["samples_by_target"] = target_counts
            
            stats["avg_func_length"] = sum(len(s.func) for s in self._samples) / len(self._samples)
        
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