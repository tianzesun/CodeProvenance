"""Production-grade certification report system for code similarity detection.

This module provides publication-level statistical analysis and certification
reports with:
- Paired statistical tests (McNemar, Wilcoxon)
- Bootstrap confidence intervals
- Effect size calculations (Cohen's d, Cliff's Delta)
- Multiple comparison correction
- Stratified analysis across clone types, difficulty, and language
- Publication-grade HTML/PDF/JSON reports
- Full reproducibility tracking

Architecture:
    certification/
    ├── report_builder.py      - Main report generation
    ├── statistical_tests.py   - McNemar, Wilcoxon, effect sizes
    ├── confidence_intervals.py - Bootstrap and analytic CIs
    ├── effect_size.py         - Cohen's d, Cliff's Delta
    ├── tables.py              - Report table generation
    ├── plots.py               - Visualization generation
    ├── reproducibility.py     - Reproducibility tracking
    ├── stratified.py          - Stratified analysis
    └── templates/             - HTML templates
"""
from __future__ import annotations

from .report_builder import CertificationReportBuilder
from .statistical_tests import (
    mcnemar_test,
    wilcoxon_signed_rank_test,
    paired_statistical_tests,
)
from .confidence_intervals import (
    bootstrap_ci,
    compute_all_confidence_intervals,
)
from .effect_size import (
    cohens_d,
    cliffs_delta,
    interpret_effect_size,
)
from .tables import (
    ResultsTable,
    SignificanceTable,
    StratifiedTable,
)
from .plots import (
    ReliabilityDiagramPlotter,
    DegradationCurvePlotter,
)
from .reproducibility import (
    ReproducibilityInfo,
    compute_reproducibility_hash,
)
from .stratified import (
    StratifiedAnalyzer,
    StratifiedResults,
)
from .models import (
    BenchmarkRecord,
    EngineMetrics,
    ComparisonResult,
)

__all__ = [
    # Report builder
    "CertificationReportBuilder",
    # Statistical tests
    "mcnemar_test",
    "wilcoxon_signed_rank_test",
    "paired_statistical_tests",
    # Confidence intervals
    "bootstrap_ci",
    "compute_all_confidence_intervals",
    # Effect sizes
    "cohens_d",
    "cliffs_delta",
    "interpret_effect_size",
    # Tables
    "ResultsTable",
    "SignificanceTable",
    "StratifiedTable",
    # Plots
    "ReliabilityDiagramPlotter",
    "DegradationCurvePlotter",
    # Reproducibility
    "ReproducibilityInfo",
    "compute_reproducibility_hash",
    # Stratified analysis
    "StratifiedAnalyzer",
    "StratifiedResults",
    # Models
    "BenchmarkRecord",
    "EngineMetrics",
    "ComparisonResult",
]