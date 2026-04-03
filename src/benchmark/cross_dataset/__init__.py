"""Cross-dataset benchmark system.

Provides unified dataset format, tool adapters, evaluation runner,
and cross-dataset evaluation capabilities.
"""
from __future__ import annotations

from benchmark.cross_dataset.unified_format import UnifiedDataset, UnifiedPair, UnifiedBenchmarkDataset
from benchmark.cross_dataset.dataset_registry import DatasetRegistry
from benchmark.cross_dataset.tool_adapters import (
    ToolAdapter, BaseToolAdapter,
    EngineToolAdapter, EngineAdapter,
    JaccardToolAdapter, LineOverlapToolAdapter,
    TokenJaccardAdapter, NgramAdapter, CosineTFIDFAdapter,
)
from benchmark.cross_dataset.evaluation_runner import EvaluationRunner, EvaluationResult
from benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator, CrossEvalReport
from benchmark.cross_dataset.results import (
    DatasetResult,
    ToolResult,
    CrossEvalSummary,
    RankingEntry,
)

__all__ = [
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
    "EvaluationRunner",
    "EvaluationResult",
    "CrossDatasetEvaluator",
    "CrossEvalReport",
    "DatasetResult",
    "ToolResult",
    "CrossEvalSummary",
    "RankingEntry",
]
