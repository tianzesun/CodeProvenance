"""Failure analysis for benchmark results.

Analyzes where the detector fails, categorizing failures by:
- False positives (different logic, similar structure)
- False negatives (same logic, different syntax)
- Clone type (T1-T4)
- Engine type (token, ast, hybrid)

This is the most important step in the iteration loop - it maps
failures back to specific engine weaknesses for targeted improvement.

Usage:
    from benchmark.analysis.failure_analysis import FailureAnalyzer

    analyzer = FailureAnalyzer()
    report = analyzer.analyze(results, ground_truth, dataset)
    print(report.summary())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class FailureCase:
    """A single failure case with details."""
    id: str
    code_a: str
    code_b: str
    true_label: int
    predicted_label: int
    score: float
    threshold: float
    clone_type: int  # 0=non-clone, 1-4=clone type
    engine_name: str = ""
    failure_mode: str = ""  # "false_positive" or "false_negative"
    category: str = ""  # Human-readable failure category


@dataclass
class FailureCategory:
    """Aggregated statistics for a failure category."""
    name: str
    count: int = 0
    avg_score: float = 0.0
    examples: List[str] = field(default_factory=list)


@dataclass
class FailureReport:
    """Complete failure analysis report."""
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
    
    # Failure breakdown by clone type
    failures_by_type: Dict[str, FailureCategory] = field(default_factory=dict)
    
    # Failure breakdown by characteristic
    failures_by_characteristic: Dict[str, FailureCategory] = field(default_factory=dict)
    
    # Detailed failure cases
    failure_cases: List[FailureCase] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            f"FAILURE ANALYSIS REPORT",
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
            "FAILURE RATE BREAKDOWN:",
        ]
        
        total_errors = self.false_positives + self.false_negatives
        if total_errors > 0:
            fp_pct = self.false_positives / total_errors * 100
            fn_pct = self.false_negatives / total_errors * 100
            lines.extend([
                f"  False Positives: {self.false_positives} ({fp_pct:.1f}%)",
                f"  False Negatives: {self.false_negatives} ({fn_pct:.1f}%)",
                "",
            ])
        else:
            lines.append("  No errors found!")
            lines.append("")
        
        if self.failures_by_type:
            lines.append("FAILURES BY CLONE TYPE:")
            for name, cat in self.failures_by_type.items():
                lines.append(
                    f"  {name}: {cat.count} cases (avg score: {cat.avg_score:.4f})"
                )
            lines.append("")
        
        if self.failures_by_characteristic:
            lines.append("FAILURES BY CHARACTERISTIC:")
            for name, cat in self.failures_by_characteristic.items():
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


class FailureAnalyzer:
    """Analyze benchmark failures to guide detector improvement.
    
    Usage:
        analyzer = FailureAnalyzer()
        report = analyzer.analyze(
            engine_name="hybrid_v1",
            dataset_name="synthetic_v1",
            results=results,  # List of (score, label, clone_type, code_a, code_b)
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
    ) -> FailureReport:
        """Analyze failures from benchmark results.
        
        Args:
            engine_name: Name of the engine being analyzed.
            dataset_name: Name of the dataset.
            results: List of (score, label, clone_type, code_a, code_b).
            threshold: Decision threshold used.
            
        Returns:
            FailureReport with analysis.
        """
        report = FailureReport(
            engine_name=engine_name,
            dataset_name=dataset_name,
            threshold=threshold,
        )
        
        total = len(results)
        report.total_cases = total
        
        tp = fp = tn = fn = 0
        failure_cases: List[FailureCase] = []
        tp_by_type: Dict[int, int] = {}
        fn_by_type: Dict[int, int] = {}
        fp_by_type: Dict[int, int] = {}
        
        for i, (score, label, clone_type, code_a, code_b) in enumerate(results):
            predicted = 1 if score >= threshold else 0
            
            if predicted == 1 and label == 1:
                tp += 1
                tp_by_type[clone_type] = tp_by_type.get(clone_type, 0) + 1
            elif predicted == 0 and label == 0:
                tn += 1
            elif predicted == 1 and label == 0:
                fp += 1
                fp_by_type[clone_type] = fp_by_type.get(clone_type, 0) + 1
                failure_cases.append(FailureCase(
                    id=f"case_{i:05d}",
                    code_a=code_a,
                    code_b=code_b,
                    true_label=label,
                    predicted_label=predicted,
                    score=score,
                    threshold=threshold,
                    clone_type=clone_type,
                    engine_name=engine_name,
                    failure_mode="false_positive",
                    category=self._classify_fp(score),
                ))
            else:  # predicted == 0 and label == 1
                fn += 1
                fn_by_type[clone_type] = fn_by_type.get(clone_type, 0) + 1
                failure_cases.append(FailureCase(
                    id=f"case_{i:05d}",
                    code_a=code_a,
                    code_b=code_b,
                    true_label=label,
                    predicted_label=predicted,
                    score=score,
                    threshold=threshold,
                    clone_type=clone_type,
                    engine_name=engine_name,
                    failure_mode="false_negative",
                    category=self._classify_fn(clone_type),
                ))
        
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
        
        # Build failure breakdown by clone type
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
                report.failures_by_type[type_name] = FailureCategory(
                    name=type_name,
                    count=fn_count + fp_count,
                    avg_score=0.0,  # Would need to compute from cases
                )
        
        # Build failure breakdown by characteristic
        fp_cases = [c for c in failure_cases if c.failure_mode == "false_positive"]
        fn_cases = [c for c in failure_cases if c.failure_mode == "false_negative"]
        
        if fp_cases:
            report.failures_by_characteristic["structural_sim_no_clone"] = (
                FailureCategory(
                    name="structural_sim_no_clone",
                    count=len(fp_cases),
                    avg_score=(
                        sum(c.score for c in fp_cases) / len(fp_cases)
                        if fp_cases else 0.0
                    ),
                )
            )
        
        if fn_cases:
            t2_fn = [c for c in fn_cases if c.clone_type == 2]
            t3_fn = [c for c in fn_cases if c.clone_type == 3]
            t4_fn = [c for c in fn_cases if c.clone_type == 4]
            
            if t2_fn:
                report.failures_by_characteristic["rename_not_detected"] = (
                    FailureCategory(
                        name="rename_not_detected",
                        count=len(t2_fn),
                        avg_score=(
                            sum(c.score for c in t2_fn) / len(t2_fn)
                            if t2_fn else 0.0
                        ),
                    )
                )
            if t3_fn:
                report.failures_by_characteristic["restructure_not_detected"] = (
                    FailureCategory(
                        name="restructure_not_detected",
                        count=len(t3_fn),
                        avg_score=(
                            sum(c.score for c in t3_fn) / len(t3_fn)
                            if t3_fn else 0.0
                        ),
                    )
                )
            if t4_fn:
                report.failures_by_characteristic["semantic_not_detected"] = (
                    FailureCategory(
                        name="semantic_not_detected",
                        count=len(t4_fn),
                        avg_score=(
                            sum(c.score for c in t4_fn) / len(t4_fn)
                            if t4_fn else 0.0
                        ),
                    )
                )
        
        report.failure_cases = failure_cases
        report.recommendations = self._generate_recommendations(report)
        
        return report
    
    def _classify_fp(self, score: float) -> str:
        """Classify false positive by score characteristics.
        
        Args:
            score: Similarity score.
            
        Returns:
            Classification string.
        """
        if score > 0.8:
            return "very_high_similarity_by_chance"
        elif score > 0.6:
            return "moderate_structural_overlap"
        else:
            return "minimal_overlap_false_alarm"
    
    def _classify_fn(self, clone_type: int) -> str:
        """Classify false negative by clone type.
        
        Args:
            clone_type: Clone type (1-4).
            
        Returns:
            Classification string.
        """
        classification = {
            1: "failed_identical_detection",
            2: "failed_rename_detection",
            3: "failed_restructure_detection",
            4: "failed_semantic_detection",
        }
        return classification.get(clone_type, "unknown_failure")
    
    def _generate_recommendations(self, report: FailureReport) -> List[str]:
        """Generate improvement recommendations based on analysis.
        
        Args:
            report: FailureReport to analyze.
            
        Returns:
            List of recommendation strings.
        """
        recommendations: List[str] = []
        
        # Type-specific recommendations
        for name, cat in report.failures_by_characteristic.items():
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


