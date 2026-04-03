from __future__ import annotations

import json
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .statistics.bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_metric,
    paired_bootstrap_test,
)
from .statistics.mcnemar import (
    McNemarResult,
    mcnemar_test,
    mcnemar_test_with_correction,
)
from .statistics.confidence_interval import (
    wilson_score_interval,
    clopper_pearson_interval,
    compute_confidence_interval,
)
from .metrics.roc_auc import (
    compute_roc_auc,
    compute_roc_curve,
    compute_average_precision,
)
from .metrics.calibration import (
    compute_calibration_error,
    compute_expected_calibration_error,
    compute_maximum_calibration_error,
)


@dataclass(frozen=True)
class MetricWithCI:
    """A metric with its confidence interval.

    Attributes:
        value: The metric value.
        ci_lower: Lower bound of confidence interval.
        ci_upper: Upper bound of confidence interval.
        ci_method: Method used to compute CI.
    """
    value: float
    ci_lower: float
    ci_upper: float
    ci_method: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "ci_method": self.ci_method,
        }

    def __str__(self) -> str:
        """Format as string."""
        return f"{self.value:.4f} [{self.ci_lower:.4f}, {self.ci_upper:.4f}]"


@dataclass
class CertificationReport:
    """Comprehensive certification report for classifier evaluation.

    Attributes:
        report_id: Unique report identifier.
        timestamp: Report generation timestamp.
        model_name: Name of the model being evaluated.
        dataset_name: Name of the evaluation dataset.
        n_samples: Number of samples in evaluation set.
        metrics: Dictionary of all computed metrics.
        recommendations: List of recommendations based on metrics.
        metadata: Additional metadata.
    """
    report_id: str
    timestamp: str
    model_name: str
    dataset_name: str
    n_samples: int
    metrics: Dict[str, Any]
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "model_name": self.model_name,
            "dataset_name": self.dataset_name,
            "n_samples": self.n_samples,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, path: Union[str, Path]) -> None:
        """Save report to JSON file.

        Args:
            path: Path to save the JSON file.

        Raises:
            OSError: If file cannot be written.
            PermissionError: If insufficient permissions to write file.
        """
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(self.to_json())
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied: Cannot write to {path}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to save report to {path}: {e}"
            ) from e

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            f"CERTIFICATION REPORT: {self.model_name}",
            "=" * 60,
            f"Report ID: {self.report_id}",
            f"Timestamp: {self.timestamp}",
            f"Dataset: {self.dataset_name}",
            f"Samples: {self.n_samples}",
            "",
            "PERFORMANCE METRICS:",
            "-" * 40,
        ]

        # Add ROC-AUC if available
        if "roc_auc" in self.metrics:
            roc = self.metrics["roc_auc"]
            lines.append(f"ROC-AUC: {roc['value']:.4f} [{roc['ci_lower']:.4f}, {roc['ci_upper']:.4f}]")

        # Add Average Precision if available
        if "average_precision" in self.metrics:
            ap = self.metrics["average_precision"]
            lines.append(f"Average Precision: {ap['value']:.4f} [{ap['ci_lower']:.4f}, {ap['ci_upper']:.4f}]")

        # Add Calibration metrics if available
        if "calibration" in self.metrics:
            cal = self.metrics["calibration"]
            lines.append("")
            lines.append("CALIBRATION METRICS:")
            lines.append("-" * 40)
            lines.append(f"ECE: {cal['ece']:.4f}")
            lines.append(f"MCE: {cal['mce']:.4f}")

        # Add McNemar's test if available
        if "mcnemar" in self.metrics:
            mcn = self.metrics["mcnemar"]
            lines.append("")
            lines.append("MCNEMAR'S TEST:")
            lines.append("-" * 40)
            lines.append(f"Statistic: {mcn['statistic']:.4f}")
            lines.append(f"P-value: {mcn['p_value']:.6f}")
            lines.append(f"Significant: {mcn['significant']}")

        # Add recommendations
        if self.recommendations:
            lines.append("")
            lines.append("RECOMMENDATIONS:")
            lines.append("-" * 40)
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        lines.append("=" * 60)
        return "\n".join(lines)


