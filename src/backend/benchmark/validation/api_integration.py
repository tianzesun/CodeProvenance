"""API integration for benchmark validation framework.

Provides endpoints and utilities for validating benchmark runs through the API.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from src.backend.benchmark.validation.metric_validators import (
    MetricValidator,
    MetricValidationReport,
)
from src.backend.benchmark.validation.label_validators import (
    LabelValidator,
    LabelValidationReport,
)
from src.backend.benchmark.validation.tool_validators import (
    ToolValidator,
    ToolValidationReport,
)
from src.backend.benchmark.validation.reproducibility import (
    ReproducibilityManifest,
)
from src.backend.benchmark.validation.statistical_rigor import (
    StatisticalAnalyzer,
    StatisticalReport,
)
from src.backend.evaluation.pan_metrics import (
    Detection,
    TextSpan,
    PANMetrics,
)


@dataclass
class BenchmarkValidationRequest:
    """Request to validate a benchmark run."""
    run_id: str
    dataset_id: str
    tool_ids: List[str]
    validate_metrics: bool = True
    validate_labels: bool = True
    validate_tools: bool = True
    validate_reproducibility: bool = True
    validate_statistics: bool = True
    confidence_level: float = 0.95
    significance_level: float = 0.05


@dataclass
class BenchmarkValidationResponse:
    """Response from benchmark validation."""
    run_id: str
    timestamp: str
    validation_status: str  # "passed", "failed", "partial"
    metric_validation: Optional[Dict[str, Any]] = None
    label_validation: Optional[Dict[str, Any]] = None
    tool_validations: Optional[Dict[str, Dict[str, Any]]] = None
    reproducibility_manifest: Optional[Dict[str, Any]] = None
    statistical_analysis: Optional[Dict[str, Any]] = None
    summary: str = ""
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert response to JSON."""
        return json.dumps(self.to_dict(), indent=2)


