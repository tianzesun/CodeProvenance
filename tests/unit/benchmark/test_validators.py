"""Unit tests for benchmark validation modules."""
import pytest
import math
from src.backend.benchmark.validation.metric_validators import (
    MetricValidator,
    MetricValidationResult,
)
from src.backend.benchmark.validation.label_validators import (
    LabelValidator,
)
from src.backend.benchmark.validation.tool_validators import (
    ToolValidator,
)
from src.backend.benchmark.validation.reproducibility import (
    ReproducibilityManifest,
    calculate_file_checksum,
)
from src.backend.evaluation.pan_metrics import (
    Detection,
    TextSpan,
    PANMetrics,
)


class TestMetricValidator:
    """Tests for metric validation."""

    def test_validate_precision_calculation(self):
        """Test precision validation."""
        predictions = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        ground_truth = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        result = MetricValidator.validate_precision_calculation(
            predictions, ground_truth, 1.0
        )
        assert result.passed
        assert result.actual == 1.0

    def test_validate_metric_ranges(self):
        """Test metric range validation."""
        metrics = PANMetrics(
            precision=0.8,
            recall=0.9,
            f1_score=0.85,
            granularity=1.5,
            plagdet=0.7
        )
        results = MetricValidator.validate_metric_ranges(metrics)
        assert all(r.passed for r in results)

    def test_validate_metric_ranges_invalid(self):
        """Test metric range validation with invalid values."""
        metrics = PANMetrics(
            precision=1.5,  # Invalid: > 1
            recall=0.9,
            f1_score=0.85,
            granularity=1.5,
            plagdet=0.7
        )
        results = MetricValidator.validate_metric_ranges(metrics)
        assert not all(r.passed for r in results)

    def test_validate_no_nan_inf(self):
        """Test NaN/Inf validation."""
        metrics = PANMetrics(
            precision=0.8,
            recall=0.9,
            f1_score=0.85,
            granularity=1.5,
            plagdet=0.7
        )
        results = MetricValidator.validate_no_nan_inf(metrics)
        assert all(r.passed for r in results)

    def test_validate_no_nan_inf_with_nan(self):
        """Test NaN/Inf validation with NaN."""
        metrics = PANMetrics(
            precision=float('nan'),
            recall=0.9,
            f1_score=0.85,
            granularity=1.5,
            plagdet=0.7
        )
        results = MetricValidator.validate_no_nan_inf(metrics)
        assert not all(r.passed for r in results)


class TestLabelValidator:
    """Tests for label validation."""

    def test_calculate_cohens_kappa_perfect_agreement(self):
        """Test Cohen's Kappa with perfect agreement."""
        rater1 = [0, 1, 0, 1, 1]
        rater2 = [0, 1, 0, 1, 1]
        kappa = LabelValidator.calculate_cohens_kappa(rater1, rater2)
        assert kappa == 1.0

    def test_calculate_cohens_kappa_no_agreement(self):
        """Test Cohen's Kappa with no agreement."""
        rater1 = [0, 0, 0, 0, 0]
        rater2 = [1, 1, 1, 1, 1]
        kappa = LabelValidator.calculate_cohens_kappa(rater1, rater2)
        assert kappa <= 0  # No agreement or worse than chance

    def test_calculate_cohens_kappa_partial_agreement(self):
        """Test Cohen's Kappa with partial agreement."""
        rater1 = [0, 1, 0, 1, 1]
        rater2 = [0, 1, 1, 1, 0]
        kappa = LabelValidator.calculate_cohens_kappa(rater1, rater2)
        assert 0 < kappa < 1

    def test_check_label_consistency(self):
        """Test label consistency check."""
        labels_by_pair = {
            "pair1": [0, 0],
            "pair2": [1, 1],
            "pair3": [0, 0],
        }
        result = LabelValidator.check_label_consistency(labels_by_pair)
        assert result.passed
        assert result.value == 1.0

    def test_check_label_consistency_with_conflicts(self):
        """Test label consistency check with conflicts."""
        labels_by_pair = {
            "pair1": [0, 0],
            "pair2": [1, 0],  # Conflict
            "pair3": [0, 0],
        }
        result = LabelValidator.check_label_consistency(labels_by_pair, tolerance=1.0)
        assert not result.passed

    def test_check_class_balance(self):
        """Test class balance check."""
        labels = [0, 1, 0, 1, 0, 1]
        result = LabelValidator.check_class_balance(labels)
        assert result.passed
        assert result.value == 0.5

    def test_check_class_balance_imbalanced(self):
        """Test class balance check with imbalanced data."""
        labels = [0, 0, 0, 0, 1]
        result = LabelValidator.check_class_balance(labels, min_minority_rate=0.3)
        assert not result.passed

    def test_check_duplicate_pairs(self):
        """Test duplicate pairs check."""
        pair_ids = ["pair1", "pair2", "pair3"]
        result = LabelValidator.check_duplicate_pairs(pair_ids)
        assert result.passed
        assert result.value == 0

    def test_check_duplicate_pairs_with_duplicates(self):
        """Test duplicate pairs check with duplicates."""
        pair_ids = ["pair1", "pair2", "pair1"]
        result = LabelValidator.check_duplicate_pairs(pair_ids)
        assert not result.passed
        assert result.value == 1


