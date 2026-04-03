"""Cross-dataset benchmark system.

Provides unified dataset format, tool adapters, evaluation runner,
and cross-dataset evaluation orchestration.
"""
from benchmark.cross_dataset.unified_format import UnifiedBenchmarkDataset, DatasetRegistry
from benchmark.cross_dataset.tool_adapters import ToolAdapter, EngineToolAdapter
from benchmark.cross_dataset.eval_runner import EvaluationRunner, EvaluationResult
from benchmark.cross_dataset.cross_eval import CrossDatasetEvaluator, CrossEvalReport

__all__ = [
    "UnifiedBenchmarkDataset",
    "DatasetRegistry",
    "ToolAdapter",
    "EngineToolAdapter",
    "EvaluationRunner",
    "EvaluationResult",
    "CrossDatasetEvaluator",
    "CrossEvalReport",
]
