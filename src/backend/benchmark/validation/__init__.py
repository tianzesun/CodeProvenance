"""Benchmark validation framework for industry-grade accuracy.

This module provides comprehensive validation tools to ensure the benchmark
framework meets publication-ready standards for accuracy, reproducibility,
and statistical rigor.
"""

from src.backend.benchmark.validation.api_integration import (
    BenchmarkValidationRequest,
    BenchmarkValidationResponse,
    BenchmarkValidationService,
    ValidationAPIEndpoints,
)
from src.backend.benchmark.validation.label_validators import (
    LabelValidationResult,
    LabelValidator,
)
from src.backend.benchmark.validation.metric_validators import (
    MetricValidationReport,
    MetricValidationResult,
    MetricValidator,
)
from src.backend.benchmark.validation.reproducibility import (
    BenchmarkParameters,
    DatasetChecksum,
    DependencyInfo,
    RandomSeedInfo,
    ReproducibilityManifest,
    ToolVersionInfo,
    calculate_directory_checksum,
    calculate_file_checksum,
)
from src.backend.benchmark.validation.statistical_rigor import (
    ConfidenceInterval,
    ConfidenceIntervalCalculator,
    RobustnessAnalyzer,
    RobustnessResult,
    SignificanceTest,
    SignificanceTester,
    StatisticalAnalyzer,
    StatisticalReport,
)
from src.backend.benchmark.validation.tool_validators import (
    ToolValidationReport,
    ToolValidationResult,
    ToolValidator,
)

__all__ = [
    "BenchmarkParameters",
    "BenchmarkValidationRequest",
    "BenchmarkValidationResponse",
    "BenchmarkValidationService",
    "ConfidenceInterval",
    "ConfidenceIntervalCalculator",
    "DatasetChecksum",
    "DependencyInfo",
    "LabelValidationResult",
    "LabelValidator",
    "MetricValidationReport",
    "MetricValidationResult",
    "MetricValidator",
    "RandomSeedInfo",
    "ReproducibilityManifest",
    "RobustnessAnalyzer",
    "RobustnessResult",
    "SignificanceTest",
    "SignificanceTester",
    "StatisticalAnalyzer",
    "StatisticalReport",
    "ToolValidationReport",
    "ToolValidationResult",
    "ToolValidator",
    "ToolVersionInfo",
    "ValidationAPIEndpoints",
    "calculate_directory_checksum",
    "calculate_file_checksum",
]
