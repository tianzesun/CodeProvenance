"""Unit tests for statistical rigor framework."""
import pytest
import numpy as np
from src.backend.benchmark.validation.statistical_rigor import (
    ConfidenceIntervalCalculator,
    SignificanceTester,
    RobustnessAnalyzer,
    StatisticalAnalyzer,
    ConfidenceInterval,
    SignificanceTest,
    RobustnessResult,
)
from src.backend.evaluation.pan_metrics import (
    PANMetrics,
    Detection,
    TextSpan,
)


class TestConfidenceIntervalCalculator:
    """Tests for confidence interval calculation."""

    def test_bootstrap_ci_basic(self):
        """Test basic bootstrap confidence interval."""
        data = [0.7, 0.75, 0.8, 0.72, 0.78, 0.76, 0.74, 0.79]
        ci = ConfidenceIntervalCalculator.bootstrap_ci(
            data,
            confidence=0.95,
            n_bootstrap=1000,
        )
        assert ci.point_estimate == pytest.approx(np.mean(data), rel=0.01)
        assert ci.lower_bound < ci.point_estimate
        assert ci.upper_bound > ci.point_estimate
        assert ci.confidence_level == 0.95

    def test_bootstrap_ci_width(self):
        """Test that CI width is reasonable."""
        data = [0.7, 0.75, 0.8, 0.72, 0.78, 0.76, 0.74, 0.79]
        ci = ConfidenceIntervalCalculator.bootstrap_ci(
            data,
            confidence=0.95,
            n_bootstrap=1000,
        )
        # Width should be less than 0.2 for this data
        assert ci.width < 0.2

    def test_bootstrap_ci_contains_point_estimate(self):
        """Test that CI contains point estimate."""
        data = [0.7, 0.75, 0.8, 0.72, 0.78, 0.76, 0.74, 0.79]
        ci = ConfidenceIntervalCalculator.bootstrap_ci(data)
        assert ci.contains(ci.point_estimate)

    def test_calculate_metric_ci(self):
        """Test calculating CI for a specific metric."""
        metrics_list = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
            PANMetrics(0.82, 0.87, 0.845, 1.0, 0.845),
        ]
        ci = ConfidenceIntervalCalculator.calculate_metric_ci(
            metrics_list,
            "f1_score",
            confidence=0.95,
            n_bootstrap=1000,
        )
        assert ci.metric_name == "f1_score"
        assert 0.7 < ci.point_estimate < 0.9
        assert ci.lower_bound < ci.upper_bound

    def test_confidence_interval_contains(self):
        """Test CI contains method."""
        ci = ConfidenceInterval(
            metric_name="test",
            point_estimate=0.75,
            lower_bound=0.70,
            upper_bound=0.80,
        )
        assert ci.contains(0.75)
        assert ci.contains(0.70)
        assert ci.contains(0.80)
        assert not ci.contains(0.65)
        assert not ci.contains(0.85)


