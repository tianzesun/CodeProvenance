"""Benchmark system for CodeProvenance.

The benchmark system is the evaluation engine that drives improvement
of the similarity detection algorithms through scientific measurement.
"""

from .registry import EngineRegistry, registry, DetectionEngine
from .similarity.base_engine import BaseSimilarityEngine
from .similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)
from .adapters.codeprovenance_engine import CodeProvenanceAdapter as CodeProvenanceEngine
from .adapters.codeprovenance_engine_v2 import CodeProvenanceEngineV2
from .adapters.codeprovenance_engine_v3 import CodeProvenanceEngineV3
from .adapters.codeprovenance_engine_v4 import CodeProvenanceEngineV4
from .adapters.jplag_adapter import JPlagAdapter as JPlagBenchmarkEngine
from .adapters.nicad_adapter import NiCadAdapter as NiCadBenchmarkEngine
from .adapters.pmd_adapter import PMDBenchmarkEngine
from .adapters.moss_adapter import MossAdapter as MossBenchmarkEngine
from .adapters.dolos_adapter import DolosBenchmarkEngine
from .adapters.lexical_baseline import LexicalBaselineAdapter
from .adapters.ast_baseline import ASTBaselineAdapter


def _register_builtin_engines() -> None:
    """Register all built-in engines with the global registry."""
    registry.register("token_winnowing", TokenWinnowingEngine)
    registry.register("ast_structural", ASTEngine)
    registry.register("hybrid", HybridEngine)
    registry.register("codeprovenance", CodeProvenanceEngine)
    registry.register("codeprovenance_v2", CodeProvenanceEngineV2)
    registry.register("codeprovenance_v3", CodeProvenanceEngineV3)
    registry.register("jplag", JPlagBenchmarkEngine)
    registry.register("nicad", NiCadBenchmarkEngine)
    registry.register("pmd", PMDBenchmarkEngine)
    registry.register("moss", MossBenchmarkEngine)
    registry.register("dolos", DolosBenchmarkEngine)
    registry.register("lexical_baseline", LexicalBaselineAdapter)
    registry.register("ast_baseline", ASTBaselineAdapter)
    registry.register("codeprovenance_v4", CodeProvenanceEngineV4)


_register_builtin_engines()
