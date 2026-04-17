"""Dataset registry for cross-dataset benchmarking.

Maintains a registry of all available datasets with lazy loading support.
"""
from __future__ import annotations

from typing import Dict, List, Callable, Optional, Any
from pathlib import Path

from src.backend.benchmark.cross_dataset.unified_format import UnifiedDataset


class DatasetRegistry:
    """Registry of all available datasets.

    Supports:
        - Registration of dataset loaders by name
        - Lazy loading on demand
        - Listing available datasets
        - Loading from existing CanonicalDataset via adapter
        - Singleton pattern via get_instance()
    """

    _instance: Optional["DatasetRegistry"] = None

    def __init__(self):
        self._loaders: Dict[str, Callable[..., UnifiedDataset]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._cache: Dict[str, UnifiedDataset] = {}

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
        loader: Callable[..., UnifiedDataset],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._loaders[name] = loader
        self._metadata[name] = metadata or {}

    def register_external_loader(
        self,
        name: str,
        data_root: str = "data/datasets",
        split: str = "test",
        max_pairs: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an external dataset loader."""
        import importlib.util
        def wrapper(**kwargs) -> UnifiedDataset:
            project_root = Path(__file__).resolve().parents[3]
            src = project_root / "src"
            loader_mod_path = src / "benchmark" / "pipeline" / "loader.py"
            external_mod_path = src / "benchmark" / "pipeline" / "external_loader.py"
            import sys
            loader_spec = importlib.util.spec_from_file_location("bp_loader", loader_mod_path)
            loader_mod = importlib.util.module_from_spec(loader_spec)
            sys.modules["bp_loader"] = loader_mod
            sys.modules["benchmark.pipeline.loader"] = loader_mod
            loader_spec.loader.exec_module(loader_mod)
            ext_spec = importlib.util.spec_from_file_location("bp_external", external_mod_path)
            ext_mod = importlib.util.module_from_spec(ext_spec)
            ext_spec.loader.exec_module(ext_mod)
            ExternalDatasetLoader = ext_mod.ExternalDatasetLoader
            ext = ExternalDatasetLoader(data_root=data_root, seed=42)
            canonical = ext.load_by_name(name, split=split, max_pairs=max_pairs)
            return UnifiedDataset.from_canonical(canonical, name=name)
        meta = metadata or {}
        meta["data_root"] = data_root
        meta["split"] = split
        meta["max_pairs"] = max_pairs
        self.register(name, wrapper, meta)

    def register_canonical_adapter(
        self,
        name: str,
        canonical_loader: Callable,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        def loader(**kwargs) -> UnifiedDataset:
            canonical = canonical_loader(**kwargs)
            return UnifiedDataset.from_canonical(canonical, name=name)
        self.register(name, loader, metadata)

    def load(self, name: str, use_cache: bool = True, **kwargs) -> UnifiedDataset:
        if use_cache and name in self._cache:
            return self._cache[name]
        if name not in self._loaders:
            raise ValueError(
                f"Dataset '{name}' not registered. "
                f"Available: {self.list_datasets()}"
            )
        dataset = self._loaders[name](**kwargs)
        if use_cache:
            self._cache[name] = dataset
        return dataset

    def get(self, name: str, **kwargs) -> UnifiedDataset:
        return self.load(name, **kwargs)

    def clear_cache(self) -> None:
        self._cache.clear()

    def list_datasets(self) -> List[str]:
        return sorted(self._loaders.keys())

    def has(self, name: str) -> bool:
        return name in self._loaders

    def names(self) -> List[str]:
        return sorted(self._loaders.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        if name not in self._loaders:
            return {}
        return dict(self._metadata.get(name, {}))

    def load_all(
        self,
        names: Optional[List[str]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, UnifiedDataset]:
        if names is None:
            names = self.list_datasets()
        result = {}
        for name in names:
            try:
                result[name] = self.load(name, use_cache=use_cache, **kwargs)
            except Exception as e:
                print(f"Warning: Failed to load dataset '{name}': {e}")
        return result

    def has(self, name: str) -> bool:
        return name in self._loaders

    def names(self) -> List[str]:
        return sorted(self._loaders.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        if name not in self._loaders:
            return {}
        return dict(self._metadata.get(name, {}))

    def load_all(
        self,
        names: Optional[List[str]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, UnifiedDataset]:
        if names is None:
            names = self.list_datasets()
        result = {}
        for name in names:
            try:
                result[name] = self.load(name, use_cache=use_cache, **kwargs)
            except Exception as e:
                print(f"Warning: Failed to load dataset '{name}': {e}")
        return result


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
        from src.backend.benchmark.pipeline.external_loader import ExternalDatasetLoader
    except ImportError:
        try:
            from backend.benchmark.pipeline.external_loader import ExternalDatasetLoader
        except ImportError as e:
            raise ImportError(
                "Failed to import ExternalDatasetLoader. "
                "Check PYTHONPATH and package layout."
            ) from e

    loader = ExternalDatasetLoader(data_root=data_root, seed=seed)

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
        "kaggle_student_code": {
            "method": "load_kaggle_student_code",
            "metadata": {
                "language": "python",
                "description": "Kaggle Student Code Similarity",
                "type": "plagiarism_detection",
            },
        },
        "human_eval": {
            "method": "load_human_eval",
            "metadata": {
                "language": "python",
                "description": "HumanEval Python code generation benchmark",
                "type": "generation_exec",
            },
        },
        "mbpp": {
            "method": "load_mbpp",
            "metadata": {
                "language": "python",
                "description": "Mostly Basic Python Problems",
                "type": "generation_exec",
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
