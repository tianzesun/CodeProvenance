"""EvalForge v2 - Production-grade benchmarking framework for plagiarism detection."""

from src.backend.evalforge.core import (
    BaseDetector,
    BenchmarkResult,
    CloneType,
    CodePair,
    DetectionResult,
    Transformer,
)
from src.backend.evalforge.core.dataset import (
    TRANSFORMATIONS,
    Dataset,
    get_available_datasets,
    load_bigclonebench,
    load_codesearchnet,
    load_codexglue_clone,
    load_poj104,
)
from src.backend.evalforge.core.metrics import (
    MetricResult,
    compute_calibration_error,
    compute_confidence_interval,
    compute_icc,
    compute_metrics,
    compute_robustness,
)
from src.backend.evalforge.detectors import (
    DolosAdapter,
    IntegrityDeskAdapter,
    JPlagAdapter,
    MOSSAdapter,
    NiCadAdapter,
    PMDCPDAdapter,
    get_all_detectors,
    get_detector,
)
from src.backend.evalforge.pipelines.runner import (
    BenchmarkRunner,
    Experiment,
    run_standard_benchmark,
)
from src.backend.evalforge.reporting.generator import (
    ReportGenerator,
    generate_standard_report,
)

__version__ = "2.0.0"

__all__ = [
    "TRANSFORMATIONS",
    # Core
    "BaseDetector",
    "BenchmarkResult",
    # Pipelines
    "BenchmarkRunner",
    "CloneType",
    "CodePair",
    # Dataset
    "Dataset",
    "DetectionResult",
    "DolosAdapter",
    "Experiment",
    "IntegrityDeskAdapter",
    "JPlagAdapter",
    "MOSSAdapter",
    "MetricResult",
    "NiCadAdapter",
    "PMDCPDAdapter",
    # Reporting
    "ReportGenerator",
    "Transformer",
    "compute_calibration_error",
    "compute_confidence_interval",
    "compute_icc",
    # Metrics
    "compute_metrics",
    "compute_robustness",
    "generate_standard_report",
    # Detectors
    "get_all_detectors",
    "get_available_datasets",
    "get_detector",
    "load_bigclonebench",
    "load_codesearchnet",
    "load_codexglue_clone",
    "load_poj104",
    "run_standard_benchmark",
]
