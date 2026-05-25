"""Validation of plagiarism detection tool outputs and consistency.

Ensures tool outputs are valid, deterministic, and reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import math
import json


@dataclass
class ToolValidationResult:
    """Result of a tool validation check."""
    check_name: str
    tool_id: str
    passed: bool
    value: Any
    expected: Any | None = None
    details: str = ""

    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        if self.details:
            return f"{status} {self.tool_id}/{self.check_name}: {self.details}"
        return f"{status} {self.tool_id}/{self.check_name}: {self.value}"


@dataclass
class ToolValidationReport:
    """Complete validation report for tool outputs."""
    tool_id: str
    results: List[ToolValidationResult]
    all_passed: bool
    summary: str
    determinism_score: float  # 0-1, how deterministic is the tool

    def __str__(self) -> str:
        lines = [
            f"Tool: {self.tool_id}",
            f"Determinism Score: {self.determinism_score:.2%}",
            self.summary,
        ]
        for result in self.results:
            lines.append(f"  {result}")
        return "\n".join(lines)


class ToolValidator:
    """Validates plagiarism detection tool outputs."""

    # Required fields in tool output
    REQUIRED_FIELDS = {"score", "matches"}

    # Valid score range
    MIN_SCORE = 0.0
    MAX_SCORE = 1.0

    @staticmethod
    def validate_score_range(
        output: Dict[str, Any],
    ) -> ToolValidationResult:
        """Validate that similarity score is in valid range [0, 1].

        Args:
            output: Tool output dictionary

        Returns:
            Validation result
        """
        if "score" not in output:
            return ToolValidationResult(
                check_name="Score Range",
                tool_id="unknown",
                passed=False,
                value=None,
                details="Missing 'score' field",
            )

        score = output["score"]

        # Check type
        if not isinstance(score, (int, float)):
            return ToolValidationResult(
                check_name="Score Range",
                tool_id="unknown",
                passed=False,
                value=score,
                details=f"Score must be numeric, got {type(score).__name__}",
            )

        # Check range
        passed = ToolValidator.MIN_SCORE <= score <= ToolValidator.MAX_SCORE

        return ToolValidationResult(
            check_name="Score Range",
            tool_id="unknown",
            passed=passed,
            value=score,
            expected=(ToolValidator.MIN_SCORE, ToolValidator.MAX_SCORE),
            details=f"Score {score:.4f} in [{ToolValidator.MIN_SCORE}, {ToolValidator.MAX_SCORE}]",
        )

    @staticmethod
    def validate_required_fields(
        output: Dict[str, Any],
    ) -> ToolValidationResult:
        """Validate that output contains all required fields.

        Args:
            output: Tool output dictionary

        Returns:
            Validation result
        """
        missing_fields = ToolValidator.REQUIRED_FIELDS - set(output.keys())
        passed = len(missing_fields) == 0

        return ToolValidationResult(
            check_name="Required Fields",
            tool_id="unknown",
            passed=passed,
            value=len(missing_fields),
            expected=0,
            details=f"Missing: {', '.join(missing_fields)}" if missing_fields else "All required fields present",
        )

    @staticmethod
    def validate_no_nan_inf(
        output: Dict[str, Any],
    ) -> ToolValidationResult:
        """Validate that score is not NaN or Inf.

        Args:
            output: Tool output dictionary

        Returns:
            Validation result
        """
        if "score" not in output:
            return ToolValidationResult(
                check_name="NaN/Inf Check",
                tool_id="unknown",
                passed=False,
                value=None,
                details="Missing 'score' field",
            )

        score = output["score"]
        is_valid = not (math.isnan(score) or math.isinf(score))

        return ToolValidationResult(
            check_name="NaN/Inf Check",
            tool_id="unknown",
            passed=is_valid,
            value=score,
            details=f"Score is {'valid' if is_valid else 'invalid (NaN or Inf)'}",
        )

    @staticmethod
    def validate_decimal_precision(
        output: Dict[str, Any],
        max_decimal_places: int = 6,
    ) -> ToolValidationResult:
        """Validate that score has consistent decimal precision.

        Args:
            output: Tool output dictionary
            max_decimal_places: Maximum allowed decimal places

        Returns:
            Validation result
        """
        if "score" not in output:
            return ToolValidationResult(
                check_name="Decimal Precision",
                tool_id="unknown",
                passed=False,
                value=None,
                details="Missing 'score' field",
            )

        score = output["score"]
        score_str = str(score)

        # Count decimal places
        if "." in score_str:
            decimal_places = len(score_str.split(".")[1])
        else:
            decimal_places = 0

        passed = decimal_places <= max_decimal_places

        return ToolValidationResult(
            check_name="Decimal Precision",
            tool_id="unknown",
            passed=passed,
            value=decimal_places,
            expected=max_decimal_places,
            details=f"{decimal_places} decimal places (max {max_decimal_places})",
        )

    @staticmethod
    def validate_matches_format(
        output: Dict[str, Any],
    ) -> ToolValidationResult:
        """Validate that matches field has correct format.

        Args:
            output: Tool output dictionary

        Returns:
            Validation result
        """
        if "matches" not in output:
            return ToolValidationResult(
                check_name="Matches Format",
                tool_id="unknown",
                passed=False,
                value=None,
                details="Missing 'matches' field",
            )

        matches = output["matches"]

        # Should be a list
        if not isinstance(matches, list):
            return ToolValidationResult(
                check_name="Matches Format",
                tool_id="unknown",
                passed=False,
                value=type(matches).__name__,
                details=f"Matches must be a list, got {type(matches).__name__}",
            )

        # Each match should be a dict with required fields
        valid_matches = 0
        for match in matches:
            if isinstance(match, dict) and "source_start" in match and "suspicious_start" in match:
                valid_matches += 1

        passed = valid_matches == len(matches)

        return ToolValidationResult(
            check_name="Matches Format",
            tool_id="unknown",
            passed=passed,
            value=valid_matches,
            expected=len(matches),
            details=f"{valid_matches}/{len(matches)} matches have valid format",
        )

    @staticmethod
    def check_determinism(
        outputs: List[Dict[str, Any]],
    ) -> Tuple[float, List[ToolValidationResult]]:
        """Check determinism by comparing multiple runs on same input.

        Args:
            outputs: List of outputs from multiple runs

        Returns:
            Tuple of (determinism_score, validation_results)
        """
        results = []

        if len(outputs) < 2:
            return 1.0, results

        # Compare scores
        scores = [o.get("score") for o in outputs]
        score_variance = max(scores) - min(scores) if scores else 0

        score_deterministic = score_variance < 1e-6

        results.append(
            ToolValidationResult(
                check_name="Score Determinism",
                tool_id="unknown",
                passed=score_deterministic,
                value=score_variance,
                expected=0,
                details=f"Score variance: {score_variance:.2e}",
            )
        )

        # Compare matches
        matches_deterministic = True
        for i in range(1, len(outputs)):
            matches_same = (
                json.dumps(outputs[i].get("matches", []), sort_keys=True)
                == json.dumps(outputs[0].get("matches", []), sort_keys=True)
            )
            if not matches_same:
                matches_deterministic = False
                break

        results.append(
            ToolValidationResult(
                check_name="Matches Determinism",
                tool_id="unknown",
                passed=matches_deterministic,
                value=1 if matches_deterministic else 0,
                expected=1,
                details="Matches are " + ("identical" if matches_deterministic else "different"),
            )
        )

        # Calculate overall determinism score
        determinism_score = (
            (1.0 if score_deterministic else 0.5)
            + (1.0 if matches_deterministic else 0.5)
        ) / 2.0

        return determinism_score, results

    @staticmethod
    def validate_tool_output(
        tool_id: str,
        output: Dict[str, Any],
    ) -> ToolValidationReport:
        """Perform complete validation of a single tool output.

        Args:
            tool_id: Tool identifier
            output: Tool output dictionary

        Returns:
            Complete validation report
        """
        results = []

        # Add tool_id to results
        results.append(ToolValidator.validate_required_fields(output))
        results[-1].tool_id = tool_id

        results.append(ToolValidator.validate_score_range(output))
        results[-1].tool_id = tool_id

        results.append(ToolValidator.validate_no_nan_inf(output))
        results[-1].tool_id = tool_id

        results.append(ToolValidator.validate_decimal_precision(output))
        results[-1].tool_id = tool_id

        results.append(ToolValidator.validate_matches_format(output))
        results[-1].tool_id = tool_id

        all_passed = all(r.passed for r in results)
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)

        summary = f"Tool Output Validation: {passed_count}/{total_count} checks passed"
        if not all_passed:
            summary += " ⚠️ ISSUES DETECTED"

        return ToolValidationReport(
            tool_id=tool_id,
            results=results,
            all_passed=all_passed,
            summary=summary,
            determinism_score=1.0,  # Will be updated if determinism check is run
        )

    @staticmethod
    def validate_tool_determinism(
        tool_id: str,
        outputs: List[Dict[str, Any]],
    ) -> ToolValidationReport:
        """Validate tool determinism across multiple runs.

        Args:
            tool_id: Tool identifier
            outputs: List of outputs from multiple runs on same input

        Returns:
            Complete validation report
        """
        determinism_score, results = ToolValidator.check_determinism(outputs)

        for result in results:
            result.tool_id = tool_id

        all_passed = all(r.passed for r in results)
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)

        summary = f"Tool Determinism: {passed_count}/{total_count} checks passed"
        if not all_passed:
            summary += " ⚠️ NON-DETERMINISTIC BEHAVIOR DETECTED"

        return ToolValidationReport(
            tool_id=tool_id,
            results=results,
            all_passed=all_passed,
            summary=summary,
            determinism_score=determinism_score,
        )
