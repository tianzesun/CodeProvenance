"""Validation of dataset labels and ground truth quality.

Ensures dataset labels are consistent, high-quality, and suitable for benchmarking.
Includes inter-rater agreement calculation and conflict detection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Any
from collections import Counter
import math


@dataclass
class LabelValidationResult:
    """Result of a label validation check."""
    check_name: str
    passed: bool
    value: Any
    expected: Any | None = None
    details: str = ""

    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        if self.details:
            return f"{status} {self.check_name}: {self.details}"
        return f"{status} {self.check_name}: {self.value}"


@dataclass
class LabelValidationReport:
    """Complete validation report for dataset labels."""
    dataset_id: str
    results: List[LabelValidationResult]
    all_passed: bool
    certification_level: str  # "gold", "silver", "bronze"
    summary: str

    def __str__(self) -> str:
        lines = [f"Dataset: {self.dataset_id}", f"Certification: {self.certification_level}", self.summary]
        for result in self.results:
            lines.append(f"  {result}")
        return "\n".join(lines)


class LabelValidator:
    """Validates dataset labels and ground truth quality."""

    # Certification thresholds
    GOLD_KAPPA_THRESHOLD = 0.8
    SILVER_KAPPA_THRESHOLD = 0.6
    BRONZE_KAPPA_THRESHOLD = 0.4

    @staticmethod
    def calculate_cohens_kappa(
        rater1_labels: List[int], rater2_labels: List[int]
    ) -> float:
        """Calculate Cohen's Kappa inter-rater agreement coefficient.

        Measures agreement between two raters beyond chance.
        κ = (P_o - P_e) / (1 - P_e)
        where P_o is observed agreement and P_e is expected agreement by chance.

        Args:
            rater1_labels: Labels from first rater (0 or 1)
            rater2_labels: Labels from second rater (0 or 1)

        Returns:
            Cohen's Kappa coefficient in range [-1, 1]
            1.0 = perfect agreement
            0.0 = agreement by chance
            < 0 = worse than chance
        """
        if len(rater1_labels) != len(rater2_labels):
            raise ValueError("Raters must have same number of labels")

        if len(rater1_labels) == 0:
            return 0.0

        n = len(rater1_labels)

        # Observed agreement
        agreements = sum(1 for r1, r2 in zip(rater1_labels, rater2_labels) if r1 == r2)
        p_o = agreements / n

        # Expected agreement by chance
        # For binary classification: P_e = P(both 0) + P(both 1)
        count_0_r1 = sum(1 for r in rater1_labels if r == 0)
        count_1_r1 = sum(1 for r in rater1_labels if r == 1)
        count_0_r2 = sum(1 for r in rater2_labels if r == 0)
        count_1_r2 = sum(1 for r in rater2_labels if r == 1)

        p_e = (count_0_r1 / n) * (count_0_r2 / n) + (count_1_r1 / n) * (count_1_r2 / n)

        # Cohen's Kappa
        if p_e == 1.0:
            return 0.0 if p_o == 1.0 else -1.0

        kappa = (p_o - p_e) / (1 - p_e)
        return kappa

    @staticmethod
    def check_label_consistency(
        labels_by_pair: Dict[str, List[int]], tolerance: float = 0.95
    ) -> LabelValidationResult:
        """Check consistency of labels across multiple annotations.

        Args:
            labels_by_pair: Dict mapping pair_id to list of labels from different raters
            tolerance: Minimum agreement rate required (0-1)

        Returns:
            Validation result
        """
        if not labels_by_pair:
            return LabelValidationResult(
                check_name="Label Consistency",
                passed=False,
                value=0,
                details="No labels provided",
            )

        consistent_pairs = 0
        conflicts = []

        for pair_id, labels in labels_by_pair.items():
            if len(set(labels)) == 1:
                consistent_pairs += 1
            else:
                conflicts.append(pair_id)

        consistency_rate = consistent_pairs / len(labels_by_pair)
        passed = consistency_rate >= tolerance

        return LabelValidationResult(
            check_name="Label Consistency",
            passed=passed,
            value=consistency_rate,
            expected=tolerance,
            details=f"{consistent_pairs}/{len(labels_by_pair)} pairs consistent ({consistency_rate*100:.1f}%)",
        )

    @staticmethod
    def check_class_balance(
        labels: List[int], min_minority_rate: float = 0.1
    ) -> LabelValidationResult:
        """Check that dataset has reasonable class balance.

        Args:
            labels: List of binary labels (0 or 1)
            min_minority_rate: Minimum proportion of minority class (0-1)

        Returns:
            Validation result
        """
        if not labels:
            return LabelValidationResult(
                check_name="Class Balance",
                passed=False,
                value=0,
                details="No labels provided",
            )

        count_0 = sum(1 for l in labels if l == 0)
        count_1 = len(labels) - count_0

        minority_count = min(count_0, count_1)
        minority_rate = minority_count / len(labels)

        passed = minority_rate >= min_minority_rate

        return LabelValidationResult(
            check_name="Class Balance",
            passed=passed,
            value=minority_rate,
            expected=min_minority_rate,
            details=f"Class 0: {count_0}, Class 1: {count_1}, Minority rate: {minority_rate*100:.1f}%",
        )

    @staticmethod
    def check_duplicate_pairs(
        pair_ids: List[str],
    ) -> LabelValidationResult:
        """Check for duplicate pairs in dataset.

        Args:
            pair_ids: List of pair identifiers

        Returns:
            Validation result
        """
        if not pair_ids:
            return LabelValidationResult(
                check_name="Duplicate Pairs",
                passed=True,
                value=0,
                details="No pairs provided",
            )

        unique_pairs = len(set(pair_ids))
        total_pairs = len(pair_ids)
        duplicates = total_pairs - unique_pairs

        passed = duplicates == 0

        return LabelValidationResult(
            check_name="Duplicate Pairs",
            passed=passed,
            value=duplicates,
            expected=0,
            details=f"{unique_pairs} unique pairs out of {total_pairs} total",
        )

    @staticmethod
    def check_pair_validity(
        pairs: List[Dict[str, Any]],
    ) -> LabelValidationResult:
        """Check that all pairs have valid source and suspicious code.

        Args:
            pairs: List of pair dicts with 'source_code' and 'suspicious_code' keys

        Returns:
            Validation result
        """
        if not pairs:
            return LabelValidationResult(
                check_name="Pair Validity",
                passed=True,
                value=0,
                details="No pairs provided",
            )

        valid_pairs = 0
        invalid_pairs = []

        for i, pair in enumerate(pairs):
            has_source = "source_code" in pair and pair["source_code"]
            has_suspicious = "suspicious_code" in pair and pair["suspicious_code"]

            if has_source and has_suspicious:
                valid_pairs += 1
            else:
                invalid_pairs.append(i)

        passed = len(invalid_pairs) == 0

        return LabelValidationResult(
            check_name="Pair Validity",
            passed=passed,
            value=valid_pairs,
            expected=len(pairs),
            details=f"{valid_pairs}/{len(pairs)} pairs valid",
        )

    @staticmethod
    def check_code_length_constraints(
        pairs: List[Dict[str, Any]],
        min_length: int = 10,
        max_length: int = 1000000,
    ) -> LabelValidationResult:
        """Check that code lengths are within reasonable bounds.

        Args:
            pairs: List of pair dicts with 'source_code' and 'suspicious_code' keys
            min_length: Minimum code length in characters
            max_length: Maximum code length in characters

        Returns:
            Validation result
        """
        if not pairs:
            return LabelValidationResult(
                check_name="Code Length Constraints",
                passed=True,
                value=0,
                details="No pairs provided",
            )

        valid_pairs = 0
        violations = []

        for i, pair in enumerate(pairs):
            source_len = len(pair.get("source_code", ""))
            suspicious_len = len(pair.get("suspicious_code", ""))

            if (
                min_length <= source_len <= max_length
                and min_length <= suspicious_len <= max_length
            ):
                valid_pairs += 1
            else:
                violations.append(
                    (i, source_len, suspicious_len)
                )

        passed = len(violations) == 0

        return LabelValidationResult(
            check_name="Code Length Constraints",
            passed=passed,
            value=valid_pairs,
            expected=len(pairs),
            details=f"{valid_pairs}/{len(pairs)} pairs within [{min_length}, {max_length}] chars",
        )

    @staticmethod
    def check_language_consistency(
        pairs: List[Dict[str, Any]],
    ) -> LabelValidationResult:
        """Check that all pairs in dataset use same programming language.

        Args:
            pairs: List of pair dicts with 'language' key

        Returns:
            Validation result
        """
        if not pairs:
            return LabelValidationResult(
                check_name="Language Consistency",
                passed=True,
                value=0,
                details="No pairs provided",
            )

        languages = [pair.get("language", "unknown") for pair in pairs]
        unique_languages = set(languages)

        passed = len(unique_languages) == 1

        return LabelValidationResult(
            check_name="Language Consistency",
            passed=passed,
            value=len(unique_languages),
            expected=1,
            details=f"Languages: {', '.join(unique_languages)}",
        )

    @staticmethod
    def detect_labeling_artifacts(
        labels: List[int],
        pair_ids: List[str],
    ) -> LabelValidationResult:
        """Detect suspicious patterns in labeling that might indicate artifacts.

        Args:
            labels: List of binary labels
            pair_ids: List of pair identifiers

        Returns:
            Validation result
        """
        if not labels:
            return LabelValidationResult(
                check_name="Labeling Artifacts",
                passed=True,
                value=0,
                details="No labels provided",
            )

        artifacts = []

        # Check for all same label
        if len(set(labels)) == 1:
            artifacts.append("All labels are identical (no variation)")

        # Check for suspicious patterns in pair IDs
        # (e.g., all positive labels have similar IDs)
        if len(artifacts) == 0:
            # Check if labels correlate with pair ID patterns
            positive_ids = [pair_ids[i] for i, l in enumerate(labels) if l == 1]
            negative_ids = [pair_ids[i] for i, l in enumerate(labels) if l == 0]

            # Simple heuristic: check if IDs are sequential
            if positive_ids and all(
                int(id.split("_")[-1]) < 100 for id in positive_ids if "_" in id
            ):
                artifacts.append("Positive labels may be biased by ID patterns")

        passed = len(artifacts) == 0

        return LabelValidationResult(
            check_name="Labeling Artifacts",
            passed=passed,
            value=len(artifacts),
            expected=0,
            details="; ".join(artifacts) if artifacts else "No artifacts detected",
        )

    @staticmethod
    def validate_complete_dataset(
        dataset_id: str,
        pairs: List[Dict[str, Any]],
        labels: List[int],
        pair_ids: List[str],
        inter_rater_labels: Dict[str, List[int]] | None = None,
    ) -> LabelValidationReport:
        """Perform complete validation of dataset labels.

        Args:
            dataset_id: Dataset identifier
            pairs: List of code pairs
            labels: List of binary labels
            pair_ids: List of pair identifiers
            inter_rater_labels: Optional dict of labels from multiple raters

        Returns:
            Complete validation report
        """
        results = []

        # Basic checks
        results.append(LabelValidator.check_duplicate_pairs(pair_ids))
        results.append(LabelValidator.check_pair_validity(pairs))
        results.append(LabelValidator.check_code_length_constraints(pairs))
        results.append(LabelValidator.check_language_consistency(pairs))
        results.append(LabelValidator.check_class_balance(labels))
        results.append(LabelValidator.detect_labeling_artifacts(labels, pair_ids))

        # Inter-rater agreement if available
        kappa = None
        if inter_rater_labels and len(inter_rater_labels) >= 2:
            rater_lists = list(inter_rater_labels.values())
            kappa = LabelValidator.calculate_cohens_kappa(rater_lists[0], rater_lists[1])

            kappa_result = LabelValidationResult(
                check_name="Inter-Rater Agreement (Cohen's Kappa)",
                passed=kappa >= LabelValidator.SILVER_KAPPA_THRESHOLD,
                value=kappa,
                expected=LabelValidator.SILVER_KAPPA_THRESHOLD,
                details=f"κ = {kappa:.3f}",
            )
            results.append(kappa_result)

        # Determine certification level
        all_passed = all(r.passed for r in results)
        if all_passed and kappa is not None:
            if kappa >= LabelValidator.GOLD_KAPPA_THRESHOLD:
                certification_level = "gold"
            elif kappa >= LabelValidator.SILVER_KAPPA_THRESHOLD:
                certification_level = "silver"
            else:
                certification_level = "bronze"
        elif all_passed:
            certification_level = "silver"
        else:
            certification_level = "bronze"

        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)

        summary = f"Label Validation: {passed_count}/{total_count} checks passed"
        if not all_passed:
            summary += " ⚠️ ISSUES DETECTED"

        return LabelValidationReport(
            dataset_id=dataset_id,
            results=results,
            all_passed=all_passed,
            certification_level=certification_level,
            summary=summary,
        )
