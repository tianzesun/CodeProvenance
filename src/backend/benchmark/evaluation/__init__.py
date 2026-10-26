"""Evaluation module for benchmark system.

Provides statistical analysis tools for rigorous evaluation:
- Bootstrap confidence intervals
- McNemar's test for classifier comparison
- Confidence interval calculations
- ROC-AUC computation
- Calibration error metrics
"""
from __future__ import annotations

from .certification_report import (
    CertificationReport,
    generate_certification_report,
)
from .metrics.calibration import (
    compute_calibration_error,
    compute_expected_calibration_error,
    compute_maximum_calibration_error,
    plot_calibration_curve,
)
from .metrics.roc_auc import (
    compute_average_precision,
    compute_roc_auc,
    compute_roc_curve,
)
from .statistics.bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_metric,
    paired_bootstrap_test,
)
from .statistics.confidence_interval import (
    clopper_pearson_interval,
    compute_confidence_interval,
    normal_approximation_interval,
    wilson_score_interval,
)
from .statistics.mcnemar import (
    compute_mcnemar_table,
    mcnemar_test,
    mcnemar_test_with_correction,
)

__all__ = [
    # Bootstrap
    "bootstrap_confidence_interval",
    "bootstrap_metric",
    "paired_bootstrap_test",
    # McNemar
    "mcnemar_test",
    "mcnemar_test_with_correction",
    "compute_mcnemar_table",
    # Confidence intervals
    "wilson_score_interval",
    "clopper_pearson_interval",
    "normal_approximation_interval",
    "compute_confidence_interval",
    # ROC-AUC
    "compute_roc_auc",
    "compute_roc_curve",
    "compute_average_precision",
    # Calibration
    "compute_calibration_error",
    "compute_expected_calibration_error",
    "compute_maximum_calibration_error",
    "plot_calibration_curve",
    # Certification
    "CertificationReport",
    "generate_certification_report",
]