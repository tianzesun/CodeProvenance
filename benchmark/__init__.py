"""Benchmark system for CodeProvenance.

The benchmark system is the evaluation engine that drives improvement
of the similarity detection algorithms through scientific measurement.

Core architecture:
    - benchmark/similarity/base_engine.py: Strict engine interface
    - benchmark/similarity/engines.py: Concrete engine implementations
    - benchmark/registry.py: Engine registry
    - benchmark/datasets/: Dataset loaders
    - benchmark/pipeline/: Pipeline stages and runner
    - benchmark/metrics/: Evaluation metrics
    - benchmark/reporting/: Result output
"""

from benchmark.registry import EngineRegistry, registry, DetectionEngine
from benchmark.similarity.base_engine import BaseSimilarityEngine
from benchmark.similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)


def _register_builtin_engines() -> None:
    """Register all built-in engines with the global registry."""
    registry.register("token_winnowing", TokenWinnowingEngine)
    registry.register("ast_structural", ASTEngine)
    registry.register("hybrid", HybridEngine)


# Register engines on module load
_register_builtin_engines()


__all__ = [
    "BaseSimilarityEngine",
    "DetectionEngine",
    "EngineRegistry",
    "registry",
    "TokenWinnowingEngine",
    "ASTEngine",
    "HybridEngine",
]