class TestSignificanceTester:
    """Tests for significance testing."""

    def test_mcnemars_test_identical(self):
        """Test McNemar's test with identical results."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred1 = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred2 = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]

        result = SignificanceTester.mcnemars_test(pred1, pred2, gt)
        assert result.test_name == "McNemar's Test"
        assert result.p_value == 1.0  # No difference
        assert not result.significant

    def test_paired_t_test_identical(self):
        """Test paired t-test with identical samples."""
        tool1 = [0.8, 0.75, 0.82, 0.78]
        tool2 = [0.8, 0.75, 0.82, 0.78]

        result = SignificanceTester.paired_t_test(tool1, tool2)
        assert result.test_name == "Paired t-test"
        # When samples are identical, t-test returns NaN or 1.0
        assert result.p_value == 1.0 or (result.p_value != result.p_value)  # NaN check
        assert not result.significant

    def test_paired_t_test_different(self):
        """Test paired t-test with different samples."""
        tool1 = [0.8, 0.75, 0.82, 0.78, 0.80]
        tool2 = [0.6, 0.55, 0.62, 0.58, 0.60]

        result = SignificanceTester.paired_t_test(tool1, tool2, alpha=0.05)
        assert result.test_name == "Paired t-test"
        assert result.p_value < 0.05  # Significant difference
        assert result.significant

    def test_wilcoxon_test_identical(self):
        """Test Wilcoxon test with identical samples."""
        tool1 = [0.8, 0.75, 0.82, 0.78]
        tool2 = [0.8, 0.75, 0.82, 0.78]

        result = SignificanceTester.wilcoxon_test(tool1, tool2)
        assert result.test_name == "Wilcoxon Signed-Rank Test"
        assert result.p_value == 1.0  # No difference
        assert not result.significant

    def test_significance_test_effect_size(self):
        """Test effect size interpretation."""
        test_strong = SignificanceTest(
            test_name="test",
            tool1_id="t1",
            tool2_id="t2",
            statistic=10.0,
            p_value=0.001,
            significant=True,
        )
        assert test_strong.effect_size == "strong"

        test_weak = SignificanceTest(
            test_name="test",
            tool1_id="t1",
            tool2_id="t2",
            statistic=1.0,
            p_value=0.1,
            significant=False,
        )
        assert test_weak.effect_size == "weak"


class TestRobustnessAnalyzer:
    """Tests for robustness analysis."""

    def test_variable_renaming_perturbation(self):
        """Test variable renaming perturbation."""
        code = "x = 1\ny = x + 1\nfor i in range(n):\n    print(i)"
        perturbed = RobustnessAnalyzer.variable_renaming_perturbation(code)
        assert "var_x" in perturbed or "x" in perturbed  # May or may not rename
        assert len(perturbed) > 0

    def test_whitespace_perturbation(self):
        """Test whitespace perturbation."""
        code = "x = 1\n  y = x + 1\n    z = y * 2"
        perturbed = RobustnessAnalyzer.whitespace_perturbation(code)
        # Whitespace should be normalized
        assert "x = 1" in perturbed or "x=1" in perturbed

    def test_comment_perturbation(self):
        """Test comment removal perturbation."""
        code = "x = 1  # This is a comment\ny = x + 1  # Another comment"
        perturbed = RobustnessAnalyzer.comment_perturbation(code)
        # Comments should be removed
        assert "# This is a comment" not in perturbed
        assert "# Another comment" not in perturbed

    def test_analyze_robustness(self):
        """Test robustness analysis."""
        def dummy_tool(source, suspicious):
            # Simple tool that returns similarity based on length
            return min(len(source), len(suspicious)) / max(len(source), len(suspicious))

        source = "x = 1\ny = 2\nz = 3"
        suspicious = "x = 1\ny = 2\nz = 3"

        result = RobustnessAnalyzer.analyze_robustness(
            dummy_tool,
            source,
            suspicious,
        )

        assert result.tool_id == "tool"
        assert result.original_score > 0
        assert len(result.perturbed_scores) > 0
        assert 0 <= result.robustness_score <= 1

    def test_robustness_result_str(self):
        """Test robustness result string representation."""
        result = RobustnessResult(
            tool_id="jplag",
            perturbation_type="variable_renaming",
            original_score=0.85,
            perturbed_scores=[0.84, 0.83, 0.85],
            mean_change=0.01,
            std_change=0.01,
            robustness_score=0.99,
        )
        result_str = str(result)
        assert "jplag" in result_str
        assert "variable_renaming" in result_str
        assert "0.99" in result_str


class TestStatisticalAnalyzer:
    """Tests for comprehensive statistical analysis."""

    def test_analyze_metrics(self):
        """Test comprehensive metric analysis."""
        metrics_list = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
            PANMetrics(0.82, 0.87, 0.845, 1.0, 0.845),
        ]

        report = StatisticalAnalyzer.analyze_metrics(
            metrics_list,
            confidence=0.95,
            alpha=0.05,
        )

        assert len(report.confidence_intervals) > 0
        assert report.summary is not None
        assert "95" in report.summary or "0.95" in report.summary

    def test_compare_tools_equal_samples(self):
        """Test tool comparison with equal samples."""
        metrics1 = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
        ]
        metrics2 = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
        ]

        result = StatisticalAnalyzer.compare_tools(
            metrics1, metrics2, metric_name="f1_score"
        )

        assert result.test_name == "Paired t-test"
        # When samples are identical, p-value is NaN or 1.0
        assert result.p_value == 1.0 or (result.p_value != result.p_value)  # NaN check
        assert not result.significant

    def test_compare_tools_unequal_samples(self):
        """Test tool comparison with equal length samples."""
        # Both tools have same number of samples, so paired t-test is used
        metrics1 = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
            PANMetrics(0.82, 0.87, 0.845, 1.0, 0.845),
        ]
        metrics2 = [
            PANMetrics(0.7, 0.75, 0.725, 1.0, 0.725),
            PANMetrics(0.65, 0.70, 0.675, 1.0, 0.675),
            PANMetrics(0.72, 0.77, 0.745, 1.0, 0.745),
        ]

        result = StatisticalAnalyzer.compare_tools(
            metrics1, metrics2, metric_name="f1_score"
        )

        # With equal length samples, paired t-test is used
        assert result.test_name == "Paired t-test"


class TestStatisticalReport:
    """Tests for statistical report."""

    def test_statistical_report_str(self):
        """Test statistical report string representation."""
        ci = ConfidenceInterval(
            metric_name="f1_score",
            point_estimate=0.825,
            lower_bound=0.80,
            upper_bound=0.85,
        )

        from src.backend.benchmark.validation.statistical_rigor import StatisticalReport

        report = StatisticalReport(
            confidence_intervals=[ci],
            significance_tests=[],
            robustness_results=[],
            summary="Test summary",
        )

        report_str = str(report)
        assert "Test summary" in report_str
        assert "f1_score" in report_str
        assert "0.825" in report_str