def _generate_report_id(model_name: str, dataset_name: str) -> str:
    """Generate unique report ID.

    Args:
        model_name: Name of the model being evaluated.
        dataset_name: Name of the evaluation dataset.

    Returns:
        Unique report ID string in format: cert_{model_name}_{dataset_name}_{timestamp}.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"cert_{model_name}_{dataset_name}_{timestamp}"


def _generate_recommendations(
    metrics: Dict[str, Any],
    roc_threshold: float = 0.7,
    ece_threshold: float = 0.05,
    mce_threshold: float = 0.1,
) -> List[str]:
    """Generate recommendations based on metrics.

    Args:
        metrics: Dictionary of computed metrics.
        roc_threshold: Minimum acceptable ROC-AUC.
        ece_threshold: Maximum acceptable ECE.
        mce_threshold: Maximum acceptable MCE.

    Returns:
        List of recommendations.
    """
    recommendations = []

    # Check ROC-AUC
    if "roc_auc" in metrics:
        roc_auc = metrics["roc_auc"]["value"]
        if roc_auc < roc_threshold:
            recommendations.append(
                f"ROC-AUC ({roc_auc:.4f}) is below threshold ({roc_threshold}). "
                "Consider improving model discrimination ability."
            )
        elif roc_auc < 0.8:
            recommendations.append(
                f"ROC-AUC ({roc_auc:.4f}) is acceptable but could be improved. "
                "Consider feature engineering or model architecture changes."
            )

    # Check calibration
    if "calibration" in metrics:
        ece = metrics["calibration"]["ece"]
        mce = metrics["calibration"]["mce"]

        if ece > ece_threshold:
            recommendations.append(
                f"ECE ({ece:.4f}) exceeds threshold ({ece_threshold}). "
                "Model is poorly calibrated. Consider Platt scaling or isotonic regression."
            )

        if mce > mce_threshold:
            recommendations.append(
                f"MCE ({mce:.4f}) exceeds threshold ({mce_threshold}). "
                "Model has severe calibration issues in some confidence bins."
            )

    # Check if no issues found
    if not recommendations:
        recommendations.append(
            "All metrics meet quality thresholds. Model is ready for production deployment."
        )

    return recommendations


def generate_certification_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    model_name: str = "model",
    dataset_name: str = "test_set",
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    calibration_bins: int = 10,
    seed: int = 42,
) -> CertificationReport:
    """Generate comprehensive certification report.

    Args:
        y_true: Ground truth binary labels.
        y_pred: Predicted binary labels.
        y_prob: Predicted probabilities for positive class.
        model_name: Name of the model.
        dataset_name: Name of the dataset.
        n_bootstrap: Number of bootstrap samples for CI.
        confidence_level: Confidence level for intervals.
        calibration_bins: Number of bins for calibration.
        seed: Random seed for reproducibility.

    Returns:
        CertificationReport with all metrics.

    Raises:
        ValueError: If input arrays have mismatched lengths, are empty,
            or contain invalid values.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_prob = np.asarray(y_prob)

    # Validate input arrays
    if len(y_true) == 0:
        raise ValueError("Input arrays cannot be empty")

    if not (len(y_true) == len(y_pred) == len(y_prob)):
        raise ValueError(
            f"Input arrays must have the same length: "
            f"y_true={len(y_true)}, y_pred={len(y_pred)}, y_prob={len(y_prob)}"
        )

    # Validate y_true and y_pred contain binary values
    unique_true = np.unique(y_true)
    unique_pred = np.unique(y_pred)
    if not np.all(np.isin(unique_true, [0, 1])):
        raise ValueError(
            f"y_true must contain only binary values (0, 1), got {unique_true}"
        )
    if not np.all(np.isin(unique_pred, [0, 1])):
        raise ValueError(
            f"y_pred must contain only binary values (0, 1), got {unique_pred}"
        )

    # Validate y_prob contains values in [0, 1]
    if np.any(y_prob < 0) or np.any(y_prob > 1):
        raise ValueError("y_prob must contain values in range [0, 1]")

    # Validate confidence_level
    if not 0 < confidence_level < 1:
        raise ValueError(
            f"confidence_level must be in (0, 1), got {confidence_level}"
        )

    # Validate n_bootstrap
    if n_bootstrap < 1:
        raise ValueError(
            f"n_bootstrap must be at least 1, got {n_bootstrap}"
        )

    # Validate calibration_bins
    if calibration_bins < 2:
        raise ValueError(
            f"calibration_bins must be at least 2, got {calibration_bins}"
        )

    n_samples = len(y_true)

    # Compute ROC-AUC with bootstrap CI
    roc_auc_value = compute_roc_auc(y_true, y_prob)
    roc_ci = bootstrap_metric(
        np.array([roc_auc_value]),
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )

    # Compute Average Precision with bootstrap CI
    ap_value = compute_average_precision(y_true, y_prob)
    ap_ci = bootstrap_metric(
        np.array([ap_value]),
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )

    # Compute calibration metrics
    calibration_result = compute_calibration_error(
        y_true, y_prob, n_bins=calibration_bins
    )

    # Compute Wilson confidence interval for accuracy
    accuracy = np.mean(y_true == y_pred)
    n_correct = int(np.sum(y_true == y_pred))
    wilson_ci = wilson_score_interval(n_correct, n_samples, confidence_level)

    # Compute Clopper-Pearson confidence interval for accuracy
    clopper_ci = clopper_pearson_interval(n_correct, n_samples, confidence_level)

    # Compile metrics
    metrics = {
        "roc_auc": {
            "value": float(roc_auc_value),
            "ci_lower": float(roc_ci.ci_lower),
            "ci_upper": float(roc_ci.ci_upper),
            "ci_method": "bootstrap",
        },
        "average_precision": {
            "value": float(ap_value),
            "ci_lower": float(ap_ci.ci_lower),
            "ci_upper": float(ap_ci.ci_upper),
            "ci_method": "bootstrap",
        },
        "calibration": {
            "ece": float(calibration_result.ece),
            "mce": float(calibration_result.mce),
            "bin_accuracies": calibration_result.bin_accuracies.tolist(),
            "bin_confidences": calibration_result.bin_confidences.tolist(),
            "bin_counts": calibration_result.bin_counts.tolist(),
        },
        "accuracy": {
            "value": float(accuracy),
            "wilson_ci_lower": float(wilson_ci.ci_lower),
            "wilson_ci_upper": float(wilson_ci.ci_upper),
            "clopper_ci_lower": float(clopper_ci.ci_lower),
            "clopper_ci_upper": float(clopper_ci.ci_upper),
        },
        "sample_size": n_samples,
        "positive_rate": float(np.mean(y_true)),
        "prediction_rate": float(np.mean(y_pred)),
    }

    # Generate recommendations
    recommendations = _generate_recommendations(metrics)

    # Create report
    report = CertificationReport(
        report_id=_generate_report_id(model_name, dataset_name),
        timestamp=datetime.now().isoformat(),
        model_name=model_name,
        dataset_name=dataset_name,
        n_samples=n_samples,
        metrics=metrics,
        recommendations=recommendations,
        metadata={
            "n_bootstrap": n_bootstrap,
            "confidence_level": confidence_level,
            "calibration_bins": calibration_bins,
            "seed": seed,
        },
    )

    return report


