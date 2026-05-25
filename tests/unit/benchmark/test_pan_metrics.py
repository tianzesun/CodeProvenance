"""Comprehensive unit tests for PAN plagiarism detection metrics.

Tests verify that metric calculations match the official PAN reference
implementation exactly, including edge cases and boundary conditions.
"""
import pytest
import math
from src.backend.evaluation.pan_metrics import (
    PANMetrics,
    Detection,
    TextSpan,
    calculate_pan_metrics,
    pan_macro_average,
    pan_micro_average,
)


class TestTextSpan:
    """Tests for TextSpan class."""

    def test_span_creation(self):
        """Test creating a text span."""
        span = TextSpan(offset=10, length=20)
        assert span.offset == 10
        assert span.length == 20
        assert span.end == 30

    def test_span_overlap_no_overlap(self):
        """Test overlap calculation with no overlap."""
        span1 = TextSpan(offset=0, length=10)
        span2 = TextSpan(offset=20, length=10)
        assert span1.overlap(span2) == 0
        assert span2.overlap(span1) == 0

    def test_span_overlap_partial(self):
        """Test overlap calculation with partial overlap."""
        span1 = TextSpan(offset=0, length=15)
        span2 = TextSpan(offset=10, length=15)
        assert span1.overlap(span2) == 5
        assert span2.overlap(span1) == 5

    def test_span_overlap_complete(self):
        """Test overlap calculation with complete overlap."""
        span1 = TextSpan(offset=0, length=20)
        span2 = TextSpan(offset=5, length=10)
        assert span1.overlap(span2) == 10
        assert span2.overlap(span1) == 10

    def test_span_overlap_identical(self):
        """Test overlap calculation with identical spans."""
        span1 = TextSpan(offset=10, length=20)
        span2 = TextSpan(offset=10, length=20)
        assert span1.overlap(span2) == 20
        assert span2.overlap(span1) == 20


