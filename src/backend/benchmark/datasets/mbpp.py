"""
MBPP Dataset Loader.

Loads MBPP (Mostly Basic Python Problems) dataset.
Contains Python programming tasks with prompts, tests, and reference code.

Reference: https://huggingface.co/datasets/mbpp
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class MBPPSample:
    """A code generation sample from MBPP."""

    id: str
    text: str
    code: str
    test_list: List[str]
    split: str = "train"


class MBPPDataset:
    """
    Loads MBPP dataset.

    Dataset structure:
        mbpp/
        └── huggingface/
            ├── train/
            │   ├── data-00000-of-00001.arrow
            │   └── ...
            ├── validation/
            ├── test/
            └── prompt/
    """

    def __init__(self, data_dir: Path = Path("benchmark/data/mbpp")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[MBPPSample] = []
        self._dataset = None

    def load(
        self, split: str = "train", max_samples: Optional[int] = None
    ) -> List[MBPPSample]:
        """
        Load MBPP samples from HuggingFace Arrow format.

        Args:
            split: Dataset split ('train', 'validation', 'test', 'prompt')
            max_samples: Maximum number of samples to load

        Returns:
            List of MBPPSample objects
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

        dataset = load_from_disk(str(split_dir))
        self._dataset = dataset

        samples = []
        for i, item in enumerate(dataset):
            if max_samples and i >= max_samples:
                break

            sample = MBPPSample(
                id=str(item.get("task_id", f"{split}_{i}")),
                text=item.get("text", ""),
                code=item.get("code", ""),
                test_list=item.get("test_list", []),
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
            "name": "MBPP",
            "language": "python",
            "huggingface_dir": str(self.hf_dir),
            "available_splits": self._get_available_splits(),
            "samples_loaded": len(self._samples),
        }

        if self._samples:
            split_counts = {}
            for s in self._samples:
                split_counts[s.split] = split_counts.get(s.split, 0) + 1
            stats["samples_by_split"] = split_counts

            stats["avg_prompt_length"] = sum(len(s.text) for s in self._samples) / len(
                self._samples
            )
            stats["avg_code_length"] = sum(len(s.code) for s in self._samples) / len(
                self._samples
            )
            stats["avg_tests_per_sample"] = sum(
                len(s.test_list) for s in self._samples
            ) / len(self._samples)

        return stats

    def check_availability(self) -> Dict[str, bool]:
        """Check dataset availability."""
        return {
            "data_dir": self.data_dir.exists(),
            "huggingface_dir": self.hf_dir.exists(),
            "train_split": (self.hf_dir / "train").exists(),
            "validation_split": (self.hf_dir / "validation").exists(),
            "test_split": (self.hf_dir / "test").exists(),
            "prompt_split": (self.hf_dir / "prompt").exists(),
        }
