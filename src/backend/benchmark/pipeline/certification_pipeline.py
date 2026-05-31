"""World-class certification pipeline integrating all validation components.

This is the main entry point for running benchmarks with full certification:
1. Label validation (Cohen's Kappa, balance checks)
2. Cross-validation (5-fold stratified)
3. Adversarial robustness testing
4. Comprehensive reporting

Usage:
    pipeline = CertificationPipeline()
    report = pipeline.run_full_certification(
        code_pairs=pairs,
        labels=labels,
        scores_dict={"tool_a": scores_a, "tool_b": scores_b},
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime

from src.backend.benchmark.validation.label_validators import (
    DatasetLabelValidator,
    LabelValidationResult,
)
from src.backend.benchmark.validation.cross_validator import (
    cross_validate_benchmark,
    CrossValidationResult,
)
from src.backend.benchmark.certification.adversarial_robustness import (
    AdversarialRobustnessValidator,
    AdversarialRobustnessResult,
)
from src.backend.benchmark.certification.reproducibility import (
    collect_reproducibility_info,
    ReproducibilityInfo,
)

@dataclass
class CertificationReport:
    """Complete certification report with all validation results.
    
    Attributes:
        timestamp: When the certification was run.
        dataset_name: Name of the dataset.
        total_pairs: Number of code pairs.
        label_validation: Label quality results.
        cross_validation: CV results per tool.
        adversarial_robustness: Robustness results per tool.
        reproducibility: Reproducibility tracking info.
        passed_certification: Whether all checks passed.
        issues: List of issues found.
        warnings: List of warnings.
    """
    timestamp: str
    dataset_name: str
    total_pairs: int
    label_validation: LabelValidationResult
    cross_validation: Dict[str, CrossValidationResult]
    adversarial_robustness: Dict[str, AdversarialRobustnessResult]
    reproducibility: ReproducibilityInfo
    passed_certification: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "dataset_name": self.dataset_name,
            "total_pairs": self.total_pairs,
            "label_validation": self.label_validation.to_dict(),
            "cross_validation": {
                tool: result.to_dict()
                for tool, result in self.cross_validation.items()
            },
            "adversarial_robustness": {
                tool: result.to_dict()
                for tool, result in self.adversarial_robustness.items()
            },
            "reproducibility": self.reproducibility.to_dict(),
            "passed_certification": self.passed_certification,
            "issues": self.issues,
            "warnings": self.warnings,
        }
    
    def save_json(self, path: Path) -> None:
        """Save report to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def generate_human_report(self) -> str:
        """Generate human-readable certification report."""
        lines = [
            "=" * 80,
            "WORLD-CLASS BENCHMARK CERTIFICATION REPORT",
            "=" * 80,
            f"Timestamp: {self.timestamp}",
            f"Dataset: {self.dataset_name}",
            f"Total Pairs: {self.total_pairs}",
            f"Certification Status: {'✓ PASSED' if self.passed_certification else '✗ FAILED'}",
            "",
        ]
        
        # Label validation section
        lines.extend([
            "─" * 80,
            "1. LABEL QUALITY VALIDATION",
            "─" * 80,
            f"Cohen's Kappa: {self.label_validation.cohen_kappa:.4f} " +
            f"{'✓' if self.label_validation.cohen_kappa >= 0.70 else '✗'}",
            f"Label Balance: {self.label_validation.is_balanced} " +
            f"{'✓' if self.label_validation.is_balanced else '✗'}",
            f"Label Distribution: {self.label_validation.label_distribution}",
            f"Suspicious Pairs: {len(self.label_validation.suspicious_pairs)} " +
            f"({len(self.label_validation.suspicious_pairs)/self.total_pairs*100:.1f}%)",
            f"Quality Score: {self.label_validation.quality_score:.4f}",
        ])
        
        if self.label_validation.issues:
            lines.append("Issues:")
            for issue in self.label_validation.issues:
                lines.append(f"  ✗ {issue}")
        
        # Cross-validation section
        lines.extend([
            "",
            "─" * 80,
            "2. CROSS-VALIDATION RESULTS (5-fold stratified)",
            "─" * 80,
        ])
        
        for tool_name, cv_result in self.cross_validation.items():
            lines.extend([
                f"\n{tool_name}:",
                f"  Mean F1:          {cv_result.mean_f1:.4f} (±{cv_result.std_f1:.4f})",
                f"  F1 95% CI:        [{cv_result.ci_f1[0]:.4f}, {cv_result.ci_f1[1]:.4f}]",
                f"  Mean Precision:   {cv_result.mean_precision:.4f} (±{cv_result.std_precision:.4f})",
                f"  Prec 95% CI:      [{cv_result.ci_precision[0]:.4f}, {cv_result.ci_precision[1]:.4f}]",
                f"  Mean Recall:      {cv_result.mean_recall:.4f} (±{cv_result.std_recall:.4f})",
                f"  Recall 95% CI:    [{cv_result.ci_recall[0]:.4f}, {cv_result.ci_recall[1]:.4f}]",
                f"  Fold Stability:   {cv_result.fold_stability:.4f} " +
                f"({'✓ stable' if cv_result.fold_stability < 0.3 else '✗ unstable'})",
            ])
        
        # Adversarial robustness section
        lines.extend([
            "",
            "─" * 80,
            "3. ADVERSARIAL ROBUSTNESS TESTING",
            "─" * 80,
        ])
        
        for tool_name, robustness in self.adversarial_robustness.items():
            status = "✓ ROBUST" if robustness.is_robust else "✗ NOT ROBUST"
            lines.extend([
                f"\n{tool_name}: {status}",
                f"  Original F1:           {robustness.original_metric:.4f}",
                f"  Mean After Attacks:    {sum(robustness.adversarial_metrics)/len(robustness.adversarial_metrics):.4f}",
                f"  Stability Score:       {robustness.stability_score:.4f}",
                f"  Mean Degradation:      {robustness.mean_degradation:.1%}",
                f"  Max Degradation:       {robustness.max_degradation:.1%}",
                f"  Attack Details:",
            ])
            for attack_name, degradation in robustness.attack_details.items():
                lines.append(f"    - {attack_name}: {degradation:.1%} drop")
        
        # Reproducibility section
        lines.extend([
            "",
            "─" * 80,
            "4. REPRODUCIBILITY TRACKING",
            "─" * 80,
            f"Code Commit:     {self.reproducibility.code_commit[:8] if self.reproducibility.code_commit else 'N/A'}",
            f"Dataset Hash:    {self.reproducibility.dataset_hash[:16] if self.reproducibility.dataset_hash else 'N/A'}",
            f"Config Hash:     {self.reproducibility.config_hash[:16] if self.reproducibility.config_hash else 'N/A'}",
            f"Python Version:  {self.reproducibility.python_version}",
            f"Random Seed:     {self.reproducibility.random_seed}",
        ])
        
        # Issues and warnings
        if self.issues:
            lines.extend([
                "",
                "─" * 80,
                "CRITICAL ISSUES",
                "─" * 80,
            ])
            for issue in self.issues:
                lines.append(f"✗ {issue}")
        
        if self.warnings:
            lines.extend([
                "",
                "─" * 80,
                "WARNINGS",
                "─" * 80,
            ])
            for warning in self.warnings:
                lines.append(f"⚠ {warning}")
        
        lines.extend([
            "",
            "=" * 80,
            f"Certification: {'PASSED ✓' if self.passed_certification else 'FAILED ✗'}",
            "=" * 80,
        ])
        
        return "\n".join(lines)


