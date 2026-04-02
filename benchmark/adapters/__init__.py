"""Benchmark adapters for external tool integration.

Adapters wrap external tools to make them compatible with the benchmark interface.
"""
# Legacy adapter (backward compatibility)
from benchmark.adapters.codeprovenance_engine import CodeProvenanceEngine

# New registry-based adapters (versioned strategy pattern)
from benchmark.adapters.codeprovenance_registry import (
    CodeProvenanceRegistryEngine,
    CodeProvenanceV1,
    CodeProvenanceV2,
    CodeProvenanceV3
)

# External tool adapters
from benchmark.adapters.jplag_runner import JPlagBenchmarkEngine
from benchmark.adapters.nicad_runner import NiCadBenchmarkEngine
from benchmark.adapters.pmd_runner import PMDBenchmarkEngine
from benchmark.adapters.moss_runner import MossBenchmarkEngine

__all__ = [
    # Legacy
    'CodeProvenanceEngine',
    # Registry-based (versioned)
    'CodeProvenanceRegistryEngine',
    'CodeProvenanceV1',
    'CodeProvenanceV2',
    'CodeProvenanceV3',
    # External tools
    'JPlagBenchmarkEngine',
    'NiCadBenchmarkEngine',
    'PMDBenchmarkEngine',
    'MossBenchmarkEngine'
]
