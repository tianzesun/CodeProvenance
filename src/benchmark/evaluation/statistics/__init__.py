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
from .mcnemar import (
    mcnemar_test,
    mcnemar_test_with_correction,
    compute_mcnemar_table,
)
from .confidence_interval import (
    wilson_score_interval,
    clopper_pearson_interval,
    normal_approximation_interval,
    compute_confidence_interval,
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