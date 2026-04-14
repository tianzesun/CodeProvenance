"""Threshold Stability Analysis and Failure Clustering.

Two critical upgrades for diagnostic intelligence:

1. Threshold Stability Analysis
   - F1 stability across threshold range
   - Precision-recall stability
   - Identifies threshold sensitivity (fragile vs robust model)

2. Failure Clustering Engine
   - Groups similar failure patterns
   - Identifies "attack surfaces" of the detector
   - Provides targeted improvement directions

Usage:
    from benchmark.analysis.stability_analysis import (
        ThresholdStabilityAnalyzer,
        FailureClusterAnalyzer
    )
    
    # Threshold stability
    stability = ThresholdStabilityAnalyzer(results).analyze()
    print(stability.summary())
    
    # Failure clustering
    clusters = FailureClusterAnalyzer(results, embeddings).cluster()
    print(clusters.summary())
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class ThresholdStabilityReport:
    """Report on threshold stability analysis."""
    optimal_threshold: float = 0.5
    optimal_f1: float = 0.0
    
    # Stability metrics
    f1_max: float = 0.0
    f1_min: float = 0.0
    f1_range: float = 0.0
    f1_std: float = 0.0
    f1_at_05: float = 0.0  # F1 at threshold=0.5
    
    # Robustness score: how stable is F1 across thresholds?
    # 1.0 = perfectly stable, 0.0 = completely unstable
    robustness_score: float = 0.0
    
    # Threshold sensitivity: how much F1 changes per 0.01 threshold change
    avg_sensitivity: float = 0.0
    
    # Working range: thresholds within 5% of optimal F1
    working_range: Tuple[float, float] = (0.0, 1.0)
    working_range_width: float = 0.0
    
    # Stability curve data (for plotting)
    f1_curve: List[Tuple[float, float]] = field(default_factory=list)
    precision_curve: List[Tuple[float, float]] = field(default_factory=list)
    recall_curve: List[Tuple[float, float]] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "THRESHOLD STABILITY ANALYSIS",
            "=" * 70,
            "",
            f"Optimal Threshold: {self.optimal_threshold:.2f}",
            f"Optimal F1 Score:  {self.optimal_f1:.4f}",
            "",
            "STABILITY METRICS:",
            f"  F1 Range:          [{self.f1_min:.4f}, {self.f1_max:.4f}]",
            f"  F1 Std Dev:        {self.f1_std:.4f}",
            f"  F1 at T=0.5:       {self.f1_at_05:.4f}",
            f"  Avg Sensitivity:   {self.avg_sensitivity:.4f} F1/unit",
            "",
            "ROBUSTNESS:",
            f"  Robustness Score:  {self.robustness_score:.4f}",
            f"  Working Range:     [{self.working_range[0]:.2f}, {self.working_range[1]:.2f}]",
            f"  Working Width:     {self.working_range_width:.2f}",
            "",
        ]
        
        # Interpret robustness
        if self.robustness_score >= 0.9:
            lines.append("  >>> Model is HIGHLY ROBUST - threshold choice is not critical")
        elif self.robustness_score >= 0.7:
            lines.append("  >>> Model is MODERATELY ROBUST - threshold choice matters somewhat")
        elif self.robustness_score >= 0.5:
            lines.append("  >>> Model is SENSITIVE - threshold choice is important")
        else:
            lines.append("  >>> Model is FRAGILE - small threshold changes cause large F1 swings")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)


@dataclass
class FailureCluster:
    """A cluster of similar failures."""
    cluster_id: int
    size: int
    avg_error: float
    
    # Cluster characteristics
    characteristics: Dict[str, Any] = field(default_factory=dict)
    
    # Sample failures
    sample_ids: List[str] = field(default_factory=list)
    
    # Dominant pattern
    dominant_pattern: str = ""
    
    # Recommended fix
    recommended_fix: str = ""


@dataclass
class FailureClusterReport:
    """Report on failure clustering analysis."""
    total_failures: int = 0
    num_clusters: int = 0
    
    clusters: List[FailureCluster] = field(default_factory=list)
    
    # Attack surface summary
    attack_surfaces: Dict[str, int] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "FAILURE CLUSTERING REPORT",
            "=" * 70,
            "",
            f"Total Failures Analyzed: {self.total_failures}",
            f"Failure Clusters Found:  {self.num_clusters}",
            "",
            "ATTACK SURFACES:",
        ]
        
        for surface, count in sorted(
            self.attack_surfaces.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"  {surface}: {count} failures")
        
        if self.clusters:
            lines.append("")
            lines.append("CLUSTER DETAILS:")
            for i, cluster in enumerate(self.clusters[:5], 1):
                lines.append(
                    f"  {i}. Cluster {cluster.cluster_id}: {cluster.size} failures "
                    f"(avg error: {cluster.avg_error:.3f})"
                )
                lines.append(f"     Pattern: {cluster.dominant_pattern}")
                if cluster.recommended_fix:
                    lines.append(f"     Fix: {cluster.recommended_fix}")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)


class ThresholdStabilityAnalyzer:
    """Analyzes threshold stability of similarity detector.
    
    Determines if the model's F1 is stable across threshold choices
    or critically dependent on a specific threshold value.
    
    Usage:
        analyzer = ThresholdStabilityAnalyzer(results)
        report = analyzer.analyze()
        print(report.summary())
    """
    
    def __init__(
        self,
        results: List[Tuple[float, int, int, str, str]],
    ):
        """Initialize stability analyzer.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
        """
        self.results = results
    
    def analyze(
        self,
        threshold_range: Tuple[float, float] = (0.0, 1.0),
        num_steps: int = 100,
    ) -> ThresholdStabilityReport:
        """Run threshold stability analysis.
        
        Args:
            threshold_range: Range of thresholds to test (start, end).
            num_steps: Number of threshold values to test.
            
        Returns:
            ThresholdStabilityReport with analysis.
        """
        t_start, t_end = threshold_range
        step = (t_end - t_start) / num_steps
        
        f1_scores: List[float] = []
        precisions: List[float] = []
        recalls: List[float] = []
        thresholds: List[float] = []
        
        for i in range(num_steps + 1):
            t = t_start + i * step
            thresholds.append(t)
            
            tp = fp = tn = fn = 0
            for score, label, _, _, _ in self.results:
                predicted = 1 if score >= t else 0
                if predicted == 1 and label == 1:
                    tp += 1
                elif predicted == 1 and label == 0:
                    fp += 1
                elif predicted == 0 and label == 0:
                    tn += 1
                else:
                    fn += 1
            
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            
            f1_scores.append(f1)
            precisions.append(prec)
            recalls.append(rec)
        
        # Build report
        report = ThresholdStabilityReport()
        
        # Optimal threshold
        max_f1_idx = f1_scores.index(max(f1_scores))
        report.optimal_threshold = thresholds[max_f1_idx]
        report.optimal_f1 = f1_scores[max_f1_idx]
        
        # Stability metrics
        report.f1_max = max(f1_scores)
        report.f1_min = min(f1_scores)
        report.f1_range = report.f1_max - report.f1_min
        
        mean_f1 = sum(f1_scores) / len(f1_scores)
        report.f1_std = math.sqrt(
            sum((f - mean_f1) ** 2 for f in f1_scores) / len(f1_scores)
        )
        
        # F1 at threshold 0.5
        if 0.5 in thresholds:
            report.f1_at_05 = f1_scores[thresholds.index(0.5)]
        
        # Robustness score: normalized inverse of F1 standard deviation
        # Perfect robustness: all thresholds give same F1
        max_possible_std = report.f1_max / 2  # theoretical maximum
        report.robustness_score = max(
            0.0,
            1.0 - (report.f1_std / max_possible_std) if max_possible_std > 0 else 1.0
        )
        
        # Average sensitivity: how much F1 changes per unit threshold change
        sensitivities = []
        for i in range(1, len(f1_scores)):
            dt = thresholds[i] - thresholds[i - 1]
            if dt > 0:
                sensitivities.append(abs(f1_scores[i] - f1_scores[i - 1]) / dt)
        report.avg_sensitivity = (
            sum(sensitivities) / len(sensitivities) if sensitivities else 0.0
        )
        
        # Working range: thresholds where F1 >= 95% of optimal
        f1_threshold = 0.95 * report.optimal_f1
        working_starts = []
        working_ends = []
        in_working = False
        
        for t, f1 in zip(thresholds, f1_scores):
            if f1 >= f1_threshold:
                if not in_working:
                    working_starts.append(t)
                    in_working = True
            else:
                if in_working:
                    working_ends.append(t)
                    in_working = False
        
        if working_starts:
            report.working_range = (working_starts[0], working_ends[-1] if working_ends else 1.0)
            report.working_range_width = report.working_range[1] - report.working_range[0]
        
        # Curves for plotting
        report.f1_curve = list(zip(thresholds, f1_scores))
        report.precision_curve = list(zip(thresholds, precisions))
        report.recall_curve = list(zip(thresholds, recalls))
        
        return report


class FailureClusterAnalyzer:
    """Clusters failures into groups with similar patterns.
    
    Identifies "attack surfaces" of the detector - groups of
    failures that share common characteristics and suggest
    specific code changes needed.
    
    Usage:
        analyzer = FailureClusterAnalyzer(results, component_scores)
        report = analyzer.cluster()
        print(report.summary())
    """
    
    # Known failure patterns with their fix recommendations
    FAILURE_PATTERNS = {
        "rename_heavy": {
            "description": "Variable/method rename not detected",
            "fix": "Add identifier normalization (stemming, type-aware mapping)",
            "characteristics": {"token": "low", "structure": "medium_to_high"},
        },
        "restructure_heavy": {
            "description": "Code reordered/statement restructuring",
            "fix": "Improve AST subtree matching and control flow analysis",
            "characteristics": {"token": "medium", "structure": "medium"},
        },
        "semantic_equivalent": {
            "description": "Same logic, completely different implementation",
            "fix": "Add semantic embedding similarity (code2vec, CodeBERT)",
            "characteristics": {"token": "low", "structure": "low"},
        },
        "partial_overlap": {
            "description": "Partial code match with inserted different logic",
            "fix": "Implement sliding window matching or longest common subsequence",
            "characteristics": {"token": "medium", "structure": "low_to_medium"},
        },
        "api_substitution": {
            "description": "Different API calls achieving same effect",
            "fix": "Add API semantic mapping or knowledge graph",
            "characteristics": {"token": "low", "structure": "medium"},
        },
        "template_similarity": {
            "description": "Both codes use same template/boilerplate",
            "fix": "Remove common boilerplate before comparison",
            "characteristics": {"token": "medium", "structure": "high"},
        },
    }
    
    def __init__(
        self,
        results: List[Tuple[float, int, int, str, str]],
        component_scores: List[Dict[str, float]] = None,
    ):
        """Initialize failure cluster analyzer.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
            component_scores: List of component score dicts per pair.
        """
        self.results = results
        self.component_scores = component_scores or []
    
    def cluster(
        self,
        threshold: float = 0.5,
    ) -> FailureClusterReport:
        """Run failure clustering.
        
        Args:
            threshold: Decision threshold.
            
        Returns:
            FailureClusterReport with clusters.
        """
        # Identify failures (FP and FN)
        failures: List[Dict[str, Any]] = []
        for i, (score, label, clone_type, code_a, code_b) in enumerate(self.results):
            predicted = 1 if score >= threshold else 0
            if predicted != label:
                comp_scores = self.component_scores[i] if i < len(self.component_scores) else {}
                failures.append({
                    "index": i,
                    "score": score,
                    "label": label,
                    "clone_type": clone_type,
                    "predicted": predicted,
                    "error": score - label,
                    "component_scores": comp_scores,
                    "code_a": code_a,
                    "code_b": code_b,
                })
        
        if not failures:
            return FailureClusterReport(total_failures=0, num_clusters=0)
        
        # Classify each failure into a pattern
        cluster_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for failure in failures:
            pattern_name = self._classify_failure(failure)
            cluster_map[pattern_name].append(failure)
        
        # Build clusters
        clusters: List[FailureCluster] = []
        attack_surfaces: Dict[str, int] = {}
        
        for pattern_name, pattern_failures in sorted(
            cluster_map.items(),
            key=lambda x: len(x[1]),
            reverse=True
        ):
            if not pattern_failures:
                continue
            
            pattern_info = self.FAILURE_PATTERNS.get(
                pattern_name,
                {
                    "description": pattern_name,
                    "fix": "Investigate and improve",
                }
            )
            
            avg_error = sum(f["error"] for f in pattern_failures) / len(pattern_failures)
            
            cluster = FailureCluster(
                cluster_id=len(clusters),
                size=len(pattern_failures),
                avg_error=avg_error,
                dominant_pattern=pattern_info.get("description", pattern_name),
                recommended_fix=pattern_info.get("fix", "Investigate and improve"),
                characteristics=pattern_info.get("characteristics", {}),
                sample_ids=[f"failure_{f['index']}" for f in pattern_failures[:5]],
            )
            
            clusters.append(cluster)
            attack_surfaces[pattern_name] = len(pattern_failures)
        
        return FailureClusterReport(
            total_failures=len(failures),
            num_clusters=len(clusters),
            clusters=clusters,
            attack_surfaces=attack_surfaces,
        )
    
    def _classify_failure(self, failure: Dict[str, Any]) -> str:
        """Classify a failure into a known pattern.
        
        Args:
            failure: Failure details with component scores.
            
        Returns:
            Pattern name identifier.
        """
        comp = failure.get("component_scores", {})
        clone_type = failure.get("clone_type", 0)
        is_fn = failure.get("label", 0) == 1  # False negative
        
        token_score = comp.get("token", 0.5)
        ast_score = comp.get("ast", 0.5)
        struct_score = comp.get("structure", 0.5)
        
        if is_fn:
            # False negative: components failed to score high enough
            if clone_type == 2 and token_score < 0.4:
                return "rename_heavy"
            elif clone_type == 3 and struct_score < 0.5:
                return "restructure_heavy"
            elif clone_type == 4 and token_score < 0.3 and ast_score < 0.3:
                return "semantic_equivalent"
            elif token_score < 0.5 and struct_score < 0.5:
                return "partial_overlap"
            elif ast_score < 0.4 and struct_score < 0.4:
                return "api_substitution"
            else:
                return "partial_overlap"
        else:
            # False positive: components scored too high for different code
            if token_score > 0.6 and ast_score > 0.6:
                return "template_similarity"
            elif token_score > 0.5:
                return "partial_overlap"
            else:
                return "rename_heavy"