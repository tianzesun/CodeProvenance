"""
HumanEval Dataset Loader.

Loads OpenAI HumanEval dataset.
Contains 164 Python programming tasks with prompts, tests, and canonical solutions.

Reference: https://huggingface.co/datasets/openai_humaneval
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class HumanEvalSample:
    """A code generation sample from HumanEval."""

    id: str
    prompt: str
    test: str
    entry_point: str
    canonical_solution: str = ""
    split: str = "test"


class HumanEvalDataset:
    """
    Loads HumanEval dataset.

    Dataset structure:
        human_eval/
        └── huggingface/
            └── test/
                ├── data-00000-of-00001.arrow
                └── ...
    """

    # Splits from manifest
    SPLITS = {
        "test": 164,
    }

    def __init__(self, data_dir: Path = Path("benchmark/data/human_eval")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[HumanEvalSample] = []
        self._dataset = None

    def load(
        self, split: str = "test", max_samples: Optional[int] = None
    ) -> List[HumanEvalSample]:
        """
        Load HumanEval samples from HuggingFace Arrow format.

        Args:
            split: Dataset split ('test')
            max_samples: Maximum number of samples to load

        Returns:
            List of HumanEvalSample objects
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

            sample = HumanEvalSample(
                id=item.get("task_id", f"{split}_{i}"),
                prompt=item.get("prompt", ""),
                test=item.get("test", ""),
                entry_point=item.get("entry_point", ""),
                canonical_solution=item.get("canonical_solution", ""),
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
            "name": "HumanEval",
            "language": "python",
            "huggingface_dir": str(self.hf_dir),
            "available_splits": self._get_available_splits(),
            "expected_splits": self.SPLITS,
            "samples_loaded": len(self._samples),
        }

        if self._samples:
            stats["avg_prompt_length"] = sum(
                len(s.prompt) for s in self._samples
            ) / len(self._samples)
            stats["avg_test_length"] = sum(len(s.test) for s in self._samples) / len(
                self._samples
            )
            stats["avg_solution_length"] = sum(
                len(s.canonical_solution) for s in self._samples
            ) / len(self._samples)

        return stats

    def check_availability(self) -> Dict[str, bool]:
        """Check dataset availability."""
        return {
            "data_dir": self.data_dir.exists(),
            "huggingface_dir": self.hf_dir.exists(),
            "test_split": (self.hf_dir / "test").exists(),
        }
