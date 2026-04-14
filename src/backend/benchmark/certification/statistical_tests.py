"""Statistical tests for classifier comparison.

Implements rigorous paired statistical tests for comparing code similarity
detectors on the same dataset. These tests are mandatory for publication-grade
certification reports.

Statistical Tests:
    - McNemar's Test: For classification decision differences
    - Wilcoxon Signed-Rank Test: For score distribution differences
    - Paired Bootstrap Test: For metric differences with confidence intervals

References:
    - McNemar, Q. (1947). Note on the sampling error of the difference between
      correlated proportions or percentages.
    - Wilcoxon, F. (1945). Individual comparisons by ranking methods.
    - Dietterich, T. G. (1998). Approximate statistical tests for comparing
      supervised classification learning algorithms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class McNemarResult:
    """Result of McNemar's test.

    Attributes:
        statistic: Chi-square statistic (or b for exact test).
        p_value: P-value of the test.
        significant: Whether difference is significant at alpha=0.05.
        contingency_table: 2x2 contingency table.
        b: Count where A correct, B wrong.
        c: Count where B correct, A wrong.
        method: Test method used ('chi2' or 'exact').
        corrected_alpha: Alpha level after multiple comparison correction.
    """
    statistic: float
    p_value: float
    significant: bool
    contingency_table: np.ndarray
    b: int
    c: int
    method: str
    corrected_alpha: float = 0.05

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
            "corrected_alpha": self.corrected_alpha,
        }


@dataclass(frozen=True)
class WilcoxonResult:
    """Result of Wilcoxon signed-rank test.

    Attributes:
        statistic: Wilcoxon statistic (sum of signed ranks).
        p_value: P-value of the test.
        significant: Whether difference is significant at alpha=0.05.
        n_pairs: Number of non-tied pairs.
        mean_diff: Mean difference in scores.
        std_diff: Standard deviation of differences.
        method: Test method used ('exact' or 'approximate').
    """
    statistic: float
    p_value: float
    significant: bool
    n_pairs: int
    mean_diff: float
    std_diff: float
    method: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.significant,
            "n_pairs": self.n_pairs,
            "mean_diff": self.mean_diff,
            "std_diff": self.std_diff,
            "method": self.method,
        }


@dataclass(frozen=True)
class PairedTestResults:
    """Combined results from paired statistical tests.

    Attributes:
        mcnemar: McNemar's test result.
        wilcoxon: Wilcoxon signed-rank test result.
        bootstrap_pvalue: P-value from paired bootstrap test.
        bootstrap_significant: Whether bootstrap test is significant.
        mean_diff: Mean difference in scores.
        ci_diff: Confidence interval for difference.
    """
    mcnemar: McNemarResult
    wilcoxon: WilcoxonResult
    bootstrap_pvalue: float
    bootstrap_significant: bool
    mean_diff: float
    ci_diff: Tuple[float, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mcnemar": self.mcnemar.to_dict(),
            "wilcoxon": self.wilcoxon.to_dict(),
            "bootstrap_pvalue": self.bootstrap_pvalue,
            "bootstrap_significant": self.bootstrap_significant,
            "mean_diff": self.mean_diff,
            "ci_diff": list(self.ci_diff),
        }


def compute_mcnemar_table(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
) -> Tuple[np.ndarray, int, int]:
    """Compute 2x2 contingency table for McNemar's test.

    The table compares correctness of two classifiers:

                        B correct    B wrong
        A correct         a           b
        A wrong           c           d

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
    alpha: float = 0.05,
) -> McNemarResult:
    """Perform McNemar's test to compare two classifiers.

    McNemar's test is a paired statistical test for comparing the classification
    decisions of two classifiers on the same test set. It tests the null hypothesis
    that the two classifiers have the same error rate.

    For small samples (n < 25), uses exact binomial test.
    For larger samples, uses chi-square test with optional continuity correction.

    Args:
        y_true: Ground truth labels.
        y_pred_a: Predictions from classifier A.
        y_pred_b: Predictions from classifier B.
        correction: Whether to apply continuity correction for chi-square test.
        alpha: Significance level (default 0.05).

    Returns:
        McNemarResult with test statistics and p-value.

    Raises:
        ValueError: If input arrays have different lengths.
    """
    y_true = np.asarray(y_true)
    y_pred_a = np.asarray(y_pred_a)
    y_pred_b = np.asarray(y_pred_b)

    if not (len(y_true) == len(y_pred_a) == len(y_pred_b)):
        raise ValueError(
            f"Input arrays must have same length: "
            f"y_true={len(y_true)}, y_pred_a={len(y_pred_a)}, y_pred_b={len(y_pred_b)}"
        )

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
            corrected_alpha=alpha,
        )

    # For small samples, use exact binomial test
    if n < 25:
        # Exact binomial test: P(X >= min(b,c)) where X ~ Binomial(n, 0.5)
        # Two-tailed p-value
        p_value = 2 * min(
            stats.binom.cdf(min(b, c), n, 0.5),
            stats.binom.sf(max(b, c) - 1, n, 0.5),
        )
        p_value = min(p_value, 1.0)

        return McNemarResult(
            statistic=float(b),
            p_value=float(p_value),
            significant=p_value < alpha,
            contingency_table=contingency_table,
            b=b,
            c=c,
            method="exact",
            corrected_alpha=alpha,
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
        significant=p_value < alpha,
        contingency_table=contingency_table,
        b=b,
        c=c,
        method="chi2",
        corrected_alpha=alpha,
    )


