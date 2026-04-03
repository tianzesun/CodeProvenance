"""Unified dataset format for cross-dataset benchmarking.

Normalizes all datasets into ONE format with fields:
    id, code_a, code_b, label, type (if available), source
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class UnifiedPair:
    """A single code pair in unified format.

    Fields:
        id: Unique identifier for this pair
        code_a: First code snippet
        code_b: Second code snippet
        label: Ground truth (1 = clone/plagiarism, 0 = non-clone)
        type: Clone type if available (1-4 for BigCloneBench types, 0 = non-clone)
        source: Dataset name this pair came from
        metadata: Additional metadata
    """
    id: str
    code_a: str
    code_b: str
    label: int
    type: int = 0
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedDataset:
    """A dataset in unified format.

    Contains a list of UnifiedPair objects and dataset-level metadata.
    """
    name: str
    pairs: List[UnifiedPair] = field(default_factory=list)
    language: str = ""
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.pairs)

    @property
    def label_counts(self) -> Dict[int, int]:
        """Count of pairs per label."""
        counts: Dict[int, int] = {}
        for p in self.pairs:
            counts[p.label] = counts.get(p.label, 0) + 1
        return counts

    @property
    def type_counts(self) -> Dict[int, int]:
        """Count of pairs per clone type."""
        counts: Dict[int, int] = {}
        for p in self.pairs:
            counts[p.type] = counts.get(p.type, 0) + 1
        return counts

    @property
    def positive_ratio(self) -> float:
        """Fraction of positive (clone) pairs."""
        if not self.pairs:
            return 0.0
        return sum(1 for p in self.pairs if p.label == 1) / len(self.pairs)

    def get_arrays(self) -> tuple:
        """Get arrays suitable for sklearn metrics.

        Returns:
            (y_true, y_scores_placeholder) where y_true is labels array.
        """
        y_true = [p.label for p in self.pairs]
        return y_true

    @classmethod
    def from_canonical(cls, canonical, name: str = "") -> "UnifiedDataset":
        """Convert from existing CanonicalDataset format.

        Args:
            canonical: CanonicalDataset with pairs attribute
            name: Override dataset name

        Returns:
            UnifiedDataset instance
        """
        pairs = []
        ds_name = name or getattr(canonical, "name", "unknown")
        for cp in canonical.pairs:
            pairs.append(UnifiedPair(
                id=f"{ds_name}_{getattr(cp, 'id_a', '')}_{getattr(cp, 'id_b', '')}",
                code_a=cp.code_a,
                code_b=cp.code_b,
                label=cp.label,
                type=getattr(cp, "clone_type", 0),
                source=ds_name,
                metadata=getattr(cp, "metadata", {}),
            ))
        return cls(
            name=ds_name,
            pairs=pairs,
            language=getattr(canonical, "language", ""),
            version=getattr(canonical, "version", "1.0"),
        )
