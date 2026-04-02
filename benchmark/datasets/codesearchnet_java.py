"""
CodeSearchNet Dataset Loader (Java subset).

Loads CodeSearchNet Java functions for semantic similarity evaluation.
Contains 496,688 Java functions with docstrings.

Reference: https://huggingface.co/datasets/code_search_net
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CodeSearchNetJavaSample:
    """A Java code sample from CodeSearchNet."""
    id: str
    code: str
    docstring: str
    language: str = "java"
    func_name: str = ""
    split: str = "train"


class CodeSearchNetJavaDataset:
    """
    Loads CodeSearchNet Java dataset.
    
    Dataset structure:
        codesearchnet_java/
        └── huggingface/
            ├── train/
            │   ├── data-00000-of-0000X.arrow
            │   └── ...
            ├── test/
            └── validation/
    """
    
    def __init__(self, data_dir: Path = Path("benchmark/data/codesearchnet_java")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[CodeSearchNetJavaSample] = []
        self._dataset = None
    
    def load(self, split: str = "train", max_samples: Optional[int] = None) -> List[CodeSearchNetJavaSample]:
        """
        Load CodeSearchNet Java samples from HuggingFace Arrow format.
        
        Args:
            split: Dataset split ('train', 'test', 'validation')
            max_samples: Maximum number of samples to load
            
        Returns:
            List of CodeSearchNetJavaSample objects
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
            
            sample = CodeSearchNetJavaSample(
                id=f"{split}_{i}",
                code=item.get("func_code_string", ""),
                docstring=item.get("func_documentation_string", ""),
                language="java",
                func_name=item.get("func_name", ""),
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
            "name": "CodeSearchNet (Java)",
            "language": "java",
            "huggingface_dir": str(self.hf_dir),
            "available_splits": self._get_available_splits(),
            "samples_loaded": len(self._samples),
        }
        
        if self._samples:
            stats["avg_code_length"] = sum(len(s.code) for s in self._samples) / len(self._samples)
            stats["avg_docstring_length"] = sum(len(s.docstring) for s in self._samples) / len(self._samples)
        
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