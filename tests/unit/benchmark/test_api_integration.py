"""Unit tests for API integration."""
import pytest
from src.backend.benchmark.validation.api_integration import (
    BenchmarkValidationRequest,
    BenchmarkValidationResponse,
    BenchmarkValidationService,
    ValidationAPIEndpoints,
)
from src.backend.evaluation.pan_metrics import (
    Detection,
    TextSpan,
    PANMetrics,
)


class TestBenchmarkValidationRequest:
    """Tests for validation request."""

    def test_create_request(self):
        """Test creating a validation request."""
        request = BenchmarkValidationRequest(
            run_id="run-001",
            dataset_id="dataset-001",
            tool_ids=["jplag", "moss"],
        )
        assert request.run_id == "run-001"
        assert request.dataset_id == "dataset-001"
        assert len(request.tool_ids) == 2
        assert request.validate_metrics is True

    def test_request_with_custom_levels(self):
        """Test request with custom confidence/significance levels."""
        request = BenchmarkValidationRequest(
            run_id="run-001",
            dataset_id="dataset-001",
            tool_ids=["jplag"],
            confidence_level=0.99,
            significance_level=0.01,
        )
        assert request.confidence_level == 0.99
        assert request.significance_level == 0.01


class TestBenchmarkValidationResponse:
    """Tests for validation response."""

    def test_create_response(self):
        """Test creating a validation response."""
        response = BenchmarkValidationResponse(
            run_id="run-001",
            timestamp="2026-04-30T00:00:00Z",
            validation_status="passed",
        )
        assert response.run_id == "run-001"
        assert response.validation_status == "passed"
        assert len(response.errors) == 0

    def test_response_to_dict(self):
        """Test converting response to dict."""
        response = BenchmarkValidationResponse(
            run_id="run-001",
            timestamp="2026-04-30T00:00:00Z",
            validation_status="passed",
            summary="All checks passed",
        )
        d = response.to_dict()
        assert d["run_id"] == "run-001"
        assert d["validation_status"] == "passed"
        assert d["summary"] == "All checks passed"

    def test_response_to_json(self):
        """Test converting response to JSON."""
        response = BenchmarkValidationResponse(
            run_id="run-001",
            timestamp="2026-04-30T00:00:00Z",
            validation_status="passed",
        )
        json_str = response.to_json()
        assert "run-001" in json_str
        assert "passed" in json_str

    def test_response_with_errors(self):
        """Test response with errors."""
        response = BenchmarkValidationResponse(
            run_id="run-001",
            timestamp="2026-04-30T00:00:00Z",
            validation_status="failed",
            errors=["Error 1", "Error 2"],
        )
        assert len(response.errors) == 2
        assert "Error 1" in response.errors


