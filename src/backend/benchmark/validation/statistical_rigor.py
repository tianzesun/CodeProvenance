"""Statistical rigor framework for benchmark results.

Implements confidence intervals, significance testing, and robustness analysis
to ensure benchmark results are statistically sound and trustworthy.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Callable
from scipy import stats
import math

from src.backend.evaluation.pan_metrics import (
    PANMetrics,
    Detection,
    calculate_pan_metrics,
)


@dataclass
class ConfidenceInterval:
    """Confidence interval for a metric."""
    metric_name: str
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95
    method: str = "bootstrap"

    @property
    def width(self) -> float:
        """Width of the confidence interval."""
        return self.upper_bound - self.lower_bound

    def contains(self, value: float) -> bool:
        """Check if value is within the interval."""
        return self.lower_bound <= value <= self.upper_bound

    def __str__(self) -> str:
        return (
            f"{self.metric_name}: {self.point_estimate:.4f} "
            f"[{self.lower_bound:.4f}, {self.upper_bound:.4f}]"
        )


@dataclass
class SignificanceTest:
    """Result of a significance test."""
    test_name: str
    tool1_id: str
    tool2_id: str
    statistic: float
    p_value: float
    significant: bool
    alpha: float = 0.05

    @property
    def effect_size(self) -> str:
        """Interpret effect size based on p-value."""
        if self.p_value < 0.001:
            return "very strong"
        elif self.p_value < 0.01:
            return "strong"
        elif self.p_value < 0.05:
            return "moderate"
        else:
            return "weak"

    def __str__(self) -> str:
        sig_str = "significant" if self.significant else "not significant"
        return (
            f"{self.test_name}: {self.tool1_id} vs {self.tool2_id} "
            f"(p={self.p_value:.4f}, {sig_str})"
        )


@dataclass
class RobustnessResult:
    """Result of robustness analysis."""
    tool_id: str
    perturbation_type: str
    original_score: float
    perturbed_scores: List[float]
    mean_change: float
    std_change: float
    robustness_score: float  # 0-1, higher is more robust

    def __str__(self) -> str:
        return (
            f"{self.tool_id} ({self.perturbation_type}): "
            f"robustness={self.robustness_score:.3f}, "
            f"mean_change={self.mean_change:.4f}±{self.std_change:.4f}"
        )


@dataclass
class StatisticalReport:
    """Complete statistical analysis report."""
    confidence_intervals: List[ConfidenceInterval]
    significance_tests: List[SignificanceTest]
    robustness_results: List[RobustnessResult]
    summary: str

    def __str__(self) -> str:
        lines = [self.summary, ""]
        lines.append("Confidence Intervals:")
        for ci in self.confidence_intervals:
            lines.append(f"  {ci}")
        lines.append("\nSignificance Tests:")
        for test in self.significance_tests:
            lines.append(f"  {test}")
        lines.append("\nRobustness Analysis:")
        for result in self.robustness_results:
            lines.append(f"  {result}")
        return "\n".join(lines)


class ConfidenceIntervalCalculator:
    """Calculates confidence intervals using bootstrap method."""

    @staticmethod
    def bootstrap_ci(
        data: List[float],
        statistic_func: Callable[[List[float]], float] = np.mean,
        confidence: float = 0.95,
        n_bootstrap: int = 10000,
        random_seed: int = 42,
    ) -> ConfidenceInterval:
        """Calculate bootstrap confidence interval.

        Args:
            data: Data to analyze
            statistic_func: Function to calculate statistic
            confidence: Confidence level (0-1)
            n_bootstrap: Number of bootstrap samples
            random_seed: Random seed for reproducibility

        Returns:
            ConfidenceInterval object
        """
        np.random.seed(random_seed)
        n = len(data)
        bootstrap_stats = []

        for _ in range(n_bootstrap):
            # Resample with replacement
            sample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats.append(statistic_func(sample))

        # Calculate percentile-based CI
        alpha = 1 - confidence
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        lower_bound = np.percentile(bootstrap_stats, lower_percentile)
        upper_bound = np.percentile(bootstrap_stats, upper_percentile)
        point_estimate = statistic_func(data)

        return ConfidenceInterval(
            metric_name="bootstrap_statistic",
            point_estimate=point_estimate,
            lower_bound=float(lower_bound),
            upper_bound=float(upper_bound),
            confidence_level=confidence,
            method="bootstrap",
        )

    @staticmethod
    def calculate_metric_ci(
        metrics_list: List[PANMetrics],
        metric_name: str,
        confidence: float = 0.95,
        n_bootstrap: int = 10000,
    ) -> ConfidenceInterval:
        """Calculate confidence interval for a specific metric.

        Args:
            metrics_list: List of PANMetrics objects
            metric_name: Name of metric (precision, recall, f1_score, etc.)
            confidence: Confidence level
            n_bootstrap: Number of bootstrap samples

        Returns:
            ConfidenceInterval for the metric
        """
        # Extract metric values
        data = []
        for metrics in metrics_list:
            value = getattr(metrics, metric_name, None)
            if value is not None:
                data.append(value)

        if not data:
            raise ValueError(f"No data found for metric: {metric_name}")

        ci = ConfidenceIntervalCalculator.bootstrap_ci(
            data,
            statistic_func=np.mean,
            confidence=confidence,
            n_bootstrap=n_bootstrap,
        )
        ci.metric_name = metric_name
        return ci


class SignificanceTester:
    """Performs statistical significance tests."""

    @staticmethod
    def mcnemars_test(
        tool1_predictions: List[Detection],
        tool2_predictions: List[Detection],
        ground_truth: List[Detection],
        alpha: float = 0.05,
    ) -> SignificanceTest:
        """Perform McNemar's test for paired tool comparison.

        McNemar's test compares two tools on the same dataset.
        Tests whether the tools have significantly different error rates.

        Args:
            tool1_predictions: Predictions from tool 1
            tool2_predictions: Predictions from tool 2
            ground_truth: Ground truth detections
            alpha: Significance level

        Returns:
            SignificanceTest result
        """
        # Calculate metrics for each tool
        metrics1 = calculate_pan_metrics(ground_truth, tool1_predictions)
        metrics2 = calculate_pan_metrics(ground_truth, tool2_predictions)

        # For McNemar's test, we need binary outcomes (correct/incorrect)
        # Use F1 score as proxy: correct if F1 > 0.5, incorrect otherwise
        tool1_correct = 1 if metrics1.f1_score > 0.5 else 0
        tool2_correct = 1 if metrics2.f1_score > 0.5 else 0

        # McNemar's test contingency table
        # b = tool1 correct, tool2 incorrect
        # c = tool1 incorrect, tool2 correct
        b = 1 if (tool1_correct == 1 and tool2_correct == 0) else 0
        c = 1 if (tool1_correct == 0 and tool2_correct == 1) else 0

        # McNemar's statistic: (b - c)^2 / (b + c)
        if b + c == 0:
            statistic = 0.0
            p_value = 1.0
        else:
            statistic = (b - c) ** 2 / (b + c)
            # Chi-square distribution with 1 degree of freedom
            p_value = 1 - stats.chi2.cdf(statistic, df=1)

        significant = p_value < alpha

        return SignificanceTest(
            test_name="McNemar's Test",
            tool1_id="tool1",
            tool2_id="tool2",
            statistic=statistic,
            p_value=p_value,
            significant=significant,
            alpha=alpha,
        )

    @staticmethod
    def paired_t_test(
        tool1_metrics: List[float],
        tool2_metrics: List[float],
        alpha: float = 0.05,
    ) -> SignificanceTest:
        """Perform paired t-test for tool comparison.

        Args:
            tool1_metrics: Metric values from tool 1
            tool2_metrics: Metric values from tool 2
            alpha: Significance level

        Returns:
            SignificanceTest result
        """
        if len(tool1_metrics) != len(tool2_metrics):
            raise ValueError("Metrics must have same length")

        # Paired t-test
        t_statistic, p_value = stats.ttest_rel(tool1_metrics, tool2_metrics)

        significant = p_value < alpha

        return SignificanceTest(
            test_name="Paired t-test",
            tool1_id="tool1",
            tool2_id="tool2",
            statistic=float(t_statistic),
            p_value=float(p_value),
            significant=significant,
            alpha=alpha,
        )

    @staticmethod
    def wilcoxon_test(
        tool1_metrics: List[float],
        tool2_metrics: List[float],
        alpha: float = 0.05,
    ) -> SignificanceTest:
        """Perform Wilcoxon signed-rank test (non-parametric).

        Args:
            tool1_metrics: Metric values from tool 1
            tool2_metrics: Metric values from tool 2
            alpha: Significance level

        Returns:
            SignificanceTest result
        """
        if len(tool1_metrics) != len(tool2_metrics):
            raise ValueError("Metrics must have same length")

        # Check if all differences are zero
        differences = [t1 - t2 for t1, t2 in zip(tool1_metrics, tool2_metrics)]
        if all(d == 0 for d in differences):
            # No difference, return p-value of 1.0
            return SignificanceTest(
                test_name="Wilcoxon Signed-Rank Test",
                tool1_id="tool1",
                tool2_id="tool2",
                statistic=0.0,
                p_value=1.0,
                significant=False,
                alpha=alpha,
            )

        # Wilcoxon signed-rank test
        statistic, p_value = stats.wilcoxon(tool1_metrics, tool2_metrics)

        significant = p_value < alpha

        return SignificanceTest(
            test_name="Wilcoxon Signed-Rank Test",
            tool1_id="tool1",
            tool2_id="tool2",
            statistic=float(statistic),
            p_value=float(p_value),
            significant=significant,
            alpha=alpha,
        )


class RobustnessAnalyzer:
    """Analyzes tool robustness under code perturbations."""

    @staticmethod
    def variable_renaming_perturbation(code: str) -> str:
        """Perturb code by renaming variables.

        Simple perturbation: replace common variable names.
        """
        import re
        perturbed = code
        # Replace common variable names
        replacements = {
            r'\bx\b': 'var_x',
            r'\by\b': 'var_y',
            r'\bi\b': 'idx',
            r'\bj\b': 'jdx',
            r'\bn\b': 'num',
        }
        for pattern, replacement in replacements.items():
            perturbed = re.sub(pattern, replacement, perturbed)
        return perturbed

    @staticmethod
    def whitespace_perturbation(code: str) -> str:
        """Perturb code by changing whitespace."""
        # Add/remove whitespace
        lines = code.split('\n')
        perturbed_lines = []
        for line in lines:
            # Normalize whitespace
            perturbed_lines.append(line.strip())
        return '\n'.join(perturbed_lines)

    @staticmethod
    def comment_perturbation(code: str) -> str:
        """Perturb code by removing comments."""
        import re
        # Remove single-line comments
        perturbed = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments (Python docstrings)
        perturbed = re.sub(r'""".*?"""', '', perturbed, flags=re.DOTALL)
        perturbed = re.sub(r"'''.*?'''", '', perturbed, flags=re.DOTALL)
        return perturbed

    @staticmethod
    def analyze_robustness(
        tool_func: Callable[[str, str], float],
        source_code: str,
        suspicious_code: str,
        perturbations: List[Tuple[str, Callable[[str], str]]] | None = None,
    ) -> RobustnessResult:
        """Analyze tool robustness under code perturbations.

        Args:
            tool_func: Function that takes (source, suspicious) and returns score
            source_code: Source code
            suspicious_code: Suspicious code
            perturbations: List of (name, perturbation_func) tuples

        Returns:
            RobustnessResult
        """
        if perturbations is None:
            perturbations = [
                ("variable_renaming", RobustnessAnalyzer.variable_renaming_perturbation),
                ("whitespace", RobustnessAnalyzer.whitespace_perturbation),
                ("comments", RobustnessAnalyzer.comment_perturbation),
            ]

        # Original score
        original_score = tool_func(source_code, suspicious_code)

        # Perturbed scores
        perturbed_scores = []
        for name, perturb_func in perturbations:
            perturbed_suspicious = perturb_func(suspicious_code)
            perturbed_score = tool_func(source_code, perturbed_suspicious)
            perturbed_scores.append(perturbed_score)

        # Calculate robustness metrics
        score_changes = [abs(original_score - ps) for ps in perturbed_scores]
        mean_change = float(np.mean(score_changes))
        std_change = float(np.std(score_changes))

        # Robustness score: 1 - (mean_change / max_possible_change)
        # Assuming max change is 1.0 (from 0 to 1)
        robustness_score = max(0.0, 1.0 - mean_change)

        return RobustnessResult(
            tool_id="tool",
            perturbation_type="combined",
            original_score=original_score,
            perturbed_scores=perturbed_scores,
            mean_change=mean_change,
            std_change=std_change,
            robustness_score=robustness_score,
        )


class StatisticalAnalyzer:
    """Comprehensive statistical analysis framework."""

    @staticmethod
    def analyze_metrics(
        metrics_list: List[PANMetrics],
        confidence: float = 0.95,
        alpha: float = 0.05,
    ) -> StatisticalReport:
        """Perform comprehensive statistical analysis of metrics.

        Args:
            metrics_list: List of PANMetrics objects
            confidence: Confidence level for intervals
            alpha: Significance level for tests

        Returns:
            StatisticalReport with all analyses
        """
        # Calculate confidence intervals for each metric
        metric_names = ["precision", "recall", "f1_score", "granularity", "plagdet"]
        confidence_intervals = []

        for metric_name in metric_names:
            try:
                ci = ConfidenceIntervalCalculator.calculate_metric_ci(
                    metrics_list,
                    metric_name,
                    confidence=confidence,
                )
                confidence_intervals.append(ci)
            except ValueError:
                pass

        # Placeholder for significance tests (would need multiple tool results)
        significance_tests = []

        # Placeholder for robustness results
        robustness_results = []

        # Generate summary
        summary = (
            f"Statistical Analysis: {len(metrics_list)} samples\n"
            f"Confidence level: {confidence*100:.0f}%\n"
            f"Significance level: {alpha*100:.0f}%"
        )

        return StatisticalReport(
            confidence_intervals=confidence_intervals,
            significance_tests=significance_tests,
            robustness_results=robustness_results,
            summary=summary,
        )

    @staticmethod
    def compare_tools(
        tool1_metrics: List[PANMetrics],
        tool2_metrics: List[PANMetrics],
        metric_name: str = "f1_score",
        alpha: float = 0.05,
    ) -> SignificanceTest:
        """Compare two tools using statistical tests.

        Args:
            tool1_metrics: Metrics from tool 1
            tool2_metrics: Metrics from tool 2
            metric_name: Metric to compare
            alpha: Significance level

        Returns:
            SignificanceTest result
        """
        # Extract metric values
        tool1_values = [getattr(m, metric_name) for m in tool1_metrics]
        tool2_values = [getattr(m, metric_name) for m in tool2_metrics]

        # Use paired t-test if same number of samples
        if len(tool1_values) == len(tool2_values):
            return SignificanceTester.paired_t_test(
                tool1_values, tool2_values, alpha=alpha
            )
        else:
            # Use Wilcoxon test for unequal samples
            return SignificanceTester.wilcoxon_test(
                tool1_values, tool2_values, alpha=alpha
            )
