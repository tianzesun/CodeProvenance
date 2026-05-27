"""Ground truth label validation for benchmark datasets.

Validates label quality and consistency before benchmarking.
Catches mislabeled pairs that could contaminate metrics.

Validation methods:
- Inter-rater agreement (Cohen's Kappa)
- Label consistency checks
- Outlier detection
- Distribution analysis
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

@dataclass(frozen=True)
class LabelValidationResult:
    """Result of label quality validation.
    
    Attributes:
        total_pairs: Total number of pairs evaluated.
        cohen_kappa: Inter-rater agreement (0-1, higher is better).
        label_distribution: Distribution of labels.
        is_balanced: Whether labels are reasonably balanced.
        suspicious_pairs: Indices of potentially mislabeled pairs.
        quality_score: Overall label quality (0-1).
        is_valid: Whether labels pass validation threshold (>0.70 kappa).
        issues: List of identified issues.
    """
    total_pairs: int
    cohen_kappa: float
    label_distribution: Dict[int, int]
    is_balanced: bool
    suspicious_pairs: List[int]
    quality_score: float
    is_valid: bool
    issues: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_pairs": self.total_pairs,
            "cohen_kappa": round(self.cohen_kappa, 4),
            "label_distribution": self.label_distribution,
            "is_balanced": self.is_balanced,
            "suspicious_pairs_count": len(self.suspicious_pairs),
            "suspicious_pairs": self.suspicious_pairs[:20],  # First 20
            "quality_score": round(self.quality_score, 4),
            "is_valid": self.is_valid,
            "issues": self.issues,
        }

class LabelValidator:
    """Validates ground truth labels."""
    
    def __init__(self, balance_threshold: float = 0.3):
        """Initialize validator.
        
        Args:
            balance_threshold: Minimum fraction of minority class (e.g., 0.3 = at least 30%).
        """
        self.balance_threshold = balance_threshold
    
    def validate(
        self,
        labels: List[int],
        rater1: Optional[List[int]] = None,
        rater2: Optional[List[int]] = None,
    ) -> LabelValidationResult:
        """Validate label quality.
        
        Args:
            labels: Primary labels.
            rater1: Optional second set of labels for agreement check.
            rater2: Optional third set of labels for agreement check.
            
        Returns:
            LabelValidationResult with quality metrics.
        """
        labels_arr = np.array(labels)
        issues: List[str] = []
        
        # Check label distribution
        unique, counts = np.unique(labels_arr, return_counts=True)
        label_dist = dict(zip(map(int, unique), map(int, counts)))
        
        # Check balance
        total = len(labels_arr)
        if total > 0:
            min_count = min(counts)
            min_fraction = min_count / total
            is_balanced = min_fraction >= self.balance_threshold
            
            if not is_balanced:
                issues.append(
                    f"Imbalanced labels: minority class is {min_fraction:.1%} "
                    f"(threshold: {self.balance_threshold:.1%})"
                )
        else:
            is_balanced = False
        
        # Compute inter-rater agreement if provided
        cohen_kappa = 0.0
        if rater1 is not None and rater2 is not None:
            cohen_kappa = self._compute_cohen_kappa(labels_arr, rater1, rater2)
            if cohen_kappa < 0.70:
                issues.append(
                    f"Low inter-rater agreement: Cohen's kappa = {cohen_kappa:.3f}"
                )
        
        # Detect suspicious/outlier pairs
        suspicious_pairs = self._detect_suspicious_pairs(labels_arr, rater1, rater2)
        if len(suspicious_pairs) > len(labels_arr) * 0.1:  # > 10% suspicious
            issues.append(
                f"{len(suspicious_pairs)} pairs ({len(suspicious_pairs)/len(labels_arr):.1%}) "
                f"flagged as potentially mislabeled"
            )
        
        # Overall quality score
        quality_score = self._compute_quality_score(
            is_balanced, cohen_kappa, len(suspicious_pairs) / max(1, len(labels_arr))
        )
        is_valid = quality_score >= 0.70
        
        return LabelValidationResult(
            total_pairs=len(labels_arr),
            cohen_kappa=cohen_kappa,
            label_distribution=label_dist,
            is_balanced=is_balanced,
            suspicious_pairs=suspicious_pairs,
            quality_score=quality_score,
            is_valid=is_valid,
            issues=issues,
        )
    
    def _compute_cohen_kappa(
        self,
        labels: np.ndarray,
        rater1: Optional[List[int]],
        rater2: Optional[List[int]],
    ) -> float:
        """Compute Cohen's kappa between three raters.
        
        Args:
            labels: Primary labels (reference).
            rater1: Second rater's labels.
            rater2: Third rater's labels.
            
        Returns:
            Cohen's kappa value (0-1).
        """
        if rater1 is None or rater2 is None:
            return 0.0
        
        rater1_arr = np.array(rater1)
        rater2_arr = np.array(rater2)
        
        if len(labels) != len(rater1_arr) or len(labels) != len(rater2_arr):
            return 0.0
        
        # Agreement between all three
        perfect_agreement = np.sum((labels == rater1_arr) & (labels == rater2_arr))
        two_agree = (
            np.sum((labels == rater1_arr) & (labels != rater2_arr)) +
            np.sum((labels != rater1_arr) & (labels == rater2_arr)) +
            np.sum((rater1_arr == rater2_arr) & (rater1_arr != labels))
        )
        
        # Observed agreement
        p_o = perfect_agreement / len(labels) if len(labels) > 0 else 0
        
        # Expected agreement (assuming random)
        unique_labels = np.unique(np.concatenate([labels, rater1_arr, rater2_arr]))
        p_e = 0.0
        for label in unique_labels:
            p_label = np.sum(labels == label) / len(labels)
            p_e += p_label ** 3
        
        # Cohen's kappa
        if p_e >= 1.0:
            kappa = 0.0
        else:
            kappa = (p_o - p_e) / (1 - p_e)
        
        return float(max(0.0, min(1.0, kappa)))
    
    @staticmethod
    def calculate_cohens_kappa(
        rater1: List[int],
        rater2: List[int],
    ) -> float:
        """Static method to calculate Cohen's kappa between two raters.
        
        Args:
            rater1: First rater's labels.
            rater2: Second rater's labels.
            
        Returns:
            Cohen's kappa value (0-1).
        """
        if len(rater1) != len(rater2):
            return 0.0
        
        rater1_arr = np.array(rater1)
        rater2_arr = np.array(rater2)
        labels = rater1_arr  # Use rater1 as reference
        
        # Observed agreement
        perfect_agreement = np.sum(rater1_arr == rater2_arr)
        p_o = perfect_agreement / len(rater1) if len(rater1) > 0 else 0
        
        # Expected agreement
        unique_labels = np.unique(np.concatenate([rater1_arr, rater2_arr]))
        p_e = 0.0
        for label in unique_labels:
            p_label1 = np.sum(rater1_arr == label) / len(rater1)
            p_label2 = np.sum(rater2_arr == label) / len(rater2)
            p_e += p_label1 * p_label2
        
        # Cohen's kappa
        if p_e >= 1.0:
            return 0.0
        kappa = (p_o - p_e) / (1 - p_e)
        return float(max(0.0, min(1.0, kappa)))
    
    @staticmethod
    def check_label_consistency(
        labels_by_pair: Dict[str, List[int]],
        tolerance: float = 0.0,
    ) -> Any:
        """Check label consistency across pairs.
        
        Args:
            labels_by_pair: Dictionary mapping pair IDs to label lists.
            tolerance: Minimum consistency required (0.0 to 1.0).
            
        Returns:
            ValidationResult-like object with passed and value attributes.
        """
        inconsistent = 0
        total = len(labels_by_pair)
        
        for pair_id, labels in labels_by_pair.items():
            if len(set(labels)) > 1:
                inconsistent += 1
        
        consistency = (total - inconsistent) / total if total > 0 else 1.0
        # tolerance is the minimum required consistency
        passed = consistency >= tolerance
        
        class ConsistencyResult:
            def __init__(self, passed: bool, value: float):
                self.passed = passed
                self.value = value
        
        return ConsistencyResult(passed, consistency)
    
    @staticmethod
    def check_class_balance(
        labels: List[int],
        min_minority_rate: float = 0.3,
    ) -> Any:
        """Check class balance in labels.
        
        Args:
            labels: List of labels.
            min_minority_rate: Minimum fraction for minority class.
            
        Returns:
            ValidationResult-like object with passed and value attributes.
        """
        unique, counts = np.unique(labels, return_counts=True)
        if len(counts) < 2:
            class BalanceResult:
                def __init__(self, passed: bool, value: float):
                    self.passed = passed
                    self.value = value
            return BalanceResult(False, 0.0)
        
        min_fraction = min(counts) / len(labels)
        passed = min_fraction >= min_minority_rate
        
        class BalanceResult:
            def __init__(self, passed: bool, value: float):
                self.passed = passed
                self.value = value
        
        return BalanceResult(passed, min_fraction)
    
    @staticmethod
    def check_duplicate_pairs(pair_ids: List[str]) -> Any:
        """Check for duplicate pair IDs.
        
        Args:
            pair_ids: List of pair identifiers.
            
        Returns:
            ValidationResult-like object with passed and value attributes.
        """
        unique_count = len(set(pair_ids))
        total_count = len(pair_ids)
        duplicates = total_count - unique_count
        
        class DuplicateResult:
            def __init__(self, passed: bool, value: int):
                self.passed = passed
                self.value = value
        
        return DuplicateResult(duplicates == 0, duplicates)
    
    def _detect_suspicious_pairs(
        self,
        labels: np.ndarray,
        rater1: Optional[List[int]] = None,
        rater2: Optional[List[int]] = None,
    ) -> List[int]:
        """Detect potentially mislabeled pairs.
        
        Args:
            labels: Primary labels.
            rater1: Optional alternative labels.
            rater2: Optional alternative labels.
            
        Returns:
            Indices of suspicious pairs.
        """
        suspicious: List[int] = []
        
        # Check for disagreement between raters
        if rater1 is not None and rater2 is not None:
            rater1_arr = np.array(rater1)
            rater2_arr = np.array(rater2)
            
            for i, (l, r1, r2) in enumerate(zip(labels, rater1_arr, rater2_arr)):
                # If all three disagree, flag as suspicious
                if l != r1 and l != r2 and r1 != r2:
                    suspicious.append(i)
                # If 2-out-of-3 agree but primary label disagrees
                elif (r1 == r2 and r1 != l):
                    suspicious.append(i)
        
        return suspicious
    
    def _compute_quality_score(
        self,
        is_balanced: bool,
        cohen_kappa: float,
        suspicious_fraction: float,
    ) -> float:
        """Compute overall label quality score.
        
        Args:
            is_balanced: Whether labels are balanced.
            cohen_kappa: Inter-rater agreement.
            suspicious_fraction: Fraction of suspicious pairs.
            
        Returns:
            Quality score (0-1).
        """
        # Balance contributes 20%
        balance_score = 1.0 if is_balanced else 0.5
        
        # Agreement contributes 60%
        agreement_score = cohen_kappa
        
        # Suspicion contributes 20%
        suspicion_score = max(0.0, 1.0 - suspicious_fraction * 2)
        
        overall = 0.2 * balance_score + 0.6 * agreement_score + 0.2 * suspicion_score
        
        return float(max(0.0, min(1.0, overall)))

@dataclass
class LabelValidationReport:
    """Complete report of label validation with certification level.
    
    Attributes:
        dataset_id: Identifier for the dataset.
        total_pairs: Total number of pairs validated.
        results: List of individual validation results.
        all_passed: Whether all validation checks passed.
        certification_level: Certification level (0-1).
        summary: Human-readable summary.
    """
    dataset_id: str
    total_pairs: int
    results: List[LabelValidationResult]
    all_passed: bool
    certification_level: float
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dataset_id": self.dataset_id,
            "total_pairs": self.total_pairs,
            "results": [r.to_dict() for r in self.results],
            "all_passed": self.all_passed,
            "certification_level": round(self.certification_level, 4),
            "summary": self.summary,
        }


class LabelValidatorWithComplete:
    """Extended LabelValidator with complete dataset validation."""
    
    @staticmethod
    def validate_complete_dataset(
        dataset_id: str,
        pairs: List[Dict[str, Any]],
        labels: List[int],
        pair_ids: List[str],
        inter_rater_labels: Optional[Dict[str, List[int]]] = None,
    ) -> LabelValidationReport:
        """Validate a complete dataset with all checks.
        
        Args:
            dataset_id: Dataset identifier.
            pairs: List of code pair dictionaries.
            labels: Binary labels for each pair.
            pair_ids: Pair identifiers.
            inter_rater_labels: Optional inter-rater labels by annotator.
            
        Returns:
            LabelValidationReport with all validation results.
        """
        results: List[LabelValidationResult] = []
        
        # Convert pairs to tuples
        code_pairs = [(p["code_a"], p["code_b"]) for p in pairs]
        
        # Get alternative labels
        alt_labels = None
        if inter_rater_labels:
            alt_labels = list(inter_rater_labels.values())
        
        # Run validation
        result = DatasetLabelValidator.validate_dataset(
            pairs=code_pairs,
            labels=labels,
            alternative_labels=alt_labels,
        )
        results.append(result)
        
        # Calculate certification level
        certification_level = result.quality_score
        
        # Determine if all passed
        all_passed = result.is_valid
        
        # Generate summary
        summary = DatasetLabelValidator.generate_validation_report(result)
        
        return LabelValidationReport(
            dataset_id=dataset_id,
            total_pairs=len(pairs),
            results=results,
            all_passed=all_passed,
            certification_level=certification_level,
            summary=summary,
        )


# Alias for convenience
LabelValidator.validate_complete_dataset = staticmethod(
    LabelValidatorWithComplete.validate_complete_dataset
)


class DatasetLabelValidator:
    """Validates labels for entire datasets."""
    
    @staticmethod
    def validate_dataset(
        pairs: List[Tuple[str, str]],
        labels: List[int],
        alternative_labels: Optional[List[List[int]]] = None,
    ) -> LabelValidationResult:
        """Validate labels for a dataset of code pairs.
        
        Args:
            pairs: List of (code_a, code_b) tuples.
            labels: Ground truth labels.
            alternative_labels: Optional alternative labelings (e.g., from different annotators).
            
        Returns:
            LabelValidationResult.
        """
        validator = LabelValidator()
        
        rater1 = alternative_labels[0] if alternative_labels and len(alternative_labels) > 0 else None
        rater2 = alternative_labels[1] if alternative_labels and len(alternative_labels) > 1 else None
        
        return validator.validate(labels, rater1, rater2)
    
    @staticmethod
    def generate_validation_report(
        result: LabelValidationResult,
        verbose: bool = False,
    ) -> str:
        """Generate human-readable validation report.
        
        Args:
            result: LabelValidationResult.
            verbose: Whether to include detailed information.
            
        Returns:
            Formatted report string.
        """
        lines = [
            "=" * 70,
            "LABEL QUALITY VALIDATION REPORT",
            "=" * 70,
            f"Total Pairs: {result.total_pairs}",
            f"Cohen's Kappa: {result.cohen_kappa:.4f} {'✓' if result.cohen_kappa >= 0.70 else '✗'}",
            f"Label Balance: {result.is_balanced} {'✓' if result.is_balanced else '✗'}",
            f"Label Distribution: {result.label_distribution}",
            f"Suspicious Pairs: {len(result.suspicious_pairs)} ({len(result.suspicious_pairs)/result.total_pairs*100:.1f}%)",
            f"Quality Score: {result.quality_score:.4f}",
            f"Valid for Benchmarking: {result.is_valid} {'✓' if result.is_valid else '✗'}",
        ]
        
        if result.issues:
            lines.append("")
            lines.append("ISSUES IDENTIFIED:")
            for issue in result.issues:
                lines.append(f"  • {issue}")
        
        if verbose and result.suspicious_pairs:
            lines.append("")
            lines.append("SUSPICIOUS PAIRS (first 20):")
            for idx in result.suspicious_pairs[:20]:
                lines.append(f"  • Pair #{idx}")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)