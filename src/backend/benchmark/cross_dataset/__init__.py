"""Cross-dataset benchmark system.

Provides unified dataset format, tool adapters, evaluation runner,
and cross-dataset evaluation capabilities.
"""
from __future__ import annotations

from src.backend.benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator, CrossEvalReport
from src.backend.benchmark.cross_dataset.dataset_catalog import (
    DATASETS,
    DatasetCatalog,
    DatasetEntry,
    generate_pairs,
    normalize_code,
)
from src.backend.benchmark.cross_dataset.dataset_registry import DatasetRegistry
from src.backend.benchmark.cross_dataset.evaluation_runner import EvaluationResult, EvaluationRunner
from src.backend.benchmark.cross_dataset.results import (
    CrossEvalSummary,
    DatasetResult,
    RankingEntry,
    ToolResult,
)
from src.backend.benchmark.cross_dataset.tool_adapters import (
    ALL_TOOLS,
    BaseToolAdapter,
    CosineTFIDFAdapter,
    DolosAdapter,
    EngineAdapter,
    EngineToolAdapter,
    IntegrityDeskAdapter,
    JaccardToolAdapter,
    JPlagAdapter,
    LineOverlapToolAdapter,
    MOSSAdapter,
    NgramAdapter,
    TokenJaccardAdapter,
    ToolAdapter,
)
from src.backend.benchmark.cross_dataset.unified_format import (
    UnifiedBenchmarkDataset,
    UnifiedDataset,
    UnifiedPair,
)

__all__ = [
    "ALL_TOOLS",
    "DATASETS",
    "BaseToolAdapter",
    "CosineTFIDFAdapter",
    "CrossDatasetEvaluator",
    "CrossEvalReport",
    "CrossEvalSummary",
    "DatasetCatalog",
    "DatasetEntry",
    "DatasetRegistry",
    "DatasetResult",
    "DolosAdapter",
    "EngineAdapter",
    "EngineToolAdapter",
    "EvaluationResult",
    "EvaluationRunner",
    "IntegrityDeskAdapter",
    "JPlagAdapter",
    "JaccardToolAdapter",
    "LineOverlapToolAdapter",
    "MOSSAdapter",
    "NgramAdapter",
    "RankingEntry",
    "TokenJaccardAdapter",
    "ToolAdapter",
    "ToolResult",
    "UnifiedBenchmarkDataset",
    "UnifiedDataset",
    "UnifiedPair",
    "generate_pairs",
    "normalize_code",
]
