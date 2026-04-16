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
from .dolos_adapter import DolosAdapter
from .lexical_baseline import LexicalBaselineAdapter
from .ast_baseline import ASTBaselineAdapter

__all__ = [
    # Legacy
    'CodeProvenanceEngine',
    # External tools
    'JPlagBenchmarkEngine',
    'NiCadBenchmarkEngine',
    'PMDBenchmarkEngine',
    'MossBenchmarkEngine'
]
