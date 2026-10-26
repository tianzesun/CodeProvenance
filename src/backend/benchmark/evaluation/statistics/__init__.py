"""Statistical analysis tools for benchmark evaluation.

Provides rigorous statistical methods for evaluating classifier performance:
- Bootstrap confidence intervals
- McNemar's test for classifier comparison
- Various confidence interval methods
"""
from __future__ import annotations

from .bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_metric,
    paired_bootstrap_test,
)
from .confidence_interval import (
    clopper_pearson_interval,
    compute_confidence_interval,
    normal_approximation_interval,
    wilson_score_interval,
)
from .mcnemar import (
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
]