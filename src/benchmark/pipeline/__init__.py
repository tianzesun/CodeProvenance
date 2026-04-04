"""Unified Benchmark Pipeline.

Single authoritative execution model for all datasets, engines, metrics, and reports.
All evaluation must execute through this pipeline - no bypassing.
"""
from benchmark.pipeline.config import BenchmarkConfig
from benchmark.pipeline.loader import DatasetLoader
from benchmark.pipeline.stages import (
    PipelineStage,
    NormalizerStage,
    ParserStage,
    SimilarityStage,
    EvaluationStage,
    MetricsStage,
    ReportingStage
)
from benchmark.pipeline.runner import BenchmarkRunner, BenchmarkRunResult

__all__ = [
    'BenchmarkConfig',
    'DatasetLoader',
    'PipelineStage',
    'NormalizerStage',
    'ParserStage',
    'SimilarityStage',
    'EvaluationStage',
    'MetricsStage',
    'ReportingStage',
    'BenchmarkRunner',
    'BenchmarkRunResult',
]