class TestBenchmarkValidationService:
    """Tests for validation service."""

    def test_validate_metrics(self):
        """Test metric validation through service."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        expected = PANMetrics(1.0, 1.0, 1.0, 1.0, 1.0)

        report = BenchmarkValidationService.validate_metrics(gt, pred, expected)
        assert report.all_passed

    def test_validate_dataset(self):
        """Test dataset validation through service."""
        pairs = [
            {"source_code": "x" * 100, "suspicious_code": "y" * 100},
            {"source_code": "a" * 100, "suspicious_code": "b" * 100},
        ]
        labels = [0, 1]
        pair_ids = ["p1", "p2"]

        report = BenchmarkValidationService.validate_dataset(
            "dataset-001", pairs, labels, pair_ids
        )
        assert report.dataset_id == "dataset-001"

    def test_validate_tool_output(self):
        """Test tool output validation through service."""
        output = {"score": 0.75, "matches": []}

        report = BenchmarkValidationService.validate_tool_output("jplag", output)
        assert report.tool_id == "jplag"
        assert report.all_passed

    def test_create_reproducibility_manifest(self):
        """Test creating manifest through service."""
        manifest = BenchmarkValidationService.create_reproducibility_manifest(
            "run-001",
            description="Test run",
            codeprovenance_version="abc123",
        )
        assert manifest.run_id == "run-001"
        assert manifest.description == "Test run"

    def test_analyze_statistics(self):
        """Test statistical analysis through service."""
        metrics_list = [
            PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825),
            PANMetrics(0.75, 0.80, 0.775, 1.0, 0.775),
        ]

        report = BenchmarkValidationService.analyze_statistics(metrics_list)
        assert len(report.confidence_intervals) > 0

    def test_validate_benchmark_run(self):
        """Test complete benchmark run validation."""
        gt = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        pred = [Detection(
            suspicious_span=TextSpan(0, 100),
            source_span=TextSpan(0, 100)
        )]
        expected = PANMetrics(1.0, 1.0, 1.0, 1.0, 1.0)
        pairs = [{"source_code": "x" * 100, "suspicious_code": "y" * 100}]
        labels = [0]
        pair_ids = ["p1"]
        tool_outputs = {"jplag": [{"score": 0.75, "matches": []}]}
        metrics_list = [PANMetrics(0.8, 0.85, 0.825, 1.0, 0.825)]

        request = BenchmarkValidationRequest(
            run_id="run-001",
            dataset_id="dataset-001",
            tool_ids=["jplag"],
        )

        response = BenchmarkValidationService.validate_benchmark_run(
            request,
            gt,
            pred,
            expected,
            pairs,
            labels,
            pair_ids,
            tool_outputs,
            metrics_list,
        )

        assert response.run_id == "run-001"
        assert response.validation_status in ["passed", "partial", "failed"]


class TestValidationAPIEndpoints:
    """Tests for API endpoints."""

    def test_validate_benchmark_endpoint(self):
        """Test benchmark validation endpoint."""
        response = ValidationAPIEndpoints.validate_benchmark_endpoint(
            run_id="run-001",
            dataset_id="dataset-001",
            tool_ids=["jplag"],
            ground_truth=[
                {
                    "suspicious_offset": 0,
                    "suspicious_length": 100,
                    "source_offset": 0,
                    "source_length": 100,
                }
            ],
            predictions=[
                {
                    "suspicious_offset": 0,
                    "suspicious_length": 100,
                    "source_offset": 0,
                    "source_length": 100,
                }
            ],
            expected_metrics={
                "precision": 1.0,
                "recall": 1.0,
                "f1_score": 1.0,
                "granularity": 1.0,
                "plagdet": 1.0,
            },
            pairs=[{"source_code": "x" * 100, "suspicious_code": "y" * 100}],
            labels=[0],
            pair_ids=["p1"],
            tool_outputs={"jplag": [{"score": 0.75, "matches": []}]},
            metrics_list=[
                {
                    "precision": 0.8,
                    "recall": 0.85,
                    "f1_score": 0.825,
                    "granularity": 1.0,
                    "plagdet": 0.825,
                }
            ],
        )

        assert response.run_id == "run-001"
        assert response.validation_status in ["passed", "partial", "failed"]

    def test_get_validation_status_endpoint(self):
        """Test getting validation status."""
        status = ValidationAPIEndpoints.get_validation_status_endpoint("run-001")
        assert status["run_id"] == "run-001"
        assert "status" in status
        assert "timestamp" in status

    def test_get_validation_report_endpoint(self):
        """Test getting validation report."""
        report = ValidationAPIEndpoints.get_validation_report_endpoint("run-001")
        assert report["run_id"] == "run-001"
        assert "report" in report

    def test_compare_tools_endpoint(self):
        """Test tool comparison endpoint."""
        comparison = ValidationAPIEndpoints.compare_tools_endpoint(
            tool1_id="jplag",
            tool2_id="moss",
            metrics1=[
                {
                    "precision": 0.8,
                    "recall": 0.85,
                    "f1_score": 0.825,
                    "granularity": 1.0,
                    "plagdet": 0.825,
                }
            ],
            metrics2=[
                {
                    "precision": 0.8,
                    "recall": 0.85,
                    "f1_score": 0.825,
                    "granularity": 1.0,
                    "plagdet": 0.825,
                }
            ],
        )

        assert comparison["tool1"] == "jplag"
        assert comparison["tool2"] == "moss"
        assert "test" in comparison
        assert "p_value" in comparison
        assert "significant" in comparison
