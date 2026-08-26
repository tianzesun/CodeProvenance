"""Historical Fingerprint - Style evolution tracking for submissions.

Tracks how code style changes over time and detects significant deviations
from a student's historical patterns.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Thresholds for style deviation detection
STYLE_DEVIATION_THRESHOLD = 0.3
HISTORICAL_CONSISTENCY_THRESHOLD = 0.5


@dataclass
class StyleFeatures:
    """Extracted style features from code."""

    avg_line_length: float
    max_line_length: int
    indentation_depth: float
    comment_ratio: float
    blank_line_ratio: float
    naming_convention: str  # 'snake_case', 'camelCase', 'PascalCase', 'unknown'
    function_count: int
    class_count: int
    complexity_score: float
    token_count: int
    hash: str = field(default="")

    def __post_init__(self) -> None:
        """Compute hash after initialization."""
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a hash of style features."""
        data = {
            "avg_line_length": self.avg_line_length,
            "indentation_depth": self.indentation_depth,
            "comment_ratio": self.comment_ratio,
            "naming_convention": self.naming_convention,
            "function_count": self.function_count,
            "class_count": self.class_count,
        }
        return hashlib.md5(str(sorted(data.items())).encode()).hexdigest()[:12]


@dataclass
class HistoricalFingerprint:
    """Historical fingerprint for a student's submissions."""

    student_id: str
    submission_history: list[dict[str, Any]] = field(default_factory=list)
    style_trend: dict[str, float] = field(default_factory=dict)
    consistency_score: float = 1.0
    anomalies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "submission_count": len(self.submission_history),
            "consistency_score": self.consistency_score,
            "style_trend": self.style_trend,
            "anomalies": self.anomalies,
        }


@dataclass
class FingerprintResult:
    """Result of fingerprint analysis."""

    student_id: str
    current_features: StyleFeatures
    historical_features: StyleFeatures | None
    deviation_score: float
    is_anomaly: bool
    confidence_score: float
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "current_features": {
                "avg_line_length": self.current_features.avg_line_length,
                "indentation_depth": self.current_features.indentation_depth,
                "comment_ratio": self.current_features.comment_ratio,
                "naming_convention": self.current_features.naming_convention,
                "function_count": self.current_features.function_count,
                "class_count": self.current_features.class_count,
                "complexity_score": self.current_features.complexity_score,
            },
            "historical_features": (
                {
                    "avg_line_length": self.historical_features.avg_line_length,
                    "indentation_depth": self.historical_features.indentation_depth,
                    "comment_ratio": self.historical_features.comment_ratio,
                    "naming_convention": self.historical_features.naming_convention,
                    "function_count": self.historical_features.function_count,
                    "class_count": self.historical_features.class_count,
                    "complexity_score": self.historical_features.complexity_score,
                }
                if self.historical_features
                else None
            ),
            "deviation_score": self.deviation_score,
            "is_anomaly": self.is_anomaly,
            "confidence_score": self.confidence_score,
            "recommendations": self.recommendations,
        }


