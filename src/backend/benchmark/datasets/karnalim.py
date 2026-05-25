"""Karnalim classroom plagiarism dataset loader.

Oscar Karnalim's classroom plagiarism dataset contains real student submissions
with confirmed plagiarism cases from university programming assignments.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from src.backend.benchmark.datasets.schema import (
    CanonicalDataset,
    CloneType,
    CodePair,
    DatasetContract,
    DatasetMetadata,
    Difficulty,
)


@dataclass
class KarnalimSample:
    """A single source-code submission from the Karnalim dataset."""

    id: str
    content: str
    language: str = "java"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KarnalimClonePair:
    """A manually confirmed plagiarism pair from the Karnalim dataset."""

    id: str
    sample_a_id: str
    sample_b_id: str
    clone_type: int = 2
    is_plagiarism: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class KarnalimDataset(DatasetContract):
    """Load Karnalim classroom submissions into the benchmark dataset contract."""

    dataset_id = "karnalim_classroom"
    dataset_name = "Karnalim Classroom Dataset"
    dataset_description = "Real student programming submissions with plagiarism labels"
    language = "java"
    expected_sample_count = 132
    expected_clone_pair_count = 28

    def __init__(self, dataset_path: Optional[Path] = None):
        """Initialize the loader with an explicit or environment-provided path."""
        self.dataset_path = dataset_path or Path(
            os.environ.get("KARNALIM_DATASET_PATH", "./datasets/karnalim")
        )
        self.loaded = False
        self._samples: List[KarnalimSample] = []
        self._clone_pairs: List[KarnalimClonePair] = []

    @property
    def metadata(self) -> DatasetMetadata:
        """Return static dataset metadata for validation and reporting."""
        size = len(self._clone_pairs) or self.expected_clone_pair_count
        return DatasetMetadata(
            name=self.dataset_name,
            version="2019",
            language=self.language,
            clone_types=[CloneType.TYPE_2, CloneType.TYPE_3],
            difficulty=Difficulty.MEDIUM,
            size=size,
            source="https://github.com/oscarkarnalim/classroom_dataset",
            license="research",
            ground_truth_format="binary",
            description=self.dataset_description,
        )

    def load(self, **kwargs: Any) -> CanonicalDataset:
        """Load submissions and confirmed plagiarism pairs as a canonical dataset."""
        if kwargs:
            max_pairs = kwargs.get("max_pairs")
        else:
            max_pairs = None

        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Karnalim dataset not found at {self.dataset_path}. "
                "Clone https://github.com/oscarkarnalim/classroom_dataset and set "
                "KARNALIM_DATASET_PATH."
            )

        self._load_samples()
        self._load_ground_truth()
        if max_pairs is not None:
            self._clone_pairs = self._clone_pairs[: int(max_pairs)]
        self.loaded = True

        sample_by_id = {sample.id: sample for sample in self._samples}
        pairs = [
            self._to_code_pair(pair, sample_by_id)
            for pair in self._clone_pairs
            if pair.sample_a_id in sample_by_id and pair.sample_b_id in sample_by_id
        ]
        return CanonicalDataset(
            name=self.dataset_id,
            version=self.metadata.version,
            pairs=pairs,
            metadata=self.metadata,
            submissions=list(self._samples),
            language=self.language,
        )

    def _load_samples(self) -> None:
        """Load Java submissions from assignment directories."""
        self._samples = []

        for assignment_dir in sorted(self.dataset_path.glob("assignment*")):
            if not assignment_dir.is_dir():
                continue

            submissions_dir = assignment_dir / "submissions"
            if not submissions_dir.exists():
                continue

            for submission_file in sorted(submissions_dir.glob("*.java")):
                content = submission_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                self._samples.append(
                    KarnalimSample(
                        id=f"{assignment_dir.name}_{submission_file.stem}",
                        content=content,
                        metadata={
                            "assignment": assignment_dir.name,
                            "filename": submission_file.name,
                            "student_id": submission_file.stem,
                        },
                    )
                )

    def _load_ground_truth(self) -> None:
        """Load confirmed plagiarism pairs from ``ground_truth.json`` when present."""
        self._clone_pairs = []

        gt_file = self.dataset_path / "ground_truth.json"
        if not gt_file.exists():
            return

        gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
        for pair in gt_data.get("plagiarism_pairs", []):
            assignment = pair["assignment"]
            self._clone_pairs.append(
                KarnalimClonePair(
                    id=f"{assignment}_{pair['a']}_{pair['b']}",
                    sample_a_id=f"{assignment}_{pair['a']}",
                    sample_b_id=f"{assignment}_{pair['b']}",
                    clone_type=int(pair.get("clone_type", 2)),
                    metadata={
                        "assignment": assignment,
                        "description": pair.get("description", ""),
                    },
                )
            )

    @staticmethod
    def _to_code_pair(
        pair: KarnalimClonePair,
        sample_by_id: Dict[str, KarnalimSample],
    ) -> CodePair:
        """Convert a Karnalim pair into the shared canonical pair schema."""
        sample_a = sample_by_id[pair.sample_a_id]
        sample_b = sample_by_id[pair.sample_b_id]
        return CodePair(
            id_a=pair.sample_a_id,
            id_b=pair.sample_b_id,
            code_a=sample_a.content,
            code_b=sample_b.content,
            label=1 if pair.is_plagiarism else 0,
            clone_type=pair.clone_type,
            metadata=dict(pair.metadata),
        )

    def get_all_samples(self) -> Iterator[KarnalimSample]:
        """Return an iterator over loaded samples, loading the dataset if needed."""
        self._ensure_loaded()
        return iter(self._samples)

    def get_all_clone_pairs(self) -> Iterator[KarnalimClonePair]:
        """Return an iterator over loaded clone pairs, loading the dataset if needed."""
        self._ensure_loaded()
        return iter(self._clone_pairs)

    def get_sample_by_id(self, sample_id: str) -> Optional[KarnalimSample]:
        """Return one sample by identifier, or ``None`` when it is absent."""
        self._ensure_loaded()
        return next(
            (sample for sample in self._samples if sample.id == sample_id), None
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Return lightweight statistics for the loaded dataset."""
        self._ensure_loaded()
        assignments = {sample.metadata["assignment"] for sample in self._samples}
        return {
            "name": self.dataset_name,
            "samples_count": len(self._samples),
            "clone_pairs_count": len(self._clone_pairs),
            "language": self.language,
            "assignments": len(assignments),
        }

    def _ensure_loaded(self) -> None:
        """Load the dataset before serving cached convenience data."""
        if not self.loaded:
            self.load()
