"""Explicit Pipeline Phases for Code Similarity Detection.

Provides clear, explicit pipeline phases for improved readability and onboarding:
- IngestionPhase: Phase 1 - Load and validate input files
- NormalizationPhase: Phase 2 - Code normalization
- RepresentationPhase: Phase 3 - IR generation
- ComparisonPhase: Phase 4 - Similarity computation
- AggregationPhase: Phase 5 - Result aggregation
- EvaluationPhase: Phase 6 - Metric evaluation
- ReportingPhase: Phase 7 - Report generation

Each phase is:
- Pure function (no side effects)
- Stateless (given same inputs -> same outputs)
- Deterministic
- Well-documented with clear inputs/outputs
"""
from benchmark.pipeline.phases.ingest import (
    IngestionPhase,
    IngestedFile,
)
from benchmark.pipeline.phases.normalize import (
    NormalizationPhase,
    NormalizedCode,
)
from benchmark.pipeline.phases.represent import (
    RepresentationPhase,
    IntermediateRepresentation,
)
from benchmark.pipeline.phases.compare import (
    ComparisonPhase,
    ComparisonResult,
)
from benchmark.pipeline.phases.aggregate import (
    AggregationPhase,
    AggregatedResult,
)
from benchmark.pipeline.phases.evaluate import (
    EvaluationPhase,
    EvaluationResult,
)
from benchmark.pipeline.phases.report import (
    ReportingPhase,
    ReportOutput,
)

__all__ = [
    # Phase 1: Ingestion
    "IngestionPhase",
    "IngestedFile",
    # Phase 2: Normalization
    "NormalizationPhase",
    "NormalizedCode",
    # Phase 3: Representation
    "RepresentationPhase",
    "IntermediateRepresentation",
    # Phase 4: Comparison
    "ComparisonPhase",
    "ComparisonResult",
    # Phase 5: Aggregation
    "AggregationPhase",
    "AggregatedResult",
    # Phase 6: Evaluation
    "EvaluationPhase",
    "EvaluationResult",
    # Phase 7: Reporting
    "ReportingPhase",
    "ReportOutput",
]