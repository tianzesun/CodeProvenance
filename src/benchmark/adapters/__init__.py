"""Benchmark adapters for external tool integration.

Adapters wrap external tools to make them compatible with the benchmark interface.
"""
# Legacy adapter (backward compatibility)
from .codeprovenance_engine import CodeProvenanceAdapter as CodeProvenanceEngine

# New registry-based adapters (versioned strategy pattern)
from .codeprovenance_registry import (
    CodeProvenanceRegistryEngine,
    CodeProvenanceV1,
    CodeProvenanceV2,
    CodeProvenanceV3
)

# External tool adapters
from .jplag_runner import JPlagAdapter as JPlagBenchmarkEngine
from .nicad_runner import NiCadAdapter as NiCadBenchmarkEngine
from .pmd_runner import PMDBenchmarkEngine
from .moss_runner import MossAdapter as MossBenchmarkEngine

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
