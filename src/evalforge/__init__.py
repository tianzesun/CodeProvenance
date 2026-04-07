"""EvalForge v2 - Production-grade benchmarking framework for plagiarism detection."""

from src.evalforge.core import (
    BaseDetector,
    DetectionResult,
    CodePair,
    CloneType,
    Transformer,
    BenchmarkResult,
)

from src.evalforge.detectors import (
    get_all_detectors,
    get_detector,
    IntegrityDeskAdapter,
    MOSSAdapter,
    JPlagAdapter,
    DolosAdapter,
    NiCadAdapter,
    PMDCPDAdapter,
)

from src.evalforge.core.dataset import (
    Dataset,
    TRANSFORMATIONS,
    load_poj104,
    load_bigclonebench,
    load_codesearchnet,
    load_codexglue_clone,
    get_available_datasets,
)

from src.evalforge.core.metrics import (
    compute_metrics,
    compute_calibration_error,
    compute_robustness,
    compute_confidence_interval,
    compute_icc,
    MetricResult,
)

from src.evalforge.pipelines.runner import (
    BenchmarkRunner,
    Experiment,
    run_standard_benchmark,
)

from src.evalforge.reporting.generator import (
    ReportGenerator,
    generate_standard_report,
)

__version__ = "2.0.0"

__all__ = [
    # Core
    "BaseDetector",
    "DetectionResult",
    "CodePair",
    "CloneType",
    "Transformer",
    "BenchmarkResult",
    
    # Detectors
    "get_all_detectors",
    "get_detector",
    "IntegrityDeskAdapter",
    "MOSSAdapter",
    "JPlagAdapter",
    "DolosAdapter",
    "NiCadAdapter",
    "PMDCPDAdapter",
    
    # Dataset
    "Dataset",
    "TRANSFORMATIONS",
    "load_poj104",
    "load_bigclonebench",
    "load_codesearchnet",
    "load_codexglue_clone",
    "get_available_datasets",
    
    # Metrics
    "compute_metrics",
    "compute_calibration_error",
    "compute_robustness",
    "compute_confidence_interval",
    "compute_icc",
    "MetricResult",
    
    # Pipelines
    "BenchmarkRunner",
    "Experiment",
    "run_standard_benchmark",
    
    # Reporting
    "ReportGenerator",
    "generate_standard_report",
]