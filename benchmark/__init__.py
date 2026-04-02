"""Benchmark system for CodeProvenance.

The benchmark system is the evaluation engine that drives improvement
of the similarity detection algorithms through scientific measurement.
"""

from benchmark.registry import EngineRegistry, registry, DetectionEngine
from benchmark.similarity.base_engine import BaseSimilarityEngine
from benchmark.similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)
from benchmark.adapters.codeprovenance_engine import CodeProvenanceEngine
from benchmark.adapters.codeprovenance_engine_v2 import CodeProvenanceEngineV2
from benchmark.adapters.codeprovenance_engine_v3 import CodeProvenanceEngineV3
from benchmark.adapters.codeprovenance_engine_v4 import CodeProvenanceEngineV4
from benchmark.adapters.jplag_runner import JPlagBenchmarkEngine
from benchmark.adapters.nicad_runner import NiCadBenchmarkEngine
from benchmark.adapters.pmd_runner import PMDBenchmarkEngine
from benchmark.adapters.moss_runner import MossBenchmarkEngine
from benchmark.adapters.dolos_runner import DolosBenchmarkEngine


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
    registry.register("codeprovenance_v4", CodeProvenanceEngineV4)


_register_builtin_engines()
