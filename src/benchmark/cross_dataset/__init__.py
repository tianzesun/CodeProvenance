"""Cross-dataset benchmark system.

Provides unified dataset format, tool adapters, evaluation runner,
and cross-dataset evaluation capabilities.
"""
from __future__ import annotations

from src.benchmark.cross_dataset.unified_format import UnifiedDataset, UnifiedPair, UnifiedBenchmarkDataset
from src.benchmark.cross_dataset.dataset_registry import DatasetRegistry
from src.benchmark.cross_dataset.dataset_catalog import (
    DATASETS, DatasetEntry, DatasetCatalog,
    normalize_code, generate_pairs,
)
from src.benchmark.cross_dataset.tool_adapters import (
    ToolAdapter, BaseToolAdapter,
    EngineToolAdapter, EngineAdapter,
    JaccardToolAdapter, LineOverlapToolAdapter,
    TokenJaccardAdapter, NgramAdapter, CosineTFIDFAdapter,
    MOSSAdapter, JPlagAdapter, DolosAdapter, IntegrityDeskAdapter,
    ALL_TOOLS,
)
from src.benchmark.cross_dataset.evaluation_runner import EvaluationRunner, EvaluationResult
from src.benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator, CrossEvalReport
from src.benchmark.cross_dataset.results import (
    DatasetResult,
    ToolResult,
    CrossEvalSummary,
    RankingEntry,
)

__all__ = [
    "DATASETS",
    "DatasetEntry",
    "DatasetCatalog",
    "normalize_code",
    "generate_pairs",
    "UnifiedDataset",
    "UnifiedPair",
    "UnifiedBenchmarkDataset",
    "DatasetRegistry",
    "ToolAdapter",
    "BaseToolAdapter",
    "EngineToolAdapter",
    "EngineAdapter",
    "JaccardToolAdapter",
    "LineOverlapToolAdapter",
    "TokenJaccardAdapter",
    "NgramAdapter",
    "CosineTFIDFAdapter",
    "MOSSAdapter",
    "JPlagAdapter",
    "DolosAdapter",
    "IntegrityDeskAdapter",
    "ALL_TOOLS",
    "EvaluationRunner",
    "EvaluationResult",
    "CrossDatasetEvaluator",
    "CrossEvalReport",
    "DatasetResult",
    "ToolResult",
    "CrossEvalSummary",
    "RankingEntry",
]
