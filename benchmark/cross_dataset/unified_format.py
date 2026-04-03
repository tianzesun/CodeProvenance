"""Unified dataset format and registry for cross-dataset benchmarking.

Normalizes all datasets into ONE format with fields:
  id, code_a, code_b, label, type (if available), source
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class UnifiedPair:
    """A single code pair in unified format."""
    id: str
    code_a: str
    code_b: str
    label: int
    type: Optional[str] = None
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code_a": self.code_a,
            "code_b": self.code_b,
            "label": self.label,
            "type": self.type,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UnifiedPair":
        return cls(
            id=d["id"],
            code_a=d["code_a"],
            code_b=d["code_b"],
            label=int(d["label"]),
            type=d.get("type"),
            source=d.get("source", ""),
        )


@dataclass
class UnifiedBenchmarkDataset:
    """Normalized dataset in unified format.

    All datasets are converted to this format regardless of origin.
    """
    name: str
    pairs: List[UnifiedPair] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.pairs)

    @property
    def labels(self) -> List[int]:
        return [p.label for p in self.pairs]

    @property
    def positive_count(self) -> int:
        return sum(1 for p in self.pairs if p.label == 1)

    @property
    def negative_count(self) -> int:
        return sum(1 for p in self.pairs if p.label == 0)

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.pairs]

    def save(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "metadata": self.metadata,
            "total_pairs": len(self.pairs),
            "positive": self.positive_count,
            "negative": self.negative_count,
            "pairs": self.to_dicts(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "UnifiedBenchmarkDataset":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = [UnifiedPair.from_dict(p) for p in data.get("pairs", [])]
        ds = cls(name=data.get("name", "unknown"), pairs=pairs)
        ds.metadata = data.get("metadata", {})
        return ds

    @classmethod
    def from_canonical(cls, canonical_dataset) -> "UnifiedBenchmarkDataset":
        """Convert a CanonicalDataset (from the existing pipeline) to unified format."""
        pairs = []
        for idx, pair in enumerate(canonical_dataset.pairs):
            clone_type_str = None
            ct = getattr(pair, "clone_type", 0)
            if ct:
                clone_type_str = f"type{ct}" if ct > 0 else None
            pairs.append(UnifiedPair(
                id=f"{canonical_dataset.name}_{idx}",
                code_a=pair.code_a,
                code_b=pair.code_b,
                label=pair.label,
                type=clone_type_str,
                source=canonical_dataset.name,
            ))
        ds = cls(name=canonical_dataset.name, pairs=pairs)
        ds.metadata["version"] = getattr(canonical_dataset, "version", "1.0")
        ds.metadata["language"] = getattr(canonical_dataset, "language", "unknown")
        return ds

    @classmethod
    def from_codepair_list(
        cls,
        name: str,
        pairs: list,
        source: str = "",
    ) -> "UnifiedBenchmarkDataset":
        """Build from a list of objects with code_a/code_b/label attributes."""
        unified = []
        for idx, p in enumerate(pairs):
            unified.append(UnifiedPair(
                id=getattr(p, "id", f"{name}_{idx}"),
                code_a=getattr(p, "code_a", ""),
                code_b=getattr(p, "code_b", ""),
                label=int(getattr(p, "label", 0)),
                type=getattr(p, "type", getattr(p, "clone_type", None)),
                source=source or name,
            ))
        ds = cls(name=name, pairs=unified)
        return ds


class DatasetRegistry:
    """Registry of available datasets with lazy loading.

    Maps dataset names to loader functions that return UnifiedBenchmarkDataset.
    """

    _instance: Optional["DatasetRegistry"] = None
    _loaders: Dict[str, Any]
    _cache: Dict[str, UnifiedBenchmarkDataset]

    def __init__(self) -> None:
        self._loaders = {}
        self._cache = {}

    @classmethod
    def get_instance(cls) -> "DatasetRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register(
        self,
        name: str,
        loader: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._loaders[name] = {
            "loader": loader,
            "metadata": metadata or {},
        }

    def register_canonical_loader(
        self,
        name: str,
        loader_fn: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a loader that returns CanonicalDataset (auto-converted)."""
        def wrapper(**kwargs) -> UnifiedBenchmarkDataset:
            canonical = loader_fn(**kwargs)
            return UnifiedBenchmarkDataset.from_canonical(canonical)
        self.register(name, wrapper, metadata)

    def register_file_loader(
        self,
        name: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a pre-saved JSON file as a dataset."""
        def wrapper() -> UnifiedBenchmarkDataset:
            return UnifiedBenchmarkDataset.load(file_path)
        meta = metadata or {}
        meta["file_path"] = file_path
        self.register(name, wrapper, meta)

    def register_external_loader(
        self,
        name: str,
        data_root: str = "data/datasets",
        split: str = "test",
        max_pairs: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an external dataset loader (poj104, codexglue, etc.)."""
        def wrapper() -> UnifiedBenchmarkDataset:
            try:
                from benchmark.pipeline.external_loader import ExternalDatasetLoader
            except ImportError:
                from src.benchmark.pipeline.external_loader import ExternalDatasetLoader
            ext = ExternalDatasetLoader(data_root=data_root, seed=42)
            canonical = ext.load_by_name(name, split=split, max_pairs=max_pairs)
            return UnifiedBenchmarkDataset.from_canonical(canonical)
        meta = metadata or {}
        meta["data_root"] = data_root
        meta["split"] = split
        meta["max_pairs"] = max_pairs
        self.register(name, wrapper, meta)

    def list_datasets(self) -> List[str]:
        return sorted(self._loaders.keys())

    def has(self, name: str) -> bool:
        return name in self._loaders

    def get_metadata(self, name: str) -> Dict[str, Any]:
        if name not in self._loaders:
            return {}
        return dict(self._loaders[name].get("metadata", {}))

    def load(
        self,
        name: str,
        use_cache: bool = True,
        **kwargs,
    ) -> UnifiedBenchmarkDataset:
        if use_cache and name in self._cache:
            return self._cache[name]
        if name not in self._loaders:
            raise ValueError(
                f"Dataset '{name}' not registered. "
                f"Available: {self.list_datasets()}"
            )
        loader = self._loaders[name]["loader"]
        dataset = loader(**kwargs)
        if use_cache:
            self._cache[name] = dataset
        return dataset

    def load_all(
        self,
        names: Optional[List[str]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, UnifiedBenchmarkDataset]:
        if names is None:
            names = self.list_datasets()
        result = {}
        for name in names:
            try:
                result[name] = self.load(name, use_cache=use_cache, **kwargs)
            except Exception as e:
                print(f"Warning: Failed to load dataset '{name}': {e}")
        return result

    def clear_cache(self) -> None:
        self._cache.clear()
