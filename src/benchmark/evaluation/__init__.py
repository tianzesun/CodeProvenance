"""Evaluation module for benchmark system.

Provides statistical analysis tools for rigorous evaluation:
- Bootstrap confidence intervals
- McNemar's test for classifier comparison
- Confidence interval calculations
- ROC-AUC computation
- Calibration error metrics
"""
from __future__ import annotations

from .statistics.bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_metric,
    paired_bootstrap_test,
)
from .statistics.mcnemar import (
    mcnemar_test,
    mcnemar_test_with_correction,
    compute_mcnemar_table,
)
from .statistics.confidence_interval import (
    wilson_score_interval,
    clopper_pearson_interval,
    normal_approximation_interval,
    compute_confidence_interval,
)
from .metrics.roc_auc import (
    compute_roc_auc,
    compute_roc_curve,
    compute_average_precision,
)
from .metrics.calibration import (
    compute_calibration_error,
    compute_expected_calibration_error,
    compute_maximum_calibration_error,
    plot_calibration_curve,
)
from .certification_report import (
    CertificationReport,
    generate_certification_report,
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