def compare_classifiers_certification(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_prob_a: np.ndarray,
    y_pred_b: np.ndarray,
    y_prob_b: np.ndarray,
    model_name_a: str = "model_a",
    model_name_b: str = "model_b",
    dataset_name: str = "test_set",
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> Tuple[CertificationReport, CertificationReport, Dict[str, Any]]:
    """Generate certification reports for two classifiers and compare.

    Args:
        y_true: Ground truth binary labels.
        y_pred_a: Predictions from classifier A.
        y_prob_a: Probabilities from classifier A.
        y_pred_b: Predictions from classifier B.
        y_prob_b: Probabilities from classifier B.
        model_name_a: Name of classifier A.
        model_name_b: Name of classifier B.
        dataset_name: Name of the dataset.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level for intervals.
        seed: Random seed.

    Returns:
        Tuple of (report_a, report_b, comparison_results).
    """
    # Generate individual reports
    report_a = generate_certification_report(
        y_true, y_pred_a, y_prob_a,
        model_name=model_name_a,
        dataset_name=dataset_name,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )

    report_b = generate_certification_report(
        y_true, y_pred_b, y_prob_b,
        model_name=model_name_b,
        dataset_name=dataset_name,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )

    # Perform McNemar's test
    mcnemar_result = mcnemar_test_with_correction(y_true, y_pred_a, y_pred_b)

    # Perform paired bootstrap test for ROC-AUC difference
    def roc_auc_diff(y_t: np.ndarray, y_p_a: np.ndarray, y_p_b: np.ndarray) -> float:
        auc_a = compute_roc_auc(y_t, y_p_a)
        auc_b = compute_roc_auc(y_t, y_p_b)
        return auc_a - auc_b

    bootstrap_result = paired_bootstrap_test(
        y_true, y_prob_a, y_prob_b,
        metric_fn=roc_auc_diff,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    comparison = {
        "mcnemar": {
            "statistic": float(mcnemar_result.statistic),
            "p_value": float(mcnemar_result.p_value),
            "significant": mcnemar_result.significant,
            "b": mcnemar_result.b,
            "c": mcnemar_result.c,
        },
        "roc_auc_difference": {
            "mean_diff": float(bootstrap_result["mean_diff"]),
            "ci_lower": float(bootstrap_result["ci_lower"]),
            "ci_upper": float(bootstrap_result["ci_upper"]),
            "p_value": float(bootstrap_result["p_value"]),
            "significant": bootstrap_result["significant"],
        },
        "recommendation": _generate_comparison_recommendation(
            mcnemar_result, bootstrap_result, model_name_a, model_name_b
        ),
    }

    return report_a, report_b, comparison


def _generate_comparison_recommendation(
    mcnemar_result: McNemarResult,
    bootstrap_result: Dict[str, Any],
    model_a: str,
    model_b: str,
) -> str:
    """Generate recommendation from classifier comparison.

    Args:
        mcnemar_result: Result of McNemar's test.
        bootstrap_result: Result of paired bootstrap test.
        model_a: Name of classifier A.
        model_b: Name of classifier B.

    Returns:
        Recommendation string indicating which model is better.
    """
    if not mcnemar_result.significant and not bootstrap_result["significant"]:
        return (
            f"No statistically significant difference between {model_a} and {model_b}. "
            "Both classifiers perform similarly."
        )

    if bootstrap_result["mean_diff"] > 0:
        better = model_a
        worse = model_b
    else:
        better = model_b
        worse = model_a

    return (
        f"{better} significantly outperforms {worse} "
        f"(ROC-AUC diff: {abs(bootstrap_result['mean_diff']):.4f}, "
        f"p={bootstrap_result['p_value']:.6f}). "
        f"Recommend deploying {better}."
    )