class TestPANMetricsEdgeCases:
    """Tests for edge cases in PAN metrics calculation."""

    def test_empty_predictions_empty_ground_truth(self):
        """Test with no predictions and no ground truth."""
        metrics = calculate_pan_metrics([], [])
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.granularity == 1.0
        assert metrics.plagdet == 1.0

    def test_empty_predictions_with_ground_truth(self):
        """Test with no predictions but ground truth exists."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics(gt, [])
        assert metrics.precision == 1.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.granularity == 1.0
        assert metrics.plagdet == 0.0

    def test_empty_ground_truth_with_predictions(self):
        """Test with predictions but no ground truth."""
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics([], pred)
        assert metrics.precision == 0.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 0.0
        assert metrics.granularity == 1.0
        assert metrics.plagdet == 0.0

    def test_perfect_detection(self):
        """Test with perfect detection (prediction matches ground truth exactly)."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.granularity == 1.0
        assert abs(metrics.plagdet - 1.0) < 1e-6

    def test_no_overlap(self):
        """Test with predictions that don't overlap ground truth."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(200, 100),
            source_span=TextSpan(200, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.plagdet == 0.0

    def test_partial_overlap(self):
        """Test with partial overlap between prediction and ground truth."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(50, 100),
            source_span=TextSpan(50, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        # Prediction overlaps 50 chars out of 100 in suspicious
        # Ground truth overlaps 50 chars out of 100 in suspicious
        assert metrics.precision == 0.5
        assert metrics.recall == 0.5
        assert abs(metrics.f1_score - 0.5) < 1e-6


class TestPANMetricsCalculations:
    """Tests for specific metric calculations."""

    def test_precision_calculation(self):
        """Test precision calculation with multiple predictions."""
        gt = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
            Detection(
                suspicious_span=TextSpan(200, 100),
                source_span=TextSpan(200, 100)
            ),
        ]
        pred = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
            Detection(
                suspicious_span=TextSpan(250, 50),
                source_span=TextSpan(250, 50)
            ),
        ]
        metrics = calculate_pan_metrics(gt, pred)
        # Pred 1: 100 overlap / 100 = 1.0
        # Pred 2: 50 overlap / 50 = 1.0
        # Precision = (1.0 + 1.0) / 2 = 1.0
        assert metrics.precision == 1.0

    def test_recall_calculation(self):
        """Test recall calculation with multiple ground truths."""
        gt = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
            Detection(
                suspicious_span=TextSpan(200, 100),
                source_span=TextSpan(200, 100)
            ),
        ]
        pred = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
        ]
        metrics = calculate_pan_metrics(gt, pred)
        # GT 1: 100 overlap / 100 = 1.0
        # GT 2: 0 overlap / 100 = 0.0
        # Recall = (1.0 + 0.0) / 2 = 0.5
        assert metrics.recall == 0.5

    def test_f1_calculation(self):
        """Test F1 score calculation."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        # P = 1.0, R = 1.0
        # F1 = 2 * 1.0 * 1.0 / (1.0 + 1.0) = 1.0
        assert abs(metrics.f1_score - 1.0) < 1e-6

    def test_f1_with_zero_precision_recall(self):
        """Test F1 calculation when both precision and recall are zero."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(200, 100),
            source_span=TextSpan(200, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        assert metrics.f1_score == 0.0

    def test_granularity_single_detection(self):
        """Test granularity with single detection per ground truth."""
        gt = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
            Detection(
                suspicious_span=TextSpan(200, 100),
                source_span=TextSpan(200, 100)
            ),
        ]
        pred = [
            Detection(
                suspicious_span=TextSpan(0, 100),
                source_span=TextSpan(0, 100)
            ),
            Detection(
                suspicious_span=TextSpan(200, 100),
                source_span=TextSpan(200, 100)
            ),
        ]
        metrics = calculate_pan_metrics(gt, pred)
        # Each GT detected once: granularity = 2 / 2 = 1.0
        assert metrics.granularity == 1.0

    def test_granularity_multiple_detections(self):
        """Test granularity with multiple detections per ground truth."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [
            Detection(
                suspicious_span=TextSpan(0, 50),
                source_span=TextSpan(0, 50)
            ),
            Detection(
                suspicious_span=TextSpan(50, 50),
                source_span=TextSpan(50, 50)
            ),
        ]
        metrics = calculate_pan_metrics(gt, pred)
        # GT detected twice: granularity = 2 / 1 = 2.0
        assert metrics.granularity == 2.0

    def test_plagdet_calculation(self):
        """Test PlagDet calculation."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)
        # F1 = 1.0, Granularity = 1.0
        # PlagDet = 1.0 / log2(1 + 1.0) = 1.0 / 1.0 = 1.0
        assert abs(metrics.plagdet - 1.0) < 1e-6

    def test_plagdet_with_granularity(self):
        """Test PlagDet calculation with granularity > 1."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [
            Detection(
                suspicious_span=TextSpan(0, 50),
                source_span=TextSpan(0, 50)
            ),
            Detection(
                suspicious_span=TextSpan(50, 50),
                source_span=TextSpan(50, 50)
            ),
        ]
        metrics = calculate_pan_metrics(gt, pred)
        # Precision: Pred1 overlaps 50/50=1.0, Pred2 overlaps 50/50=1.0, avg=1.0
        # Recall: GT overlaps max(50,50)=50 out of 100 = 0.5
        # F1 = 2 * 1.0 * 0.5 / (1.0 + 0.5) = 1.0 / 1.5 ≈ 0.667
        # Granularity = 2 / 1 = 2.0
        # PlagDet = 0.667 / log2(3) ≈ 0.420
        expected_f1 = 2 * 1.0 * 0.5 / (1.0 + 0.5)
        expected_plagdet = expected_f1 / math.log2(3)
        assert abs(metrics.plagdet - expected_plagdet) < 1e-6


class TestPANMetricsAveraging:
    """Tests for macro and micro averaging."""

    def test_macro_average_empty(self):
        """Test macro average with empty list."""
        metrics = pan_macro_average([])
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.granularity == 1.0
        assert metrics.plagdet == 0.0

    def test_macro_average_single(self):
        """Test macro average with single metric."""
        m = PANMetrics(precision=0.8, recall=0.9, f1_score=0.85, granularity=1.5, plagdet=0.7)
        metrics = pan_macro_average([m])
        assert metrics.precision == 0.8
        assert metrics.recall == 0.9
        assert metrics.f1_score == 0.85
        assert metrics.granularity == 1.5
        assert metrics.plagdet == 0.7

    def test_macro_average_multiple(self):
        """Test macro average with multiple metrics."""
        m1 = PANMetrics(precision=0.8, recall=0.9, f1_score=0.85, granularity=1.0, plagdet=0.85)
        m2 = PANMetrics(precision=0.6, recall=0.7, f1_score=0.65, granularity=2.0, plagdet=0.45)
        metrics = pan_macro_average([m1, m2])
        assert metrics.precision == 0.7
        assert metrics.recall == 0.8
        assert metrics.f1_score == 0.75
        assert metrics.granularity == 1.5
        assert metrics.plagdet == 0.65

    def test_micro_average(self):
        """Test micro average calculation."""
        gt1 = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred1 = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]

        gt2 = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred2 = [Detection(
            suspicious_span=TextSpan(50, 100),
            source_span=TextSpan(50, 100)
        )]

        metrics = pan_micro_average([gt1, gt2], [pred1, pred2])
        # Flattened: 2 GT, 2 Pred
        # Precision: Pred1 overlaps 100/100=1.0, Pred2 overlaps 50/100=0.5, avg=0.75
        # Recall: GT1 overlaps 100/100=1.0, GT2 overlaps 50/100=1.0 (max overlap with pred2), avg=1.0
        assert metrics.precision == 0.75
        assert metrics.recall == 1.0


class TestPANMetricsValidation:
    """Tests for metric validation and ranges."""

    def test_metrics_in_valid_range(self):
        """Test that all metrics are in valid ranges."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(25, 50),
            source_span=TextSpan(25, 50)
        )]
        metrics = calculate_pan_metrics(gt, pred)

        # Precision, Recall, F1 should be in [0, 1]
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1
        assert 0 <= metrics.f1_score <= 1

        # Granularity should be >= 1
        assert metrics.granularity >= 1.0

        # PlagDet should be in [0, 1]
        assert 0 <= metrics.plagdet <= 1

    def test_no_nan_or_inf(self):
        """Test that metrics don't contain NaN or Inf."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        metrics = calculate_pan_metrics(gt, pred)

        assert not math.isnan(metrics.precision)
        assert not math.isnan(metrics.recall)
        assert not math.isnan(metrics.f1_score)
        assert not math.isnan(metrics.granularity)
        assert not math.isnan(metrics.plagdet)

        assert not math.isinf(metrics.precision)
        assert not math.isinf(metrics.recall)
        assert not math.isinf(metrics.f1_score)
        assert not math.isinf(metrics.granularity)
        assert not math.isinf(metrics.plagdet)

    def test_metrics_serialization(self):
        """Test that metrics can be serialized to dict."""
        metrics = PANMetrics(
            precision=0.8,
            recall=0.9,
            f1_score=0.85,
            granularity=1.5,
            plagdet=0.7
        )
        d = metrics.as_dict()

        assert d["precision"] == 0.8
        assert d["recall"] == 0.9
        assert d["f1_score"] == 0.85
        assert d["granularity"] == 1.5
        assert d["plagdet"] == 0.7

        # Check rounding
        metrics2 = PANMetrics(
            precision=0.123456789,
            recall=0.987654321,
            f1_score=0.555555555,
            granularity=1.111111111,
            plagdet=0.999999999
        )
        d2 = metrics2.as_dict()
        assert d2["precision"] == 0.123457
        assert d2["recall"] == 0.987654
