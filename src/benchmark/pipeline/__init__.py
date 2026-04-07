"""Unified Benchmark Pipeline.

Single authoritative execution model for all datasets, engines, metrics, and reports.
All evaluation must execute through this pipeline - no bypassing.
"""
from src.benchmark.pipeline.config import BenchmarkConfig
from src.benchmark.pipeline.loader import DatasetLoader
from src.benchmark.pipeline.stages import (
    PipelineStage,
    NormalizerStage,
    ParserStage,
    SimilarityStage,
    EvaluationStage,
    MetricsStage,
    ReportingStage
)
from src.benchmark.pipeline.runner import BenchmarkRunner, BenchmarkRunResult

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
