"""
Karnalim Classroom Dataset Loader.

Oscar Karnalim's classroom plagiarism dataset containing real student submissions
with confirmed plagiarism cases from university programming assignments.

Reference:
Karnalim, O. (2019). A Dataset of Student Plagiarism in Programming Assignments.
In Proceedings of the 2019 ACM Conference on Innovation and Technology in Computer
Science Education (ITiCSE '19).
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Iterator, Tuple

from src.backend.benchmark.datasets.schema import Sample, ClonePair, DatasetContract
from src.backend.benchmark.datasets.base import BaseDataset


class KarnalimDataset(BaseDataset, DatasetContract):
    """
    Loader for Karnalim Classroom Plagiarism Dataset.

    Dataset contains real student submissions from introductory programming courses
    with manually verified plagiarism cases. Includes:
    - 4 programming assignments
    - Total 132 submissions
    - 28 confirmed plagiarism pairs
    - Ground truth for all pairs
    """

    dataset_id = "karnalim_classroom"
    dataset_name = "Karnalim Classroom Dataset"
    dataset_description = "Real student programming submissions with confirmed plagiarism cases"
    language = "java"
    sample_count = 132
    clone_pair_count = 28

    def __init__(self, dataset_path: Optional[Path] = None):
        super().__init__()
        self.dataset_path = dataset_path or Path(os.environ.get(
            "KARNALIM_DATASET_PATH",
            "./datasets/karnalim"
        ))
        self._samples: List[Sample] = []
        self._clone_pairs: List[ClonePair] = []

    def load(self) -> None:
        """Load and parse the Karnalim dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Karnalim dataset not found at {self.dataset_path}. "
                "Clone from https://github.com/oscarkarnalim/classroom_dataset.git "
                "and set KARNALIM_DATASET_PATH environment variable."
            )

        self._load_samples()
        self._load_ground_truth()
        self.loaded = True

    def _load_samples(self) -> None:
        """Load all submission samples from the dataset."""
        self._samples = []

        for assignment_dir in sorted(self.dataset_path.glob("assignment*")):
            if not assignment_dir.is_dir():
                continue

            assignment_id = assignment_dir.name
            submissions_dir = assignment_dir / "submissions"

            if not submissions_dir.exists():
                continue

            for submission_file in submissions_dir.glob("*.java"):
                sample_id = f"{assignment_id}_{submission_file.stem}"

                with open(submission_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                self._samples.append(Sample(
                    id=sample_id,
                    content=content,
                    language="java",
                    metadata={
                        "assignment": assignment_id,
                        "filename": submission_file.name,
                        "student_id": submission_file.stem
                    }
                ))

    def _load_ground_truth(self) -> None:
        """Load ground truth plagiarism pairs."""
        self._clone_pairs = []

        gt_file = self.dataset_path / "ground_truth.json"
        if gt_file.exists():
            with open(gt_file, 'r', encoding='utf-8') as f:
                gt_data = json.load(f)

            for pair in gt_data.get("plagiarism_pairs", []):
                self._clone_pairs.append(ClonePair(
                    id=f"{pair['assignment']}_{pair['a']}_{pair['b']}",
                    sample_a_id=f"{pair['assignment']}_{pair['a']}",
                    sample_b_id=f"{pair['assignment']}_{pair['b']}",
                    clone_type=pair.get("clone_type", 2),
                    is_plagiarism=True,
                    metadata={
                        "assignment": pair['assignment'],
                        "description": pair.get("description", "")
                    }
                ))

    def get_all_samples(self) -> Iterator[Sample]:
        self._ensure_loaded()
        return iter(self._samples)

    def get_all_clone_pairs(self) -> Iterator[ClonePair]:
        self._ensure_loaded()
        return iter(self._clone_pairs)

    def get_sample_by_id(self, sample_id: str) -> Optional[Sample]:
        self._ensure_loaded()
        return next((s for s in self._samples if s.id == sample_id), None)

    def get_statistics(self) -> Dict:
        self._ensure_loaded()
        return {
            "name": self.dataset_name,
            "samples_count": len(self._samples),
            "clone_pairs_count": len(self._clone_pairs),
            "language": self.language,
            "assignments": len(set(s.metadata["assignment"] for s in self._samples))
        }
