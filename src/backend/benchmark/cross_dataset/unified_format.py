"""Unified dataset format for cross-dataset benchmarking.

Normalizes all datasets into ONE format with fields:
    id, code_a, code_b, label, type (if available), source
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
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
        counts: Dict[int, int] = {}
        for p in self.pairs:
            counts[p.label] = counts.get(p.label, 0) + 1
        return counts

    @property
    def type_counts(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        for p in self.pairs:
            counts[p.type] = counts.get(p.type, 0) + 1
        return counts

    @property
    def positive_ratio(self) -> float:
        if not self.pairs:
            return 0.0
        return sum(1 for p in self.pairs if p.label == 1) / len(self.pairs)

    @property
    def labels(self) -> List[int]:
        return [p.label for p in self.pairs]

    @property
    def positive_count(self) -> int:
        return sum(1 for p in self.pairs if p.label == 1)

    @property
    def negative_count(self) -> int:
        return sum(1 for p in self.pairs if p.label == 0)

    def get_arrays(self) -> tuple:
        y_true = [p.label for p in self.pairs]
        return y_true

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [
            {"id": p.id, "code_a": p.code_a, "code_b": p.code_b,
             "label": p.label, "type": p.type, "source": p.source}
            for p in self.pairs
        ]

    def save(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name, "metadata": self.metadata,
            "total_pairs": len(self.pairs),
            "positive": self.positive_count, "negative": self.negative_count,
            "pairs": self.to_dicts(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_canonical(cls, canonical, name: str = "") -> "UnifiedDataset":
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


# Alias for backward compatibility with cross_eval.py
UnifiedBenchmarkDataset = UnifiedDataset
