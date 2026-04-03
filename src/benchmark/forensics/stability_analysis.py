"""Stability Analysis for code similarity detection.

Provides threshold stability analysis and failure clustering for diagnostic benchmarking.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StabilityReport:
    """Threshold stability analysis report.
    
    Attributes:
        optimal_threshold: Optimal threshold for F1 score.
        optimal_f1: F1 score at optimal threshold.
        robustness_score: How robust the model is across thresholds (0.0 to 1.0).
        avg_sensitivity: Average sensitivity to threshold changes.
    """
    optimal_threshold: float = 0.5
    optimal_f1: float = 0.0
    robustness_score: float = 0.0
    avg_sensitivity: float = 0.0


@dataclass
class FailureCluster:
    """A cluster of similar failures.
    
    Attributes:
        cluster_id: Cluster identifier.
        size: Number of failures in cluster.
        dominant_pattern: Dominant failure pattern.
        recommended_fix: Recommended fix action.
    """
    cluster_id: str = ""
    size: int = 0
    dominant_pattern: str = ""
    recommended_fix: str = ""


@dataclass
class ClusterReport:
    """Failure clustering report.
    
    Attributes:
        num_clusters: Number of clusters found.
        total_failures: Total number of failures analyzed.
        attack_surfaces: Summary of attack surfaces (pattern -> count).
        clusters: List of failure clusters.
    """
    num_clusters: int = 0
    total_failures: int = 0
    attack_surfaces: Dict[str, int] = field(default_factory=dict)
    clusters: List[FailureCluster] = field(default_factory=list)


class ThresholdStabilityAnalyzer:
    """Analyzes threshold stability for similarity detection.
    
    Tests how sensitive the model is to threshold changes and finds optimal threshold.
    """
    
    def __init__(self, results: List[Tuple[float, int, int, str, str]]):
        """Initialize analyzer with benchmark results.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
        """
        self.results = results
    
    def analyze(
        self,
        min_threshold: float = 0.0,
        max_threshold: float = 1.0,
        step: float = 0.05,
    ) -> StabilityReport:
        """Analyze threshold stability.
        
        Args:
            min_threshold: Minimum threshold to test.
            max_threshold: Maximum threshold to test.
            step: Threshold step size.
            
        Returns:
            StabilityReport with analysis.
        """
        if not self.results:
            return StabilityReport()
        
        # Test thresholds
        threshold_scores = []
        thresholds = []
        
        threshold = min_threshold
        while threshold <= max_threshold:
            precision, recall, f1 = self._compute_metrics(threshold)
            threshold_scores.append((threshold, precision, recall, f1))
            thresholds.append(threshold)
            threshold += step
        
        # Find optimal threshold (max F1)
        optimal_idx = max(range(len(threshold_scores)), key=lambda i: threshold_scores[i][3])
        optimal_threshold, optimal_precision, optimal_recall, optimal_f1 = threshold_scores[optimal_idx]
        
        # Compute robustness: how stable is F1 around optimal threshold
        f1_scores = [score[3] for score in threshold_scores]
        f1_mean = sum(f1_scores) / len(f1_scores)
        f1_variance = sum((f - f1_mean) ** 2 for f in f1_scores) / len(f1_scores)
        robustness = 1.0 / (1.0 + f1_variance)  # Higher variance = lower robustness
        
        # Compute sensitivity: average change in F1 per threshold step
        f1_changes = []
        for i in range(1, len(f1_scores)):
            f1_changes.append(abs(f1_scores[i] - f1_scores[i - 1]))
        avg_sensitivity = sum(f1_changes) / len(f1_changes) if f1_changes else 0.0
        
        return StabilityReport(
            optimal_threshold=optimal_threshold,
            optimal_f1=optimal_f1,
            robustness_score=robustness,
            avg_sensitivity=avg_sensitivity,
        )
    
    def _compute_metrics(self, threshold: float) -> Tuple[float, float, float]:
        """Compute precision, recall, F1 at given threshold.
        
        Args:
            threshold: Decision threshold.
            
        Returns:
            Tuple of (precision, recall, f1).
        """
        tp = fp = tn = fn = 0
        
        for score, label, _, _, _ in self.results:
            predicted = 1 if score >= threshold else 0
            
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 0:
                tn += 1
            else:  # predicted == 0 and label == 1
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return precision, recall, f1


class FailureClusterAnalyzer:
    """Clusters similar failures for diagnostic analysis.
    
    Groups failures by pattern to identify common attack surfaces.
    """
    
    # Known failure patterns
    PATTERNS = {
        "rename_heavy": "Variable/method rename not detected",
        "restructure_heavy": "Code reordered/statement restructuring",
        "semantic_equivalent": "Same logic, different implementation",
        "partial_overlap": "Partial code match with inserted logic",
        "api_substitution": "Different API calls achieving same effect",
        "template_similarity": "Both codes use same template/boilerplate",
    }
    
    def __init__(self, results: List[Tuple[float, int, int, str, str]]):
        """Initialize analyzer with benchmark results.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
        """
        self.results = results
    
    def cluster(
        self,
        threshold: float = 0.5,
    ) -> ClusterReport:
        """Cluster failures by pattern.
        
        Args:
            threshold: Decision threshold.
            
        Returns:
            ClusterReport with failure clusters.
        """
        # Identify failures
        failures = []
        for i, (score, label, clone_type, code_a, code_b) in enumerate(self.results):
            predicted = 1 if score >= threshold else 0
            if predicted != label:
                failures.append({
                    "index": i,
                    "score": score,
                    "label": label,
                    "clone_type": clone_type,
                    "predicted": predicted,
                    "is_fn": label == 1,
                })
        
        if not failures:
            return ClusterReport(num_clusters=0, total_failures=0)
        
        # Cluster failures by pattern
        pattern_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for failure in failures:
            pattern = self._classify_failure(failure)
            pattern_groups[pattern].append(failure)
        
        # Build clusters
        clusters = []
        attack_surfaces = {}
        
        for pattern, pattern_failures in sorted(
            pattern_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True
        ):
            if not pattern_failures:
                continue
            
            description = self.PATTERNS.get(pattern, pattern)
            fix = self._get_fix(pattern)
            
            cluster = FailureCluster(
                cluster_id=pattern,
                size=len(pattern_failures),
                dominant_pattern=description,
                recommended_fix=fix,
            )
            
            clusters.append(cluster)
            attack_surfaces[pattern] = len(pattern_failures)
        
        return ClusterReport(
            num_clusters=len(clusters),
            total_failures=len(failures),
            attack_surfaces=attack_surfaces,
            clusters=clusters,
        )
    
    def _classify_failure(self, failure: Dict[str, Any]) -> str:
        """Classify a failure into a pattern.
        
        Args:
            failure: Failure details.
            
        Returns:
            Pattern name.
        """
        clone_type = failure.get("clone_type", 0)
        is_fn = failure.get("is_fn", False)
        score = failure.get("score", 0.5)
        
        if is_fn:
            # False negative
            if clone_type == 2:
                return "rename_heavy"
            elif clone_type == 3:
                return "restructure_heavy"
            elif clone_type == 4:
                return "semantic_equivalent"
            else:
                return "partial_overlap"
        else:
            # False positive
            if score > 0.7:
                return "template_similarity"
            else:
                return "partial_overlap"
    
    def _get_fix(self, pattern: str) -> str:
        """Get recommended fix for a pattern.
        
        Args:
            pattern: Pattern name.
            
        Returns:
            Recommended fix action.
        """
        fixes = {
            "rename_heavy": "Add identifier normalization (stemming, type-aware mapping)",
            "restructure_heavy": "Improve AST subtree matching and control flow analysis",
            "semantic_equivalent": "Add semantic embedding similarity (code2vec, CodeBERT)",
            "partial_overlap": "Implement sliding window matching or longest common subsequence",
            "api_substitution": "Add API semantic mapping or knowledge graph",
            "template_similarity": "Remove common boilerplate before comparison",
        }
        return fixes.get(pattern, "Investigate and improve")