def wilcoxon_signed_rank_test(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    alternative: str = "two-sided",
    alpha: float = 0.05,
) -> WilcoxonResult:
    """Perform Wilcoxon signed-rank test for paired score distributions.

    The Wilcoxon signed-rank test is a non-parametric test that compares
    the distributions of paired observations. It tests whether the median
    difference is zero.

    This is appropriate for comparing similarity scores from two engines
    on the same code pairs.

    Args:
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        alternative: Alternative hypothesis ('two-sided', 'less', 'greater').
        alpha: Significance level (default 0.05).

    Returns:
        WilcoxonResult with test statistics and p-value.

    Raises:
        ValueError: If input arrays have different lengths or are too small.
    """
    scores_a = np.asarray(scores_a)
    scores_b = np.asarray(scores_b)

    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"Input arrays must have same length: "
            f"scores_a={len(scores_a)}, scores_b={len(scores_b)}"
        )

    if len(scores_a) < 6:
        raise ValueError(
            f"Wilcoxon test requires at least 6 pairs, got {len(scores_a)}"
        )

    # Compute differences
    differences = scores_a - scores_b

    # Remove ties (zero differences)
    non_zero_mask = differences != 0
    n_pairs = np.sum(non_zero_mask)

    if n_pairs < 6:
        # Too few non-tied pairs for reliable test
        return WilcoxonResult(
            statistic=0.0,
            p_value=1.0,
            significant=False,
            n_pairs=int(n_pairs),
            mean_diff=float(np.mean(differences)),
            std_diff=float(np.std(differences)),
            method="insufficient_data",
        )

    # Perform Wilcoxon signed-rank test
    try:
        statistic, p_value = stats.wilcoxon(
            scores_a[non_zero_mask],
            scores_b[non_zero_mask],
            alternative=alternative,
        )
        method = "exact" if n_pairs <= 20 else "approximate"
    except ValueError:
        # Fallback to approximate method
        statistic, p_value = stats.wilcoxon(
            scores_a[non_zero_mask],
            scores_b[non_zero_mask],
            alternative=alternative,
        )
        method = "approximate"

    return WilcoxonResult(
        statistic=float(statistic),
        p_value=float(p_value),
        significant=p_value < alpha,
        n_pairs=int(n_pairs),
        mean_diff=float(np.mean(differences)),
        std_diff=float(np.std(differences)),
        method=method,
    )


