"""Dataset registry for cross-dataset benchmarking.

Maintains a registry of all available datasets with lazy loading support.
"""
from __future__ import annotations

from typing import Dict, List, Callable, Optional, Any
from pathlib import Path

from benchmark.cross_dataset.unified_format import UnifiedDataset


class DatasetRegistry:
    """Registry of all available datasets.

    Supports:
        - Registration of dataset loaders by name
        - Lazy loading on demand
        - Listing available datasets
        - Loading from existing CanonicalDataset via adapter
    """

    def __init__(self):
        self._loaders: Dict[str, Callable[..., UnifiedDataset]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._cache: Dict[str, UnifiedDataset] = {}

    def register(
        self,
        name: str,
        loader: Callable[..., UnifiedDataset],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a dataset loader.

        Args:
            name: Unique dataset identifier
            loader: Callable that returns a UnifiedDataset
            metadata: Optional dataset metadata (language, description, etc.)
        """
        self._loaders[name] = loader
        self._metadata[name] = metadata or {}

    def register_external_loader(
        self,
        name: str,
        external_loader,
        method_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an adapter for ExternalDatasetLoader methods.

        Args:
            name: Dataset name in registry
            external_loader: ExternalDatasetLoader instance
            method_name: Method name to call (e.g., 'load_poj104')
            metadata: Optional metadata
        """
        def loader(**kwargs) -> UnifiedDataset:
            from benchmark.pipeline.loader import CanonicalDataset
            method = getattr(external_loader, method_name)
            canonical = method(**kwargs)
            return UnifiedDataset.from_canonical(canonical, name=name)

        self.register(name, loader, metadata)

    def register_canonical_adapter(
        self,
        name: str,
        canonical_loader: Callable,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a loader that returns CanonicalDataset (auto-converts).

        Args:
            name: Dataset name
            canonical_loader: Callable returning CanonicalDataset
            metadata: Optional metadata
        """
        def loader(**kwargs) -> UnifiedDataset:
            canonical = canonical_loader(**kwargs)
            return UnifiedDataset.from_canonical(canonical, name=name)

        self.register(name, loader, metadata)

    def get(self, name: str, **kwargs) -> UnifiedDataset:
        """Load a dataset by name.

        Args:
            name: Registered dataset name
            **kwargs: Arguments passed to the loader

        Returns:
            UnifiedDataset instance

        Raises:
            KeyError: If dataset not found
        """
        if name in self._cache:
            return self._cache[name]

        if name not in self._loaders:
            raise KeyError(
                f"Dataset '{name}' not found in registry. "
                f"Available: {list(self._loaders.keys())}"
            )

        dataset = self._loaders[name](**kwargs)
        self._cache[name] = dataset
        return dataset

    def clear_cache(self) -> None:
        """Clear all cached datasets."""
        self._cache.clear()

    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all registered datasets with metadata.

        Returns:
            List of dicts with name and metadata for each dataset
        """
        result = []
        for name in sorted(self._loaders.keys()):
            meta = dict(self._metadata.get(name, {}))
            meta["name"] = name
            if name in self._cache:
                ds = self._cache[name]
                meta["size"] = len(ds)
                meta["positive_ratio"] = ds.positive_ratio
            result.append(meta)
        return result

    def has(self, name: str) -> bool:
        """Check if a dataset is registered."""
        return name in self._loaders

    def names(self) -> List[str]:
        """Return sorted list of registered dataset names."""
        return sorted(self._loaders.keys())


def build_default_registry(
    data_root: str = "data/datasets",
    seed: int = 42,
) -> DatasetRegistry:
    """Build a registry with all known external datasets.

    Args:
        data_root: Root directory for benchmark data
        seed: Random seed for reproducibility

    Returns:
        Populated DatasetRegistry
    """
    registry = DatasetRegistry()

    try:
        from benchmark.pipeline.external_loader import ExternalDatasetLoader
        loader = ExternalDatasetLoader(data_root=data_root, seed=seed)
    except ImportError:
        try:
            from src.benchmark.pipeline.external_loader import ExternalDatasetLoader
            loader = ExternalDatasetLoader(data_root=data_root, seed=seed)
        except ImportError:
            return registry

    dataset_methods = {
        "poj104": {
            "method": "load_poj104",
            "metadata": {
                "language": "c",
                "description": "POJ-104 C programs from PKU Online Judge",
                "type": "clone_detection",
            },
        },
        "codexglue_clone": {
            "method": "load_codexglue_clone",
            "metadata": {
                "language": "java",
                "description": "CodeXGLUE Clone Detection (BigCloneBench subset)",
                "type": "clone_detection",
            },
        },
        "codexglue_defect": {
            "method": "load_codexglue_defect",
            "metadata": {
                "language": "c",
                "description": "CodeXGLUE Defect Detection",
                "type": "defect_detection",
            },
        },
        "codesearchnet_python": {
            "method": "load_codesearchnet",
            "kwargs": {"language": "python"},
            "metadata": {
                "language": "python",
                "description": "CodeSearchNet Python functions",
                "type": "code_search",
            },
        },
        "codesearchnet_java": {
            "method": "load_codesearchnet",
            "kwargs": {"language": "java"},
            "metadata": {
                "language": "java",
                "description": "CodeSearchNet Java functions",
                "type": "code_search",
            },
        },
        "kaggle": {
            "method": "load_kaggle_student_code",
            "metadata": {
                "language": "python",
                "description": "Kaggle Student Code Similarity",
                "type": "plagiarism_detection",
            },
        },
    }

    for name, info in dataset_methods.items():
        method_name = info["method"]
        kwargs = dict(info.get("kwargs", {}))
        metadata = info.get("metadata", {})

        def make_loader(mn, kw):
            def _loader(**extra) -> UnifiedDataset:
                combined = {**kw, **extra}
                method = getattr(loader, mn)
                canonical = method(**combined)
                return UnifiedDataset.from_canonical(canonical, name=name)
            return _loader

        registry.register(name, make_loader(method_name, kwargs), metadata)

    return registry