def failure_to_improvement_map(report: FailureReport) -> Dict[str, Any]:
    """Map failure patterns to specific engine improvement targets.
    
    This function translates failure analysis into concrete action items.
    
    Args:
        report: Failure report from analysis.
        
    Returns:
        Dictionary mapping improvement target to details.
    """
    improvements: Dict[str, Any] = {
        "engine": report.engine_name,
        "priority": "high" if report.f1 < 0.7 else (
            "medium" if report.f1 < 0.85 else "low"
        ),
        "targets": [],
    }
    
    # Map failure types to engine components
    failure_target_map = {
        "rename_not_detected": {
            "component": "normalizer",
            "action": "add_identifier_normalization",
        },
        "restructure_not_detected": {
            "component": "similarity/ast",
            "action": "improve_subtree_matching",
        },
        "semantic_not_detected": {
            "component": "similarity/semantic",
            "action": "add_embedding_similarity",
        },
        "structural_sim_no_clone": {
            "component": "normalizer",
            "action": "remove_common_patterns",
        },
    }
    
    for fail_name, cat in report.failures_by_characteristic.items():
        if cat.count > 0:
            target = failure_target_map.get(fail_name, {})
            if target:
                improvements["targets"].append({
                    **target,
                    "failure_count": cat.count,
                    "avg_score": cat.avg_score,
                })
    
    return improvements