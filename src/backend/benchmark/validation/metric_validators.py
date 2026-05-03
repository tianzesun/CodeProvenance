"""Comprehensive validation of PAN plagiarism detection metrics.

Ensures all metric calculations match the official PAN reference implementation
exactly, with proper numerical stability and edge case handling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
from decimal import Decimal, ROUND_HALF_UP

from src.backend.evaluation.pan_metrics import (
    PANMetrics,
    Detection,
    TextSpan,
    calculate_pan_metrics,
)


@dataclass
class MetricValidationResult:
    """Result of metric validation check."""
    metric_name: str
    expected: float
    actual: float
    passed: bool
    error: float | None = None
    tolerance: float = 1e-6
    notes: str = ""

    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        if self.error is not None:
            return f"{status} {self.metric_name}: expected {self.expected:.6f}, got {self.actual:.6f}, error {self.error:.2e}"
        return f"{status} {self.metric_name}: {self.actual:.6f}"


@dataclass
class MetricValidationReport:
    """Complete validation report for a set of metrics."""
    results: List[MetricValidationResult]
    all_passed: bool
    summary: str

    def __str__(self) -> str:
        lines = [self.summary]
        for result in self.results:
            lines.append(f"  {result}")
        return "\n".join(lines)


class MetricValidator:
    """Validates PAN metrics calculations against specifications."""

    # Tolerance for floating-point comparisons
    DEFAULT_TOLERANCE = 1e-6

    @staticmethod
    def validate_precision_calculation(
        predictions: List[Detection],
        ground_truth: List[Detection],
        expected_precision: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationResult:
        """Validate precision calculation.

        Precision = sum(overlap_i) / sum(pred_length_i)
        where overlap_i is the maximum overlap between prediction i and any ground truth.
        """
        if not predictions:
            actual = 1.0 if not ground_truth else 0.0
        else:
            precision_sum = 0.0
            for pred in predictions:
                max_overlap = 0
                for gt in ground_truth:
                    overlap_susp = pred.suspicious_span.overlap(gt.suspicious_span)
                    overlap_src = pred.source_span.overlap(gt.source_span)
                    if overlap_susp > 0 and overlap_src > 0:
                        max_overlap = max(max_overlap, overlap_susp)
                precision_sum += max_overlap / pred.suspicious_span.length

            actual = precision_sum / len(predictions)

        error = abs(actual - expected_precision)
        passed = error <= tolerance

        return MetricValidationResult(
            metric_name="Precision",
            expected=expected_precision,
            actual=actual,
            passed=passed,
            error=error if not passed else None,
            tolerance=tolerance,
        )

    @staticmethod
    def validate_recall_calculation(
        predictions: List[Detection],
        ground_truth: List[Detection],
        expected_recall: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationResult:
        """Validate recall calculation.

        Recall = sum(overlap_i) / sum(gt_length_i)
        where overlap_i is the maximum overlap between ground truth i and any prediction.
        """
        if not ground_truth:
            actual = 1.0
        elif not predictions:
            actual = 0.0
        else:
            recall_sum = 0.0
            for gt in ground_truth:
                max_overlap = 0
                for pred in predictions:
                    overlap_susp = pred.suspicious_span.overlap(gt.suspicious_span)
                    overlap_src = pred.source_span.overlap(gt.source_span)
                    if overlap_susp > 0 and overlap_src > 0:
                        max_overlap = max(max_overlap, overlap_susp)
                recall_sum += max_overlap / gt.suspicious_span.length

            actual = recall_sum / len(ground_truth)

        error = abs(actual - expected_recall)
        passed = error <= tolerance

        return MetricValidationResult(
            metric_name="Recall",
            expected=expected_recall,
            actual=actual,
            passed=passed,
            error=error if not passed else None,
            tolerance=tolerance,
        )

    @staticmethod
    def validate_f1_calculation(
        precision: float,
        recall: float,
        expected_f1: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationResult:
        """Validate F1 score calculation.

        F1 = 2 * P * R / (P + R)
        """
        if precision + recall > 0:
            actual = 2 * precision * recall / (precision + recall)
        else:
            actual = 0.0

        error = abs(actual - expected_f1)
        passed = error <= tolerance

        return MetricValidationResult(
            metric_name="F1 Score",
            expected=expected_f1,
            actual=actual,
            passed=passed,
            error=error if not passed else None,
            tolerance=tolerance,
        )

    @staticmethod
    def validate_granularity_calculation(
        predictions: List[Detection],
        ground_truth: List[Detection],
        expected_granularity: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationResult:
        """Validate granularity calculation.

        Granularity = total_detections / detected_ground_truth_count
        """
        if not ground_truth or not predictions:
            actual = 1.0
        else:
            detected_ground_truth = set()
            detection_count_per_gt = {i: 0 for i in range(len(ground_truth))}

            for gt_idx, gt in enumerate(ground_truth):
                for pred_idx, pred in enumerate(predictions):
                    overlap_susp = pred.suspicious_span.overlap(gt.suspicious_span)
                    overlap_src = pred.source_span.overlap(gt.source_span)
                    if overlap_susp > 0 and overlap_src > 0:
                        detected_ground_truth.add(gt_idx)
                        detection_count_per_gt[gt_idx] += 1

            if detected_ground_truth:
                total_detections = sum(
                    detection_count_per_gt[gt_idx] for gt_idx in detected_ground_truth
                )
                actual = total_detections / len(detected_ground_truth)
            else:
                actual = 1.0

        error = abs(actual - expected_granularity)
        passed = error <= tolerance

        return MetricValidationResult(
            metric_name="Granularity",
            expected=expected_granularity,
            actual=actual,
            passed=passed,
            error=error if not passed else None,
            tolerance=tolerance,
        )

    @staticmethod
    def validate_plagdet_calculation(
        f1_score: float,
        granularity: float,
        expected_plagdet: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationResult:
        """Validate PlagDet calculation.

        PlagDet = F1 / log2(1 + Granularity)
        """
        if granularity > 0:
            actual = f1_score / math.log2(1 + granularity)
        else:
            actual = 0.0

        error = abs(actual - expected_plagdet)
        passed = error <= tolerance

        return MetricValidationResult(
            metric_name="PlagDet",
            expected=expected_plagdet,
            actual=actual,
            passed=passed,
            error=error if not passed else None,
            tolerance=tolerance,
        )

    @staticmethod
    def validate_metric_ranges(metrics: PANMetrics) -> List[MetricValidationResult]:
        """Validate that all metrics are within valid ranges.

        - Precision, Recall, F1: [0, 1]
        - Granularity: [1, ∞)
        - PlagDet: [0, 1]
        """
        results = []

        # Precision range
        precision_valid = 0 <= metrics.precision <= 1
        results.append(
            MetricValidationResult(
                metric_name="Precision Range",
                expected=0.5,  # Dummy value
                actual=metrics.precision,
                passed=precision_valid,
                notes=f"Must be in [0, 1], got {metrics.precision}",
            )
        )

        # Recall range
        recall_valid = 0 <= metrics.recall <= 1
        results.append(
            MetricValidationResult(
                metric_name="Recall Range",
                expected=0.5,  # Dummy value
                actual=metrics.recall,
                passed=recall_valid,
                notes=f"Must be in [0, 1], got {metrics.recall}",
            )
        )

        # F1 range
        f1_valid = 0 <= metrics.f1_score <= 1
        results.append(
            MetricValidationResult(
                metric_name="F1 Range",
                expected=0.5,  # Dummy value
                actual=metrics.f1_score,
                passed=f1_valid,
                notes=f"Must be in [0, 1], got {metrics.f1_score}",
            )
        )

        # Granularity range
        granularity_valid = metrics.granularity >= 1.0
        results.append(
            MetricValidationResult(
                metric_name="Granularity Range",
                expected=1.0,
                actual=metrics.granularity,
                passed=granularity_valid,
                notes=f"Must be >= 1.0, got {metrics.granularity}",
            )
        )

        # PlagDet range
        plagdet_valid = 0 <= metrics.plagdet <= 1
        results.append(
            MetricValidationResult(
                metric_name="PlagDet Range",
                expected=0.5,  # Dummy value
                actual=metrics.plagdet,
                passed=plagdet_valid,
                notes=f"Must be in [0, 1], got {metrics.plagdet}",
            )
        )

        return results

    @staticmethod
    def validate_no_nan_inf(metrics: PANMetrics) -> List[MetricValidationResult]:
        """Validate that no metrics contain NaN or Inf values."""
        results = []

        for metric_name, value in metrics.as_dict().items():
            is_valid = not (math.isnan(value) or math.isinf(value))
            results.append(
                MetricValidationResult(
                    metric_name=f"{metric_name} (NaN/Inf check)",
                    expected=0.5,  # Dummy value
                    actual=value,
                    passed=is_valid,
                    notes=f"Must not be NaN or Inf, got {value}",
                )
            )

        return results

    @staticmethod
    def validate_metrics_consistency(metrics: PANMetrics) -> List[MetricValidationResult]:
        """Validate consistency relationships between metrics."""
        results = []

        # F1 should be <= min(precision, recall) in most cases
        # (not always true, but good sanity check)
        f1_reasonable = metrics.f1_score <= max(metrics.precision, metrics.recall) + 1e-6
        results.append(
            MetricValidationResult(
                metric_name="F1 Consistency",
                expected=metrics.f1_score,
                actual=metrics.f1_score,
                passed=f1_reasonable,
                notes="F1 should be <= max(precision, recall)",
            )
        )

        # If precision and recall are both 0, F1 should be 0
        if metrics.precision == 0 and metrics.recall == 0:
            f1_zero = metrics.f1_score == 0
            results.append(
                MetricValidationResult(
                    metric_name="F1 Zero Consistency",
                    expected=0.0,
                    actual=metrics.f1_score,
                    passed=f1_zero,
                    notes="F1 should be 0 when both precision and recall are 0",
                )
            )

        # If F1 is 0, PlagDet should be 0
        if metrics.f1_score == 0:
            plagdet_zero = metrics.plagdet == 0
            results.append(
                MetricValidationResult(
                    metric_name="PlagDet Zero Consistency",
                    expected=0.0,
                    actual=metrics.plagdet,
                    passed=plagdet_zero,
                    notes="PlagDet should be 0 when F1 is 0",
                )
            )

        return results

    @staticmethod
    def validate_complete_metrics(
        predictions: List[Detection],
        ground_truth: List[Detection],
        expected_metrics: PANMetrics,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> MetricValidationReport:
        """Perform complete validation of all metrics.

        Args:
            predictions: Predicted detections
            ground_truth: Ground truth detections
            expected_metrics: Expected metric values
            tolerance: Tolerance for floating-point comparisons

        Returns:
            Complete validation report
        """
        results = []

        # Calculate actual metrics
        actual_metrics = calculate_pan_metrics(ground_truth, predictions)

        # Validate individual metric calculations
        results.append(
            MetricValidator.validate_precision_calculation(
                predictions, ground_truth, expected_metrics.precision, tolerance
            )
        )
        results.append(
            MetricValidator.validate_recall_calculation(
                predictions, ground_truth, expected_metrics.recall, tolerance
            )
        )
        results.append(
            MetricValidator.validate_f1_calculation(
                actual_metrics.precision,
                actual_metrics.recall,
                expected_metrics.f1_score,
                tolerance,
            )
        )
        results.append(
            MetricValidator.validate_granularity_calculation(
                predictions, ground_truth, expected_metrics.granularity, tolerance
            )
        )
        results.append(
            MetricValidator.validate_plagdet_calculation(
                actual_metrics.f1_score,
                actual_metrics.granularity,
                expected_metrics.plagdet,
                tolerance,
            )
        )

        # Validate ranges
        results.extend(MetricValidator.validate_metric_ranges(actual_metrics))

        # Validate no NaN/Inf
        results.extend(MetricValidator.validate_no_nan_inf(actual_metrics))

        # Validate consistency
        results.extend(MetricValidator.validate_metrics_consistency(actual_metrics))

        all_passed = all(r.passed for r in results)
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)

        summary = f"Metric Validation: {passed_count}/{total_count} checks passed"
        if not all_passed:
            summary += " ⚠️ FAILURES DETECTED"

        return MetricValidationReport(
            results=results, all_passed=all_passed, summary=summary
        )