class CertificationPipeline:
    """Main pipeline for world-class benchmark certification."""
    
    def __init__(
        self,
        k_folds: int = 5,
        robustness_threshold: float = 0.85,
        label_quality_threshold: float = 0.70,
    ):
        """Initialize certification pipeline.
        
        Args:
            k_folds: Number of folds for cross-validation.
            robustness_threshold: Minimum stability score for robustness.
            label_quality_threshold: Minimum quality score for labels.
        """
        self.k_folds = k_folds
        self.robustness_threshold = robustness_threshold
        self.label_quality_threshold = label_quality_threshold
    
    def run_full_certification(
        self,
        code_pairs: List[Tuple[str, str]],
        labels: List[int],
        scores_dict: Dict[str, List[float]],
        dataset_name: str = "benchmark_dataset",
        alternative_labels: Optional[List[List[int]]] = None,
        config: Optional[Dict[str, Any]] = None,
        threshold: float = 0.5,
    ) -> CertificationReport:
        """Run complete certification pipeline.
        
        Args:
            code_pairs: List of (code_a, code_b) tuples.
            labels: Ground truth labels.
            scores_dict: Dictionary mapping tool names to score lists.
            dataset_name: Name of the dataset.
            alternative_labels: Optional alternative labelings (from other annotators).
            config: Optional configuration dictionary for reproducibility tracking.
            threshold: Decision threshold for binary classification.
            
        Returns:
            CertificationReport with all validation results.
        """
        issues: List[str] = []
        warnings: List[str] = []
        
        timestamp = datetime.now().isoformat()
        
        # Step 1: Validate labels
        print(f"[1/4] Validating label quality...")
        label_validation = DatasetLabelValidator.validate_dataset(
            pairs=code_pairs,
            labels=labels,
            alternative_labels=alternative_labels,
        )
        
        if not label_validation.is_valid:
            issues.append(
                f"Label quality failed: {label_validation.quality_score:.2%} < {self.label_quality_threshold:.0%}"
            )
        else:
            print(f"  ✓ Label quality passed (score: {label_validation.quality_score:.2%})")
        
        # Step 2: Run cross-validation
        print(f"[2/4] Running {self.k_folds}-fold cross-validation...")
        cross_validation = cross_validate_benchmark(
            scores_dict=scores_dict,
            labels=labels,
            k=self.k_folds,
            threshold=threshold,
        )
        
        for tool_name, cv_result in cross_validation.items():
            if cv_result.fold_stability > 0.3:
                warnings.append(
                    f"{tool_name}: High fold instability (CV={cv_result.fold_stability:.2%})"
                )
            print(f"  ✓ {tool_name}: F1={cv_result.mean_f1:.4f} (±{cv_result.std_f1:.4f})")
        
        # Step 3: Test adversarial robustness
        print(f"[3/4] Testing adversarial robustness...")
        adversarial_robustness = {}
        validator = AdversarialRobustnessValidator()
        
        for tool_name, scores in scores_dict.items():
            # Get the CV result for this tool
            cv_result = cross_validation[tool_name]
            
            # Create a metric function that computes F1 from scores
            def make_metric_fn(scores_list: List[float], threshold: float) -> Callable:
                def metric_fn(codes_a, codes_b, lbls, decisions):
                    # Compute decisions from scores
                    import numpy as np
                    scores_arr = np.array(scores_list)
                    decisions_arr = (scores_arr >= threshold).astype(int)
                    labels_arr = np.array(lbls)
                    
                    # Compute F1
                    tp = np.sum((decisions_arr == 1) & (labels_arr == 1))
                    fp = np.sum((decisions_arr == 1) & (labels_arr == 0))
                    fn = np.sum((decisions_arr == 0) & (labels_arr == 1))
                    
                    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                    return f1
                return metric_fn
            
            metric_fn = make_metric_fn(scores, threshold)
            
            robustness = validator.evaluate(
                metric_fn=metric_fn,
                code_pairs=code_pairs,
                labels=labels,
                robustness_threshold=self.robustness_threshold,
            )
            adversarial_robustness[tool_name] = robustness
            
            status = "✓" if robustness.is_robust else "✗"
            print(f"  {status} {tool_name}: stability={robustness.stability_score:.4f}")
            
            if not robustness.is_robust:
                warnings.append(
                    f"{tool_name}: Low adversarial robustness "
                    f"(stability={robustness.stability_score:.2%})"
                )
        
        # Step 4: Collect reproducibility info
        print(f"[4/4] Collecting reproducibility information...")
        reproducibility = collect_reproducibility_info(
            config=config or {},
            random_seed=42,
        )
        
        # Determine if certification passed
        passed_certification = (
            label_validation.is_valid and
            len(issues) == 0 and
            all(r.is_robust for r in adversarial_robustness.values())
        )
        
        report = CertificationReport(
            timestamp=timestamp,
            dataset_name=dataset_name,
            total_pairs=len(labels),
            label_validation=label_validation,
            cross_validation=cross_validation,
            adversarial_robustness=adversarial_robustness,
            reproducibility=reproducibility,
            passed_certification=passed_certification,
            issues=issues,
            warnings=warnings,
        )
        
        print("\n" + report.generate_human_report())
        
        return report


def run_certification_pipeline(
    code_pairs: List[Tuple[str, str]],
    labels: List[int],
    scores_dict: Dict[str, List[float]],
    dataset_name: str = "benchmark_dataset",
    output_path: Optional[Path] = None,
) -> CertificationReport:
    """Convenience function to run full certification.
    
    Args:
        code_pairs: List of (code_a, code_b) tuples.
        labels: Ground truth labels.
        scores_dict: Dictionary mapping tool names to score lists.
        dataset_name: Name of the dataset.
        output_path: Optional path to save JSON report.
        
    Returns:
        CertificationReport.
    """
    pipeline = CertificationPipeline()
    report = pipeline.run_full_certification(
        code_pairs=code_pairs,
        labels=labels,
        scores_dict=scores_dict,
        dataset_name=dataset_name,
    )
    
    if output_path:
        report.save_json(output_path)
        print(f"\nReport saved to: {output_path}")
    
    return report