class HistoricalFingerprintAnalyzer:
    """Analyze historical style patterns for submissions."""

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self._cache: dict[str, HistoricalFingerprint] = {}

    def extract_features(self, code: str) -> StyleFeatures:
        """
        Extract style features from code.

        Args:
            code: Source code to analyze.

        Returns:
            StyleFeatures with extracted metrics.
        """
        lines = code.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]

        # Line length metrics
        line_lengths = [len(line) for line in lines]
        avg_line_length = sum(line_lengths) / len(line_lengths) if lines else 0.0
        max_line_length = max(line_lengths) if lines else 0

        # Indentation depth
        indentations = []
        for line in non_empty_lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            indentations.append(indent)
        avg_indent = sum(indentations) / len(indentations) if indentations else 0.0

        # Comment ratio
        comment_lines = sum(1 for line in lines if line.strip().startswith(("#", "//", "/*")))
        comment_ratio = comment_lines / len(lines) if lines else 0.0

        # Blank line ratio
        blank_lines = sum(1 for line in lines if not line.strip())
        blank_ratio = blank_lines / len(lines) if lines else 0.0

        # Naming convention
        naming = self._detect_naming_convention(code)

        # Count functions and classes
        function_count = len(re.findall(r"def\s+\w+", code))
        class_count = len(re.findall(r"class\s+\w+", code))

        # Complexity score (simplified)
        complexity = self._compute_complexity(code)

        # Token count
        tokens = len(code.split())

        return StyleFeatures(
            avg_line_length=avg_line_length,
            max_line_length=max_line_length,
            indentation_depth=avg_indent / 4,  # Normalize to indent units
            comment_ratio=comment_ratio,
            blank_line_ratio=blank_ratio,
            naming_convention=naming,
            function_count=function_count,
            class_count=class_count,
            complexity_score=complexity,
            token_count=tokens,
        )

    def _detect_naming_convention(self, code: str) -> str:
        """Detect the primary naming convention used."""
        import re

        # Find variable/function names
        names = re.findall(r"\bdef\s+(\w+)|(\w+)\s*=", code)
        flat_names = [n for pair in names for n in pair if n]

        if not flat_names:
            return "unknown"

        snake_case = sum(1 for n in flat_names if "_" in n and n.islower())
        camel_case = sum(1 for n in flat_names if any(c.isupper() for c in n))

        if snake_case > camel_case:
            return "snake_case"
        elif camel_case > 0:
            return "camelCase"
        return "unknown"

    def _compute_complexity(self, code: str) -> float:
        """Compute a simplified complexity score."""
        import re

        # Count control flow statements
        control_keywords = len(re.findall(r"\b(if|for|while|elif|else)\b", code))
        nested_structures = code.count("    ")  # Approximate nesting

        return min(1.0, (control_keywords + nested_structures / 10) / 20)

    def analyze(
        self,
        student_id: str,
        code: str,
        submission_id: str,
        timestamp: datetime | None = None,
    ) -> FingerprintResult:
        """
        Analyze a submission against historical patterns.

        Args:
            student_id: Student identifier.
            code: Source code to analyze.
            submission_id: Submission identifier.
            timestamp: Optional timestamp (defaults to now).

        Returns:
            FingerprintResult with analysis.
        """
        if timestamp is None:
            timestamp = datetime.now()

        current_features = self.extract_features(code)

        # Get historical data
        historical = self._get_or_create_history(student_id)
        historical_features = self._get_last_features(historical)

        # Calculate deviation
        deviation_score = self._calculate_deviation(
            current_features, historical_features
        )

        # Determine if anomaly
        is_anomaly = deviation_score > STYLE_DEVIATION_THRESHOLD

        # Calculate confidence
        confidence = self._calculate_confidence(historical, deviation_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(is_anomaly, deviation_score)

        # Update history
        historical.submission_history.append(
            {
                "submission_id": submission_id,
                "timestamp": timestamp.isoformat(),
                "features": (
                    current_features.to_dict()
                    if hasattr(current_features, "to_dict")
                    else {}
                ),
                "hash": current_features.hash,
            }
        )
        self._cache[student_id] = historical

        return FingerprintResult(
            student_id=student_id,
            current_features=current_features,
            historical_features=historical_features,
            deviation_score=deviation_score,
            is_anomaly=is_anomaly,
            confidence_score=confidence,
            recommendations=recommendations,
        )

    def _get_or_create_history(self, student_id: str) -> HistoricalFingerprint:
        """Get or create historical fingerprint for a student."""
        if student_id not in self._cache:
            self._cache[student_id] = HistoricalFingerprint(student_id=student_id)
        return self._cache[student_id]

    def _get_last_features(
        self, historical: HistoricalFingerprint
    ) -> StyleFeatures | None:
        """Get the most recent style features from history."""
        if not historical.submission_history:
            return None

        last = historical.submission_history[-1]
        features_data = last.get("features", {})

        return StyleFeatures(
            avg_line_length=features_data.get("avg_line_length", 0.0),
            max_line_length=features_data.get("max_line_length", 0),
            indentation_depth=features_data.get("indentation_depth", 0.0),
            comment_ratio=features_data.get("comment_ratio", 0.0),
            blank_line_ratio=features_data.get("blank_line_ratio", 0.0),
            naming_convention=features_data.get("naming_convention", "unknown"),
            function_count=features_data.get("function_count", 0),
            class_count=features_data.get("class_count", 0),
            complexity_score=features_data.get("complexity_score", 0.0),
            token_count=features_data.get("token_count", 0),
        )

    def _calculate_deviation(
        self, current: StyleFeatures, historical: StyleFeatures | None
    ) -> float:
        """Calculate style deviation from historical patterns."""
        if historical is None:
            return 0.0  # No history, cannot compare

        deviations = []

        # Compare each feature
        features_to_compare = [
            "avg_line_length",
            "indentation_depth",
            "comment_ratio",
            "complexity_score",
        ]

        for feature in features_to_compare:
            curr_val = getattr(current, feature, 0.0)
            hist_val = getattr(historical, feature, 0.0)
            if hist_val != 0:
                dev = abs(curr_val - hist_val) / hist_val
            else:
                dev = abs(curr_val)
            deviations.append(min(1.0, dev))

        return sum(deviations) / len(deviations) if deviations else 0.0

    def _calculate_confidence(
        self, historical: HistoricalFingerprint, deviation_score: float
    ) -> float:
        """Calculate confidence in the anomaly detection."""
        submission_count = len(historical.submission_history)

        if submission_count < 3:
            return 0.3  # Low confidence with little history

        if submission_count < 10:
            return 0.6  # Medium confidence

        # Higher confidence with more history
        return min(0.95, 0.6 + submission_count * 0.01)

    def _generate_recommendations(
        self, is_anomaly: bool, deviation_score: float
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if is_anomaly:
            recommendations.append(
                "Significant style deviation detected. Manual review recommended."
            )
            if deviation_score > 0.5:
                recommendations.append(
                    "High deviation score suggests possible external assistance."
                )
        else:
            recommendations.append("Style consistent with historical patterns.")

        return recommendations

    def get_historical_consistency(self, student_id: str) -> float:
        """Get the consistency score for a student."""
        historical = self._cache.get(student_id)
        if historical:
            return historical.consistency_score
        return 1.0


def run_fingerprint_analysis(
    student_id: str,
    code: str,
    submission_id: str,
    history: list[dict[str, Any]] | None = None,
) -> FingerprintResult:
    """
    Convenience function to run fingerprint analysis.

    Args:
        student_id: Student identifier.
        code: Source code to analyze.
        submission_id: Submission identifier.
        history: Optional list of historical submissions.

    Returns:
        FingerprintResult with analysis.
    """
    analyzer = HistoricalFingerprintAnalyzer()
    return analyzer.analyze(student_id, code, submission_id)
