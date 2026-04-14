"""McNemar's test for comparing two classifiers.

McNemar's test is a statistical test used on paired nominal data to determine
whether there are significant differences between two correlated proportions.
It's particularly useful for comparing two classifiers on the same test set.

References:
- McNemar, Q. (1947). Note on the sampling error of the difference between
  correlated proportions or percentages.
- Dietterich, T. G. (1998). Approximate statistical tests for comparing
  supervised classification learning algorithms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class McNemarResult:
    """Result of McNemar's test.
    
    Attributes:
        statistic: Chi-square statistic (or exact p-value for small samples).
        p_value: P-value of the test.
        significant: Whether the difference is significant at alpha=0.05.
        contingency_table: 2x2 contingency table.
        b: Count of disagreements where A is correct and B is wrong.
        c: Count of disagreements where B is correct and A is wrong.
        method: Method used ('chi2' or 'exact').
    """
    statistic: float
    p_value: float
    significant: bool
    contingency_table: np.ndarray
    b: int
    c: int
    method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.significant,
            "contingency_table": self.contingency_table.tolist(),
            "b": self.b,
            "c": self.c,
            "method": self.method,
        }


def compute_mcnemar_table(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
) -> Tuple[np.ndarray, int, int]:
    """Compute the 2x2 contingency table for McNemar's test.
    
    The table compares the correctness of two classifiers:
    
                    B correct    B wrong
    A correct         a           b
    A wrong           c           d
    
    Where:
    - a: Both classifiers are correct
    - b: A is correct, B is wrong
    - c: B is correct, A is wrong
    - d: Both classifiers are wrong
    
    Args:
        y_true: Ground truth labels.
        y_pred_a: Predictions from classifier A.
        y_pred_b: Predictions from classifier B.
        
    Returns:
        Tuple of (contingency_table, b, c).
    """
    y_true = np.asarray(y_true)
    y_pred_a = np.asarray(y_pred_a)
    y_pred_b = np.asarray(y_pred_b)
    
    # Compute correctness
    correct_a = (y_pred_a == y_true)
    correct_b = (y_pred_b == y_true)
    
    # Build contingency table
    a = np.sum(correct_a & correct_b)   # Both correct
    b = np.sum(correct_a & ~correct_b)  # A correct, B wrong
    c = np.sum(~correct_a & correct_b)  # B correct, A wrong
    d = np.sum(~correct_a & ~correct_b) # Both wrong
    
    contingency_table = np.array([[a, b], [c, d]])
    
    return contingency_table, int(b), int(c)


def mcnemar_test(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
    correction: bool = True,
) -> McNemarResult:
    """Perform McNemar's test to compare two classifiers."""
    contingency_table, b, c = compute_mcnemar_table(y_true, y_pred_a, y_pred_b)
    
    n = b + c  # Total discordant pairs
    
    if n == 0:
        # No discordant pairs - classifiers are identical
        return McNemarResult(
            statistic=0.0,
            p_value=1.0,
            significant=False,
            contingency_table=contingency_table,
            b=b,
            c=c,
            method="exact",
        )
    
    # For small samples (n < 25), use exact binomial test
    if n < 25:
        # Exact binomial test: P(X >= b) where X ~ Binomial(n, 0.5)
        # Two-tailed p-value
        p_value = 2 * min(
            stats.binom.cdf(min(b, c), n, 0.5),
            stats.binom.sf(max(b, c) - 1, n, 0.5),
        )
        p_value = min(p_value, 1.0)  # Cap at 1.0
        
        return McNemarResult(
            statistic=float(b),  # Report b as statistic for exact test
            p_value=float(p_value),
            significant=p_value < 0.05,
            contingency_table=contingency_table,
            b=b,
            c=c,
            method="exact",
        )
    
    # For larger samples, use chi-square test
    if correction:
        # McNemar's test with continuity correction
        statistic = (abs(b - c) - 1) ** 2 / (b + c)
    else:
        # McNemar's test without continuity correction
        statistic = (b - c) ** 2 / (b + c)
    
    # Chi-square distribution with 1 degree of freedom
    p_value = 1 - stats.chi2.cdf(statistic, df=1)
    
    return McNemarResult(
        statistic=float(statistic),
        p_value=float(p_value),
        significant=p_value < 0.05,
        contingency_table=contingency_table,
        b=b,
        c=c,
        method="chi2",
    )


def mcnemar_test_with_correction(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
) -> McNemarResult:
    """Perform McNemar's test with continuity correction."""
    return mcnemar_test(y_true, y_pred_a, y_pred_b, correction=True)


def compare_classifiers_mcnemar(
    y_true: np.ndarray,
    predictions: Dict[str, np.ndarray],
    alpha: float = 0.05,
) -> Dict[str, McNemarResult]:
    """Compare multiple classifiers pairwise using McNemar's test."""
    classifiers = list(predictions.keys())
    n_classifiers = len(classifiers)
    
    # Bonferroni correction for multiple comparisons
    n_comparisons = n_classifiers * (n_classifiers - 1) // 2
    adjusted_alpha = alpha / n_comparisons if n_comparisons > 0 else alpha
    
    results = {}
    
    for i in range(n_classifiers):
        for j in range(i + 1, n_classifiers):
            name_a = classifiers[i]
            name_b = classifiers[j]
            
            result = mcnemar_test(
                y_true,
                predictions[name_a],
                predictions[name_b],
                correction=True,
            )
            
            # Adjust significance for multiple comparisons
            adjusted_result = McNemarResult(
                statistic=result.statistic,
                p_value=result.p_value,
                significant=result.p_value < adjusted_alpha,
                contingency_table=result.contingency_table,
                b=result.b,
                c=result.c,
                method=result.method,
            )
            
            results[f"{name_a}_vs_{name_b}"] = adjusted_result
    
    return results