class BenchmarkValidationService:
    """Service for validating benchmark runs."""

    @staticmethod
    def validate_metrics(
        ground_truth: List[Detection],
        predictions: List[Detection],
        expected_metrics: PANMetrics,
    ) -> MetricValidationReport:
        """Validate metrics for a benchmark run.

        Args:
            ground_truth: Ground truth detections
            predictions: Predicted detections
            expected_metrics: Expected metric values

        Returns:
            MetricValidationReport
        """
        return MetricValidator.validate_complete_metrics(
            predictions, ground_truth, expected_metrics
        )

    @staticmethod
    def validate_dataset(
        dataset_id: str,
        pairs: List[Dict[str, Any]],
        labels: List[int],
        pair_ids: List[str],
        inter_rater_labels: Optional[Dict[str, List[int]]] = None,
    ) -> LabelValidationReport:
        """Validate dataset labels.

        Args:
            dataset_id: Dataset identifier
            pairs: List of code pairs
            labels: Binary labels
            pair_ids: Pair identifiers
            inter_rater_labels: Optional inter-rater labels

        Returns:
            LabelValidationReport
        """
        return LabelValidator.validate_complete_dataset(
            dataset_id, pairs, labels, pair_ids, inter_rater_labels
        )

    @staticmethod
    def validate_tool_output(
        tool_id: str,
        output: Dict[str, Any],
    ) -> ToolValidationReport:
        """Validate tool output.

        Args:
            tool_id: Tool identifier
            output: Tool output dictionary

        Returns:
            ToolValidationReport
        """
        return ToolValidator.validate_tool_output(tool_id, output)

    @staticmethod
    def validate_tool_determinism(
        tool_id: str,
        outputs: List[Dict[str, Any]],
    ) -> ToolValidationReport:
        """Validate tool determinism.

        Args:
            tool_id: Tool identifier
            outputs: List of outputs from multiple runs

        Returns:
            ToolValidationReport
        """
        return ToolValidator.validate_tool_determinism(tool_id, outputs)

    @staticmethod
    def create_reproducibility_manifest(
        run_id: str,
        description: str = "",
        codeprovenance_version: str = "",
    ) -> ReproducibilityManifest:
        """Create reproducibility manifest.

        Args:
            run_id: Run identifier
            description: Run description
            codeprovenance_version: CodeProvenance version

        Returns:
            ReproducibilityManifest
        """
        return ReproducibilityManifest.create_current(
            run_id, description, codeprovenance_version
        )

    @staticmethod
    def analyze_statistics(
        metrics_list: List[PANMetrics],
        confidence: float = 0.95,
        alpha: float = 0.05,
    ) -> StatisticalReport:
        """Perform statistical analysis.

        Args:
            metrics_list: List of metrics
            confidence: Confidence level
            alpha: Significance level

        Returns:
            StatisticalReport
        """
        return StatisticalAnalyzer.analyze_metrics(
            metrics_list, confidence=confidence, alpha=alpha
        )

    @staticmethod
    def validate_benchmark_run(
        request: BenchmarkValidationRequest,
        ground_truth: List[Detection],
        predictions: List[Detection],
        expected_metrics: PANMetrics,
        pairs: List[Dict[str, Any]],
        labels: List[int],
        pair_ids: List[str],
        tool_outputs: Dict[str, List[Dict[str, Any]]],
        metrics_list: List[PANMetrics],
    ) -> BenchmarkValidationResponse:
        """Validate complete benchmark run.

        Args:
            request: Validation request
            ground_truth: Ground truth detections
            predictions: Predicted detections
            expected_metrics: Expected metrics
            pairs: Code pairs
            labels: Binary labels
            pair_ids: Pair identifiers
            tool_outputs: Tool outputs by tool ID
            metrics_list: List of metrics

        Returns:
            BenchmarkValidationResponse
        """
        response = BenchmarkValidationResponse(
            run_id=request.run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            validation_status="passed",
        )

        try:
            # Validate metrics
            if request.validate_metrics:
                metric_report = BenchmarkValidationService.validate_metrics(
                    ground_truth, predictions, expected_metrics
                )
                response.metric_validation = {
                    "passed": metric_report.all_passed,
                    "checks_passed": sum(1 for r in metric_report.results if r.passed),
                    "total_checks": len(metric_report.results),
                    "summary": metric_report.summary,
                }
                if not metric_report.all_passed:
                    response.validation_status = "partial"

            # Validate labels
            if request.validate_labels:
                label_report = BenchmarkValidationService.validate_dataset(
                    request.dataset_id, pairs, labels, pair_ids
                )
                response.label_validation = {
                    "passed": label_report.all_passed,
                    "certification_level": label_report.certification_level,
                    "checks_passed": sum(1 for r in label_report.results if r.passed),
                    "total_checks": len(label_report.results),
                    "summary": label_report.summary,
                }
                if not label_report.all_passed:
                    response.validation_status = "partial"

            # Validate tools
            if request.validate_tools:
                response.tool_validations = {}
                for tool_id, outputs in tool_outputs.items():
                    if tool_id in request.tool_ids:
                        # Validate single output
                        if outputs:
                            tool_report = BenchmarkValidationService.validate_tool_output(
                                tool_id, outputs[0]
                            )
                            response.tool_validations[tool_id] = {
                                "passed": tool_report.all_passed,
                                "checks_passed": sum(
                                    1 for r in tool_report.results if r.passed
                                ),
                                "total_checks": len(tool_report.results),
                            }

                            # Validate determinism if multiple outputs
                            if len(outputs) > 1:
                                det_report = (
                                    BenchmarkValidationService.validate_tool_determinism(
                                        tool_id, outputs
                                    )
                                )
                                response.tool_validations[tool_id]["determinism_score"] = (
                                    det_report.determinism_score
                                )

            # Create reproducibility manifest
            if request.validate_reproducibility:
                manifest = BenchmarkValidationService.create_reproducibility_manifest(
                    request.run_id
                )
                response.reproducibility_manifest = manifest.to_dict()

            # Perform statistical analysis
            if request.validate_statistics:
                stat_report = BenchmarkValidationService.analyze_statistics(
                    metrics_list,
                    confidence=request.confidence_level,
                    alpha=request.significance_level,
                )
                response.statistical_analysis = {
                    "confidence_intervals": [
                        {
                            "metric": ci.metric_name,
                            "point_estimate": ci.point_estimate,
                            "lower_bound": ci.lower_bound,
                            "upper_bound": ci.upper_bound,
                            "confidence_level": ci.confidence_level,
                        }
                        for ci in stat_report.confidence_intervals
                    ],
                    "summary": stat_report.summary,
                }

            # Generate summary
            if response.validation_status == "passed":
                response.summary = "All validation checks passed ✅"
            else:
                response.summary = "Some validation checks failed ⚠️"

        except Exception as e:
            response.validation_status = "failed"
            response.errors.append(str(e))
            response.summary = f"Validation failed: {str(e)}"

        return response


