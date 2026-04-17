"""Benchmark adapters for external tool integration.

Adapters wrap external tools to make them compatible with the benchmark interface.
"""
# Legacy adapter (backward compatibility)
from .codeprovenance_engine import CodeProvenanceAdapter as CodeProvenanceEngine

# New registry-based adapters (versioned strategy pattern)

# External tool adapters
from .jplag_adapter import JPlagAdapter as JPlagBenchmarkEngine
from .nicad_adapter import NiCadAdapter as NiCadBenchmarkEngine
from .pmd_adapter import PMDBenchmarkEngine
from .moss_adapter import MossAdapter as MossBenchmarkEngine
from .dolos_adapter import DolosBenchmarkEngine
from .lexical_baseline import LexicalBaselineAdapter
from .ast_baseline import ASTBaselineAdapter
from .registry import adapter_registry, initialize_registry


_REGISTRY_READY = False


def _ensure_registry() -> None:
    """
    Initialize adapter registry once for backward-compatible helper lookups.
    """
    global _REGISTRY_READY
    if _REGISTRY_READY:
        return
    initialize_registry()
    _REGISTRY_READY = True


def get_adapter(name: str):
    """
    Return an instantiated adapter by registry name.
    """
    _ensure_registry()
    metadata = adapter_registry.get(name)
    if metadata is None:
        raise KeyError(f"Unknown adapter: {name}")
    return metadata.adapter_class()

__all__ = [
    # Legacy
    'CodeProvenanceEngine',
    # External tools
    'JPlagBenchmarkEngine',
    'NiCadBenchmarkEngine',
    'PMDBenchmarkEngine',
    'MossBenchmarkEngine',
    'DolosBenchmarkEngine',
    'get_adapter',
]
