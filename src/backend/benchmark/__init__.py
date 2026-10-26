"""Benchmark system for CodeProvenance.

The benchmark system is the evaluation engine that drives improvement
of the similarity detection algorithms through scientific measurement.
"""

from .adapters.ast_baseline import ASTBaselineAdapter
from .adapters.codeprovenance_engine import CodeProvenanceAdapter as CodeProvenanceEngine
from .adapters.codeprovenance_engine_v3 import CodeProvenanceAdapterV3
from .adapters.codeprovenance_engine_v4 import CodeProvenanceAdapterV4
from .adapters.dolos_adapter import DolosBenchmarkEngine
from .adapters.jplag_adapter import JPlagAdapter as JPlagBenchmarkEngine
from .adapters.lexical_baseline import LexicalBaselineAdapter
from .adapters.moss_adapter import MossAdapter as MossBenchmarkEngine
from .adapters.nicad_adapter import NiCadAdapter as NiCadBenchmarkEngine
from .adapters.pmd_adapter import PMDBenchmarkEngine
from .registry import DetectionEngine, EngineRegistry, registry
from .similarity.base_engine import BaseSimilarityEngine
from .similarity.engines import (
    ASTEngine,
    HybridEngine,
    TokenWinnowingEngine,
)

# Benchmark suites
from .suites.official import OfficialBenchmarkSuite, SuiteConfig
from .suites.stress import StressBenchmarkSuite, StressConfig


def _register_builtin_engines() -> None:
    """Register all built-in engines with the global registry."""
    registry.register("token_winnowing", TokenWinnowingEngine)
    registry.register("ast_structural", ASTEngine)
    registry.register("hybrid", HybridEngine)
    registry.register("codeprovenance", CodeProvenanceEngine)
    registry.register("codeprovenance_v3", CodeProvenanceAdapterV3)
    registry.register("codeprovenance_v4", CodeProvenanceAdapterV4)
    registry.register("jplag", JPlagBenchmarkEngine)
    registry.register("nicad", NiCadBenchmarkEngine)
    registry.register("pmd", PMDBenchmarkEngine)
    registry.register("moss", MossBenchmarkEngine)
    registry.register("dolos", DolosBenchmarkEngine)
    registry.register("lexical_baseline", LexicalBaselineAdapter)
    registry.register("ast_baseline", ASTBaselineAdapter)


_register_builtin_engines()