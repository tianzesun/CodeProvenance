"""Cross-dataset benchmark system.

Provides unified dataset format, tool adapters, evaluation runner,
and cross-dataset evaluation capabilities.

Modules:
    unified_format: Canonical dataset format (id, code_a, code_b, label, type, source)
    dataset_registry: Registry of all available datasets
    tool_adapters: Adapters wrapping engines to output 0-1 scores
    evaluation_runner: Computes Precision/Recall/F1, ROC-AUC, PR-AUC
    results: Structured result objects with per-dataset rankings, variance, stability
"""
from __future__ import annotations

from benchmark.cross_dataset.unified_format import UnifiedDataset, UnifiedPair
from benchmark.cross_dataset.dataset_registry import DatasetRegistry
from benchmark.cross_dataset.tool_adapters import ToolAdapter, BaseToolAdapter
from benchmark.cross_dataset.evaluation_runner import EvaluationRunner, EvaluationResult
from benchmark.cross_dataset.results import (
    DatasetResult,
    ToolResult,
    CrossEvalSummary,
    RankingEntry,
)

__all__ = [
    "UnifiedDataset",
    "UnifiedPair",
    "DatasetRegistry",
    "ToolAdapter",
    "BaseToolAdapter",
    "EvaluationRunner",
    "EvaluationResult",
    "DatasetResult",
    "ToolResult",
    "CrossEvalSummary",
    "RankingEntry",
]