def paired_bootstrap_test(
    y_true: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Paired bootstrap test for comparing two classifiers.

    Tests whether classifier A is significantly different from classifier B
    using the paired bootstrap test (Dietterich, 1998).

    Args:
        y_true: Ground truth labels.
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        metric_fn: Metric function that takes (y_true, scores) and returns float.
        n_bootstrap: Number of bootstrap samples.
        seed: Random seed for reproducibility.

    Returns:
        Dictionary with test results:
        - p_value: Two-tailed p-value.
        - significant: Whether difference is significant at alpha=0.05.
        - mean_diff: Mean difference in performance.
        - ci_lower: Lower bound of difference confidence interval.
        - ci_upper: Upper bound of difference confidence interval.
        - score_a: Score of classifier A.
        - score_b: Score of classifier B.
    """
    rng = np.random.RandomState(seed)
    n_samples = len(y_true)

    # Compute observed difference
    score_a = metric_fn(y_true, scores_a)
    score_b = metric_fn(y_true, scores_b)
    observed_diff = score_a - score_b

    # Bootstrap differences
    diff_count = 0
    bootstrap_diffs = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        indices = rng.randint(0, n_samples, size=n_samples)

        y_true_boot = y_true[indices]
        scores_a_boot = scores_a[indices]
        scores_b_boot = scores_b[indices]

        score_a_boot = metric_fn(y_true_boot, scores_a_boot)
        score_b_boot = metric_fn(y_true_boot, scores_b_boot)

        diff = score_a_boot - score_b_boot
        bootstrap_diffs[i] = diff

        # Count how often we see a difference as extreme as observed
        if abs(diff) >= abs(observed_diff):
            diff_count += 1

    # Two-tailed p-value
    p_value = diff_count / n_bootstrap

    # Confidence interval for the difference
    ci_lower = np.percentile(bootstrap_diffs, 2.5)
    ci_upper = np.percentile(bootstrap_diffs, 97.5)

    return {
        "p_value": float(p_value),
        "significant": p_value < 0.05,
        "mean_diff": float(observed_diff),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "n_bootstrap": n_bootstrap,
        "score_a": float(score_a),
        "score_b": float(score_b),
    }


def paired_statistical_tests(
    y_true: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    decisions_a: np.ndarray,
    decisions_b: np.ndarray,
    metric_fn: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> PairedTestResults:
    """Perform comprehensive paired statistical tests.

    Runs McNemar's test (for decisions), Wilcoxon test (for scores), and
    paired bootstrap test (for metric differences).

    Args:
        y_true: Ground truth labels.
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        decisions_a: Binary decisions from classifier A.
        decisions_b: Binary decisions from classifier B.
        metric_fn: Optional metric function for bootstrap test.
        n_bootstrap: Number of bootstrap samples.
        alpha: Significance level.
        seed: Random seed.

    Returns:
        PairedTestResults with all test results.
    """
    # McNemar's test for classification decisions
    mcnemar_result = mcnemar_test(y_true, decisions_a, decisions_b, alpha=alpha)

    # Wilcoxon signed-rank test for score distributions
    wilcoxon_result = wilcoxon_signed_rank_test(scores_a, scores_b, alpha=alpha)

    # Paired bootstrap test (if metric function provided)
    if metric_fn is not None:
        bootstrap_result = paired_bootstrap_test(
            y_true, scores_a, scores_b, metric_fn,
            n_bootstrap=n_bootstrap, seed=seed,
        )
        bootstrap_pvalue = bootstrap_result["p_value"]
        bootstrap_significant = bootstrap_result["significant"]
        mean_diff = bootstrap_result["mean_diff"]
        ci_diff = (bootstrap_result["ci_lower"], bootstrap_result["ci_upper"])
    else:
        bootstrap_pvalue = 1.0
        bootstrap_significant = False
        mean_diff = float(np.mean(scores_a - scores_b))
        ci_diff = (0.0, 0.0)

    return PairedTestResults(
        mcnemar=mcnemar_result,
        wilcoxon=wilcoxon_result,
        bootstrap_pvalue=bootstrap_pvalue,
        bootstrap_significant=bootstrap_significant,
        mean_diff=mean_diff,
        ci_diff=ci_diff,
    )


def bonferroni_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> Tuple[List[float], float]:
    """Apply Bonferroni correction for multiple comparisons.

    The Bonferroni correction is a simple, conservative method for controlling
    the family-wise error rate when performing multiple statistical tests.

    Args:
        p_values: List of p-values from multiple tests.
        alpha: Original significance level (default 0.05).

    Returns:
        Tuple of (adjusted_p_values, corrected_alpha).
    """
    n_tests = len(p_values)
    corrected_alpha = alpha / n_tests if n_tests > 0 else alpha

    # Adjust p-values (cap at 1.0)
    adjusted_p_values = [min(p * n_tests, 1.0) for p in p_values]

    return adjusted_p_values, corrected_alpha


def compare_multiple_engines(
    y_true: np.ndarray,
    engine_scores: Dict[str, np.ndarray],
    engine_decisions: Dict[str, np.ndarray],
    metric_fn: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
    baseline_engine: Optional[str] = None,
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Dict[str, Dict[str, Any]]:
    """Compare multiple engines with multiple comparison correction.

    Performs pairwise comparisons between all engines and applies Bonferroni
    correction for multiple comparisons.

    Args:
        y_true: Ground truth labels.
        engine_scores: Dictionary mapping engine names to score arrays.
        engine_decisions: Dictionary mapping engine names to decision arrays.
        metric_fn: Optional metric function for bootstrap test.
        baseline_engine: Optional baseline engine for comparisons.
        n_bootstrap: Number of bootstrap samples.
        alpha: Original significance level.
        seed: Random seed.

    Returns:
        Dictionary mapping comparison names to test results.
    """
    engines = list(engine_scores.keys())
    n_engines = len(engines)

    # Compute all pairwise comparisons
    comparisons = []
    comparison_results = {}

    for i in range(n_engines):
        for j in range(i + 1, n_engines):
            engine_a = engines[i]
            engine_b = engines[j]
            comparison_name = f"{engine_a}_vs_{engine_b}"

            results = paired_statistical_tests(
                y_true,
                engine_scores[engine_a],
                engine_scores[engine_b],
                engine_decisions[engine_a],
                engine_decisions[engine_b],
                metric_fn=metric_fn,
                n_bootstrap=n_bootstrap,
                alpha=alpha,
                seed=seed,
            )

            comparisons.append((comparison_name, results))
            comparison_results[comparison_name] = results

    # Apply Bonferroni correction
    n_comparisons = len(comparisons)
    corrected_alpha = alpha / n_comparisons if n_comparisons > 0 else alpha

    # Update significance with corrected alpha
    for comparison_name, results in comparison_results.items():
        # Create updated McNemar result with corrected alpha
        mcnemar = results.mcnemar
        updated_mcnemar = McNemarResult(
            statistic=mcnemar.statistic,
            p_value=mcnemar.p_value,
            significant=mcnemar.p_value < corrected_alpha,
            contingency_table=mcnemar.contingency_table,
            b=mcnemar.b,
            c=mcnemar.c,
            method=mcnemar.method,
            corrected_alpha=corrected_alpha,
        )

        # Create updated results
        comparison_results[comparison_name] = PairedTestResults(
            mcnemar=updated_mcnemar,
            wilcoxon=results.wilcoxon,
            bootstrap_pvalue=results.bootstrap_pvalue,
            bootstrap_significant=results.bootstrap_pvalue < corrected_alpha,
            mean_diff=results.mean_diff,
            ci_diff=results.ci_diff,
        )

    return comparison_results