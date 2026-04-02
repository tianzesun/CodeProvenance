"""
POJ-104 Dataset Loader.

Loads POJ-104 (Peking University Online Judge) dataset.
Contains 53,000 C programs from 104 programming problems.
Used for code clone detection and plagiarism detection.

Reference: https://huggingface.co/datasets/code_x_glue_cc_clone_detection_poj104
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class POJ104Sample:
    """A code sample from POJ-104."""
    id: str
    code: str
    label: int  # Problem ID (1-104)
    split: str = "train"


class POJ104Dataset:
    """
    Loads POJ-104 dataset.
    
    Dataset structure:
        poj104/
        └── huggingface/
            ├── train/
            │   ├── data-00000-of-0000X.arrow
            │   └── ...
            ├── test/
            └── validation/
    """
    
    # Splits from manifest
    SPLITS = {
        "train": 32500,
        "validation": 8500,
        "test": 12000,
    }
    
    def __init__(self, data_dir: Path = Path("benchmark/data/poj104")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[POJ104Sample] = []
        self._dataset = None
    
    def load(self, split: str = "train", max_samples: Optional[int] = None) -> List[POJ104Sample]:
        """
        Load POJ-104 samples from HuggingFace Arrow format.
        
        Args:
            split: Dataset split ('train', 'test', 'validation')
            max_samples: Maximum number of samples to load
            
        Returns:
            List of POJ104Sample objects
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
            
            sample = POJ104Sample(
                id=f"{split}_{i}",
                code=item.get("code", ""),
                label=int(item.get("label", 0)),
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
            "name": "POJ-104",
            "language": "c",
            "total_problems": 104,
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
            
            # Count by problem label
            label_counts = {}
            for s in self._samples:
                label_counts[s.label] = label_counts.get(s.label, 0) + 1
            stats["problems_represented"] = len(label_counts)
            stats["samples_per_problem"] = {
                "min": min(label_counts.values()) if label_counts else 0,
                "max": max(label_counts.values()) if label_counts else 0,
                "avg": sum(label_counts.values()) / len(label_counts) if label_counts else 0,
            }
            
            stats["avg_code_length"] = sum(len(s.code) for s in self._samples) / len(self._samples)
        
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