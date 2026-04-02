"""Unified Benchmark Pipeline.

Single authoritative execution model for all datasets, engines, metrics, and reports.
All evaluation must execute through this pipeline - no bypassing.

This module provides:
- Legacy stages for backward compatibility
- Explicit pipeline phases for improved readability
- PipelineOrchestrator for complete pipeline execution
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
from benchmark.pipeline.runner import BenchmarkRunner

# Explicit pipeline phases for improved readability and onboarding
from benchmark.pipeline.phases import (
    IngestionPhase,
    IngestedFile,
    NormalizationPhase,
    NormalizedCode,
    RepresentationPhase,
    IntermediateRepresentation,
    ComparisonPhase,
    ComparisonResult,
    AggregationPhase,
    AggregatedResult,
    EvaluationPhase,
    EvaluationResult,
    ReportingPhase,
    ReportOutput,
)

# Pipeline orchestrator for complete pipeline execution
from benchmark.pipeline.orchestrator import (
    PipelineOrchestrator,
    PipelineResult,
)

__all__ = [
    # Legacy stages (backward compatibility)
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
    # Explicit pipeline phases
    'IngestionPhase',
    'IngestedFile',
    'NormalizationPhase',
    'NormalizedCode',
    'RepresentationPhase',
    'IntermediateRepresentation',
    'ComparisonPhase',
    'ComparisonResult',
    'AggregationPhase',
    'AggregatedResult',
    'EvaluationPhase',
    'EvaluationResult',
    'ReportingPhase',
    'ReportOutput',
    # Pipeline orchestrator
    'PipelineOrchestrator',
    'PipelineResult',
]