class ValidationAPIEndpoints:
    """API endpoints for validation framework."""

    @staticmethod
    def validate_benchmark_endpoint(
        run_id: str,
        dataset_id: str,
        tool_ids: List[str],
        ground_truth: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        expected_metrics: Dict[str, float],
        pairs: List[Dict[str, Any]],
        labels: List[int],
        pair_ids: List[str],
        tool_outputs: Dict[str, List[Dict[str, Any]]],
        metrics_list: List[Dict[str, float]],
    ) -> BenchmarkValidationResponse:
        """Endpoint to validate a benchmark run.

        Args:
            run_id: Run identifier
            dataset_id: Dataset identifier
            tool_ids: List of tool IDs
            ground_truth: Ground truth detections
            predictions: Predicted detections
            expected_metrics: Expected metric values
            pairs: Code pairs
            labels: Binary labels
            pair_ids: Pair identifiers
            tool_outputs: Tool outputs
            metrics_list: List of metrics

        Returns:
            BenchmarkValidationResponse
        """
        # Convert dicts to objects
        gt_detections = [
            Detection(
                suspicious_span=TextSpan(d["suspicious_offset"], d["suspicious_length"]),
                source_span=TextSpan(d["source_offset"], d["source_length"]),
            )
            for d in ground_truth
        ]

        pred_detections = [
            Detection(
                suspicious_span=TextSpan(d["suspicious_offset"], d["suspicious_length"]),
                source_span=TextSpan(d["source_offset"], d["source_length"]),
            )
            for d in predictions
        ]

        expected = PANMetrics(
            precision=expected_metrics.get("precision", 0.0),
            recall=expected_metrics.get("recall", 0.0),
            f1_score=expected_metrics.get("f1_score", 0.0),
            granularity=expected_metrics.get("granularity", 1.0),
            plagdet=expected_metrics.get("plagdet", 0.0),
        )

        metrics_objs = [
            PANMetrics(
                precision=m.get("precision", 0.0),
                recall=m.get("recall", 0.0),
                f1_score=m.get("f1_score", 0.0),
                granularity=m.get("granularity", 1.0),
                plagdet=m.get("plagdet", 0.0),
            )
            for m in metrics_list
        ]

        request = BenchmarkValidationRequest(
            run_id=run_id,
            dataset_id=dataset_id,
            tool_ids=tool_ids,
        )

        return BenchmarkValidationService.validate_benchmark_run(
            request,
            gt_detections,
            pred_detections,
            expected,
            pairs,
            labels,
            pair_ids,
            tool_outputs,
            metrics_objs,
        )

    @staticmethod
    def get_validation_status_endpoint(run_id: str) -> Dict[str, Any]:
        """Endpoint to get validation status of a run.

        Args:
            run_id: Run identifier

        Returns:
            Validation status dictionary
        """
        # This would load from database in real implementation
        return {
            "run_id": run_id,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @staticmethod
    def get_validation_report_endpoint(run_id: str) -> Dict[str, Any]:
        """Endpoint to get full validation report.

        Args:
            run_id: Run identifier

        Returns:
            Full validation report
        """
        # This would load from database in real implementation
        return {
            "run_id": run_id,
            "report": "validation report data",
        }

    @staticmethod
    def compare_tools_endpoint(
        tool1_id: str,
        tool2_id: str,
        metrics1: List[Dict[str, float]],
        metrics2: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Endpoint to compare two tools statistically.

        Args:
            tool1_id: First tool ID
            tool2_id: Second tool ID
            metrics1: Metrics from tool 1
            metrics2: Metrics from tool 2

        Returns:
            Comparison results
        """
        metrics1_objs = [
            PANMetrics(
                precision=m.get("precision", 0.0),
                recall=m.get("recall", 0.0),
                f1_score=m.get("f1_score", 0.0),
                granularity=m.get("granularity", 1.0),
                plagdet=m.get("plagdet", 0.0),
            )
            for m in metrics1
        ]

        metrics2_objs = [
            PANMetrics(
                precision=m.get("precision", 0.0),
                recall=m.get("recall", 0.0),
                f1_score=m.get("f1_score", 0.0),
                granularity=m.get("granularity", 1.0),
                plagdet=m.get("plagdet", 0.0),
            )
            for m in metrics2
        ]

        comparison = StatisticalAnalyzer.compare_tools(
            metrics1_objs, metrics2_objs, metric_name="f1_score"
        )

        return {
            "tool1": tool1_id,
            "tool2": tool2_id,
            "test": comparison.test_name,
            "statistic": comparison.statistic,
            "p_value": comparison.p_value,
            "significant": comparison.significant,
            "effect_size": comparison.effect_size,
        }
