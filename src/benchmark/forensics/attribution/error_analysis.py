"""Error Analysis for code similarity detection.

Categorizes errors by type and characteristics to provide
strategic intelligence for detector improvement.

Error categories:
- False positives: Different code predicted as similar
- False negatives: Similar code predicted as different
- By clone type: Type-1/2/3/4 specific errors
- By score magnitude: High-confidence vs low-confidence errors

Usage:
    from benchmark.forensics.attribution.error_analysis import ErrorAnalyzer

    analyzer = ErrorAnalyzer()
    report = analyzer.analyze(results, threshold=0.5)
    print(report.summary())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ErrorCategory:
    """A category of errors with statistics.
    
    Attributes:
        name: Category name.
        count: Number of errors in this category.
        avg_score: Average similarity score for errors.
        avg_error: Average error magnitude.
        examples: Example error identifiers.
    """
    name: str
    count: int = 0
    avg_score: float = 0.0
    avg_error: float = 0.0
    examples: List[str] = field(default_factory=list)


@dataclass
class ErrorReport:
    """Complete error analysis report.
    
    Attributes:
        engine_name: Name of the engine analyzed.
        dataset_name: Name of the dataset.
        threshold: Decision threshold used.
        total_cases: Total number of cases.
        true_positives: Number of true positives.
        true_negatives: Number of true negatives.
        false_positives: Number of false positives.
        false_negatives: Number of false negatives.
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        errors_by_type: Errors grouped by clone type.
        errors_by_confidence: Errors grouped by confidence level.
        errors_by_characteristic: Errors grouped by characteristic.
        recommendations: Improvement recommendations.
    """
    engine_name: str
    dataset_name: str
    threshold: float
    total_cases: int = 0
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    
    # Error breakdown
    errors_by_type: Dict[str, ErrorCategory] = field(default_factory=dict)
    errors_by_confidence: Dict[str, ErrorCategory] = field(default_factory=dict)
    errors_by_characteristic: Dict[str, ErrorCategory] = field(default_factory=dict)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "ERROR ANALYSIS REPORT",
            f"Engine: {self.engine_name}",
            f"Dataset: {self.dataset_name}",
            f"Threshold: {self.threshold:.2f}",
            "=" * 70,
            "",
            "OVERALL METRICS:",
            f"  Total Cases: {self.total_cases}",
            f"  True Positives:  {self.true_positives}",
            f"  True Negatives:  {self.true_negatives}",
            f"  False Positives: {self.false_positives}",
            f"  False Negatives: {self.false_negatives}",
            f"  Precision:       {self.precision:.4f}",
            f"  Recall:          {self.recall:.4f}",
            f"  F1 Score:        {self.f1:.4f}",
            "",
        ]
        
        total_errors = self.false_positives + self.false_negatives
        if total_errors > 0:
            fp_pct = self.false_positives / total_errors * 100
            fn_pct = self.false_negatives / total_errors * 100
            lines.extend([
                "ERROR RATE BREAKDOWN:",
                f"  False Positives: {self.false_positives} ({fp_pct:.1f}%)",
                f"  False Negatives: {self.false_negatives} ({fn_pct:.1f}%)",
                "",
            ])
        else:
            lines.append("  No errors found!")
            lines.append("")
        
        if self.errors_by_type:
            lines.append("ERRORS BY CLONE TYPE:")
            for name, cat in self.errors_by_type.items():
                lines.append(
                    f"  {name}: {cat.count} cases (avg score: {cat.avg_score:.4f})"
                )
            lines.append("")
        
        if self.errors_by_confidence:
            lines.append("ERRORS BY CONFIDENCE LEVEL:")
            for name, cat in self.errors_by_confidence.items():
                lines.append(
                    f"  {name}: {cat.count} cases (avg error: {cat.avg_error:.4f})"
                )
            lines.append("")
        
        if self.errors_by_characteristic:
            lines.append("ERRORS BY CHARACTERISTIC:")
            for name, cat in self.errors_by_characteristic.items():
                lines.append(
                    f"  {name}: {cat.count} cases (avg score: {cat.avg_score:.4f})"
                )
            lines.append("")
        
        if self.recommendations:
            lines.append("RECOMMENDATIONS:")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "engine_name": self.engine_name,
            "dataset_name": self.dataset_name,
            "threshold": self.threshold,
            "total_cases": self.total_cases,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "errors_by_type": {
                name: {
                    "count": cat.count,
                    "avg_score": cat.avg_score,
                    "avg_error": cat.avg_error,
                }
                for name, cat in self.errors_by_type.items()
            },
            "errors_by_confidence": {
                name: {
                    "count": cat.count,
                    "avg_score": cat.avg_score,
                    "avg_error": cat.avg_error,
                }
                for name, cat in self.errors_by_confidence.items()
            },
        }


class ErrorAnalyzer:
    """Analyzes errors from benchmark results.
    
    Categorizes errors by:
    - False positives vs false negatives
    - Clone type (Type-1/2/3/4/Non-Clone)
    - Confidence level (high/medium/low)
    - Characteristic patterns
    
    Usage:
        analyzer = ErrorAnalyzer()
        report = analyzer.analyze(
            engine_name="hybrid_v1",
            dataset_name="synthetic_v1",
            results=results,
            threshold=0.5,
        )
        print(report.summary())
    """
    
    def analyze(
        self,
        engine_name: str,
        dataset_name: str,
        results: List[Tuple[float, int, int, str, str]],
        threshold: float = 0.5,
    ) -> ErrorReport:
        """Analyze errors from benchmark results.
        
        Args:
            engine_name: Name of the engine being analyzed.
            dataset_name: Name of the dataset.
            results: List of (score, label, clone_type, code_a, code_b).
            threshold: Decision threshold used.
            
        Returns:
            ErrorReport with analysis.
        """
        report = ErrorReport(
            engine_name=engine_name,
            dataset_name=dataset_name,
            threshold=threshold,
        )
        
        total = len(results)
        report.total_cases = total
        
        tp = fp = tn = fn = 0
        fp_cases: List[Tuple[float, int, int, str, str]] = []
        fn_cases: List[Tuple[float, int, int, str, str]] = []
        tp_by_type: Dict[int, int] = {}
        fp_by_type: Dict[int, int] = {}
        fn_by_type: Dict[int, int] = {}
        
        for i, (score, label, clone_type, code_a, code_b) in enumerate(results):
            predicted = 1 if score >= threshold else 0
            
            if predicted == 1 and label == 1:
                tp += 1
                tp_by_type[clone_type] = tp_by_type.get(clone_type, 0) + 1
            elif predicted == 0 and label == 0:
                tn += 1
            elif predicted == 1 and label == 0:
                fp += 1
                fp_cases.append((score, label, clone_type, code_a, code_b))
            else:  # predicted == 0 and label == 1
                fn += 1
                fn_by_type[clone_type] = fn_by_type.get(clone_type, 0) + 1
                fn_cases.append((score, label, clone_type, code_a, code_b))
        
        report.true_positives = tp
        report.true_negatives = tn
        report.false_positives = fp
        report.false_negatives = fn
        
        # Calculate metrics
        report.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        report.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        report.f1 = (
            2 * report.precision * report.recall
            / (report.precision + report.recall)
            if (report.precision + report.recall) > 0
            else 0.0
        )
        
        # Build error breakdown by clone type
        clone_type_names = {
            0: "non_clone",
            1: "type1_identical",
            2: "type2_renamed",
            3: "type3_restructured",
            4: "type4_semantic",
        }
        
        for ctype in range(5):
            fn_count = fn_by_type.get(ctype, 0)
            fp_count = fp_by_type.get(ctype, 0)
            if fn_count > 0 or fp_count > 0:
                type_name = clone_type_names.get(ctype, f"type_{ctype}")
                
                # Get scores for this type
                type_scores = [
                    score for score, label, ct, _, _ in results
                    if ct == ctype and ((label == 0 and score >= threshold) or (label == 1 and score < threshold))
                ]
                
                report.errors_by_type[type_name] = ErrorCategory(
                    name=type_name,
                    count=fn_count + fp_count,
                    avg_score=sum(type_scores) / len(type_scores) if type_scores else 0.0,
                    avg_error=sum(abs(s - threshold) for s in type_scores) / len(type_scores) if type_scores else 0.0,
                )
        
        # Build error breakdown by confidence level
        high_conf_errors = [
            (score, label, clone_type, code_a, code_b)
            for score, label, clone_type, code_a, code_b in fp_cases + fn_cases
            if abs(score - threshold) > 0.3
        ]
        medium_conf_errors = [
            (score, label, clone_type, code_a, code_b)
            for score, label, clone_type, code_a, code_b in fp_cases + fn_cases
            if 0.1 < abs(score - threshold) <= 0.3
        ]
        low_conf_errors = [
            (score, label, clone_type, code_a, code_b)
            for score, label, clone_type, code_a, code_b in fp_cases + fn_cases
            if abs(score - threshold) <= 0.1
        ]
        
        if high_conf_errors:
            report.errors_by_confidence["high_confidence"] = ErrorCategory(
                name="high_confidence",
                count=len(high_conf_errors),
                avg_error=sum(abs(score - threshold) for score, _, _, _, _ in high_conf_errors) / len(high_conf_errors),
            )
        
        if medium_conf_errors:
            report.errors_by_confidence["medium_confidence"] = ErrorCategory(
                name="medium_confidence",
                count=len(medium_conf_errors),
                avg_error=sum(abs(score - threshold) for score, _, _, _, _ in medium_conf_errors) / len(medium_conf_errors),
            )
        
        if low_conf_errors:
            report.errors_by_confidence["low_confidence"] = ErrorCategory(
                name="low_confidence",
                count=len(low_conf_errors),
                avg_error=sum(abs(score - threshold) for score, _, _, _, _ in low_conf_errors) / len(low_conf_errors),
            )
        
        # Build error breakdown by characteristic
        if fp_cases:
            fp_scores = [score for score, _, _, _, _ in fp_cases]
            report.errors_by_characteristic["structural_sim_no_clone"] = ErrorCategory(
                name="structural_sim_no_clone",
                count=len(fp_cases),
                avg_score=sum(fp_scores) / len(fp_scores) if fp_scores else 0.0,
            )
        
        if fn_cases:
            t2_fn = [case for case in fn_cases if case[2] == 2]
            t3_fn = [case for case in fn_cases if case[2] == 3]
            t4_fn = [case for case in fn_cases if case[2] == 4]
            
            if t2_fn:
                t2_scores = [score for score, _, _, _, _ in t2_fn]
                report.errors_by_characteristic["rename_not_detected"] = ErrorCategory(
                    name="rename_not_detected",
                    count=len(t2_fn),
                    avg_score=sum(t2_scores) / len(t2_scores) if t2_scores else 0.0,
                )
            
            if t3_fn:
                t3_scores = [score for score, _, _, _, _ in t3_fn]
                report.errors_by_characteristic["restructure_not_detected"] = ErrorCategory(
                    name="restructure_not_detected",
                    count=len(t3_fn),
                    avg_score=sum(t3_scores) / len(t3_scores) if t3_scores else 0.0,
                )
            
            if t4_fn:
                t4_scores = [score for score, _, _, _, _ in t4_fn]
                report.errors_by_characteristic["semantic_not_detected"] = ErrorCategory(
                    name="semantic_not_detected",
                    count=len(t4_fn),
                    avg_score=sum(t4_scores) / len(t4_scores) if t4_scores else 0.0,
                )
        
        report.recommendations = self._generate_recommendations(report)
        
        return report
    
    def _generate_recommendations(self, report: ErrorReport) -> List[str]:
        """Generate improvement recommendations based on analysis.
        
        Args:
            report: ErrorReport to analyze.
            
        Returns:
            List of recommendation strings.
        """
        recommendations: List[str] = []
        
        # Type-specific recommendations
        for name, cat in report.errors_by_characteristic.items():
            if "rename" in name and cat.count > 0:
                recommendations.append(
                    f"Improve rename handling: {cat.count} renamed clones missed. "
                    f"Consider adding identifier normalization before similarity comparison."
                )
            if "restructure" in name and cat.count > 0:
                recommendations.append(
                    f"Improve structure detection: {cat.count} restructured clones missed. "
                    f"Consider using AST subtree matching or control flow graph analysis."
                )
            if "semantic" in name and cat.count > 0:
                recommendations.append(
                    f"Improve semantic detection: {cat.count} semantic clones missed. "
                    f"Consider using ML-based embeddings or data flow analysis."
                )
        
        # General recommendations
        if report.false_positives > report.false_negatives:
            recommendations.append(
                f"High false positive rate ({report.false_positives}). "
                f"Consider raising the similarity threshold or adding stricter filtering."
            )
        elif report.false_negatives > report.false_positives:
            recommendations.append(
                f"High false negative rate ({report.false_negatives}). "
                f"Consider lowering the similarity threshold or adding more lenient matching."
            )
        
        # Engine-specific recommendations
        if report.engine_name.startswith("token"):
            recommendations.append(
                "Token-based engines struggle with renamed variables. "
                "Consider switching to hybrid or AST-based comparison."
            )
        elif report.engine_name.startswith("ast"):
            recommendations.append(
                "AST-based engines may miss non-structural similarities. "
                "Consider enriching with token-based features."
            )
        
        if not recommendations:
            recommendations.append(
                "No specific recommendations. The detector is performing well."
            )
        
        return recommendations