class TestToolValidator:
    """Tests for tool output validation."""

    def test_validate_score_range_valid(self):
        """Test score range validation with valid score."""
        output = {"score": 0.75, "matches": []}
        result = ToolValidator.validate_score_range(output)
        assert result.passed

    def test_validate_score_range_invalid_high(self):
        """Test score range validation with score > 1."""
        output = {"score": 1.5, "matches": []}
        result = ToolValidator.validate_score_range(output)
        assert not result.passed

    def test_validate_score_range_invalid_low(self):
        """Test score range validation with score < 0."""
        output = {"score": -0.1, "matches": []}
        result = ToolValidator.validate_score_range(output)
        assert not result.passed

    def test_validate_required_fields(self):
        """Test required fields validation."""
        output = {"score": 0.75, "matches": []}
        result = ToolValidator.validate_required_fields(output)
        assert result.passed

    def test_validate_required_fields_missing(self):
        """Test required fields validation with missing field."""
        output = {"score": 0.75}
        result = ToolValidator.validate_required_fields(output)
        assert not result.passed

    def test_validate_no_nan_inf_valid(self):
        """Test NaN/Inf validation with valid score."""
        output = {"score": 0.75, "matches": []}
        result = ToolValidator.validate_no_nan_inf(output)
        assert result.passed

    def test_validate_no_nan_inf_nan(self):
        """Test NaN/Inf validation with NaN."""
        output = {"score": float('nan'), "matches": []}
        result = ToolValidator.validate_no_nan_inf(output)
        assert not result.passed

    def test_validate_no_nan_inf_inf(self):
        """Test NaN/Inf validation with Inf."""
        output = {"score": float('inf'), "matches": []}
        result = ToolValidator.validate_no_nan_inf(output)
        assert not result.passed

    def test_check_determinism_identical(self):
        """Test determinism check with identical outputs."""
        outputs = [
            {"score": 0.75, "matches": [{"source_start": 0, "suspicious_start": 0}]},
            {"score": 0.75, "matches": [{"source_start": 0, "suspicious_start": 0}]},
        ]
        score, results = ToolValidator.check_determinism(outputs)
        assert score == 1.0
        assert all(r.passed for r in results)

    def test_check_determinism_different_scores(self):
        """Test determinism check with different scores."""
        outputs = [
            {"score": 0.75, "matches": []},
            {"score": 0.76, "matches": []},
        ]
        score, results = ToolValidator.check_determinism(outputs)
        assert score < 1.0


class TestReproducibilityManifest:
    """Tests for reproducibility manifest."""

    def test_create_manifest(self):
        """Test creating a manifest."""
        manifest = ReproducibilityManifest.create_current(
            run_id="test-run-001",
            description="Test run",
            codeprovenance_version="abc123"
        )
        assert manifest.run_id == "test-run-001"
        assert manifest.description == "Test run"
        assert manifest.codeprovenance_version == "abc123"

    def test_add_dependency(self):
        """Test adding a dependency."""
        manifest = ReproducibilityManifest.create_current("test-run")
        manifest.add_dependency("numpy", "1.24.0")
        assert len(manifest.dependencies) == 1
        assert manifest.dependencies[0].name == "numpy"
        assert manifest.dependencies[0].version == "1.24.0"

    def test_add_tool_version(self):
        """Test adding tool version."""
        manifest = ReproducibilityManifest.create_current("test-run")
        manifest.add_tool_version("jplag", "4.0.0", git_hash="abc123")
        assert len(manifest.tool_versions) == 1
        assert manifest.tool_versions[0].tool_id == "jplag"
        assert manifest.tool_versions[0].version == "4.0.0"

    def test_add_dataset_checksum(self):
        """Test adding dataset checksum."""
        manifest = ReproducibilityManifest.create_current("test-run")
        manifest.add_dataset_checksum(
            "dataset1",
            "abc123def456",
            file_count=100,
            total_size_bytes=1000000,
            pair_count=500
        )
        assert len(manifest.dataset_checksums) == 1
        assert manifest.dataset_checksums[0].dataset_id == "dataset1"

    def test_manifest_to_dict(self):
        """Test converting manifest to dict."""
        manifest = ReproducibilityManifest.create_current("test-run")
        manifest.add_dependency("numpy", "1.24.0")
        d = manifest.to_dict()
        assert d["run_id"] == "test-run"
        assert len(d["dependencies"]) == 1

    def test_manifest_to_json(self):
        """Test converting manifest to JSON."""
        manifest = ReproducibilityManifest.create_current("test-run")
        json_str = manifest.to_json()
        assert "test-run" in json_str
        assert "dependencies" in json_str

    def test_manifest_save_and_load(self, tmp_path):
        """Test saving and loading manifest."""
        manifest = ReproducibilityManifest.create_current("test-run")
        manifest.add_dependency("numpy", "1.24.0")

        # Save
        path = tmp_path / "manifest.json"
        manifest.save(path)
        assert path.exists()

        # Load
        loaded = ReproducibilityManifest.load(path)
        assert loaded.run_id == "test-run"
        assert len(loaded.dependencies) == 1
        assert loaded.dependencies[0].name == "numpy"
