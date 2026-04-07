"""Failure Pattern Detection for code similarity detection.

Detects common failure patterns to provide strategic intelligence
for detector improvement.

Known failure patterns:
- rename_heavy: Variable/method rename not detected
- restructure_heavy: Code reordered/statement restructuring
- semantic_equivalent: Same logic, different implementation
- partial_overlap: Partial code match with inserted different logic
- api_substitution: Different API calls achieving same effect
- template_similarity: Both codes use same template/boilerplate

Usage:
    from src.benchmark.forensics.attribution.failure_patterns import FailurePatternDetector

    detector = FailurePatternDetector()
    report = detector.detect(results, component_scores)
    print(report.summary())
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FailurePattern:
    """A detected failure pattern.
    
    Attributes:
        pattern_id: Pattern identifier.
        description: Human-readable description.
        size: Number of failures in this pattern.
        avg_error: Average error magnitude.
        characteristics: Pattern characteristics.
        recommended_fix: Recommended fix action.
        sample_ids: Sample failure identifiers.
    """
    pattern_id: str
    description: str
    size: int = 0
    avg_error: float = 0.0
    characteristics: Dict[str, Any] = field(default_factory=dict)
    recommended_fix: str = ""
    sample_ids: List[str] = field(default_factory=list)


@dataclass
class FailurePatternReport:
    """Report on failure pattern detection.
    
    Attributes:
        total_failures: Total number of failures analyzed.
        num_patterns: Number of patterns detected.
        patterns: List of detected patterns.
        attack_surfaces: Summary of attack surfaces.
    """
    total_failures: int = 0
    num_patterns: int = 0
    patterns: List[FailurePattern] = field(default_factory=list)
    attack_surfaces: Dict[str, int] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "FAILURE PATTERN DETECTION REPORT",
            "=" * 70,
            "",
            f"Total Failures Analyzed: {self.total_failures}",
            f"Patterns Detected:       {self.num_patterns}",
            "",
            "ATTACK SURFACES:",
        ]
        
        for surface, count in sorted(
            self.attack_surfaces.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"  {surface}: {count} failures")
        
        if self.patterns:
            lines.append("")
            lines.append("PATTERN DETAILS:")
            for i, pattern in enumerate(self.patterns[:5], 1):
                lines.append(
                    f"  {i}. {pattern.pattern_id}: {pattern.size} failures "
                    f"(avg error: {pattern.avg_error:.3f})"
                )
                lines.append(f"     Description: {pattern.description}")
                if pattern.recommended_fix:
                    lines.append(f"     Fix: {pattern.recommended_fix}")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "total_failures": self.total_failures,
            "num_patterns": self.num_patterns,
            "attack_surfaces": self.attack_surfaces,
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "description": p.description,
                    "size": p.size,
                    "avg_error": p.avg_error,
                    "recommended_fix": p.recommended_fix,
                }
                for p in self.patterns
            ],
        }


class FailurePatternDetector:
    """Detects failure patterns in benchmark results.
    
    Known failure patterns with their characteristics and fixes:
    - rename_heavy: Variable/method rename not detected
      - Characteristics: token_low, structure_medium_to_high
      - Fix: Add identifier normalization
    
    - restructure_heavy: Code reordered/statement restructuring
      - Characteristics: token_medium, structure_medium
      - Fix: Improve AST subtree matching
    
    - semantic_equivalent: Same logic, completely different implementation
      - Characteristics: token_low, structure_low
      - Fix: Add semantic embedding similarity
    
    - partial_overlap: Partial code match with inserted different logic
      - Characteristics: token_medium, structure_low_to_medium
      - Fix: Implement sliding window matching
    
    - api_substitution: Different API calls achieving same effect
      - Characteristics: token_low, structure_medium
      - Fix: Add API semantic mapping
    
    - template_similarity: Both codes use same template/boilerplate
      - Characteristics: token_medium, structure_high
      - Fix: Remove common boilerplate
    
    Usage:
        detector = FailurePatternDetector()
        report = detector.detect(results, component_scores)
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
    
    def detect(
        self,
        results: List[Tuple[float, int, int, str, str]],
        component_scores: Optional[List[Dict[str, float]]] = None,
        threshold: float = 0.5,
    ) -> FailurePatternReport:
        """Detect failure patterns in benchmark results.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
            component_scores: List of component score dicts per pair.
            threshold: Decision threshold.
            
        Returns:
            FailurePatternReport with detected patterns.
        """
        # Identify failures (FP and FN)
        failures: List[Dict[str, Any]] = []
        for i, (score, label, clone_type, code_a, code_b) in enumerate(results):
            predicted = 1 if score >= threshold else 0
            if predicted != label:
                comp_scores = component_scores[i] if component_scores and i < len(component_scores) else {}
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
            return FailurePatternReport(total_failures=0, num_patterns=0)
        
        # Classify each failure into a pattern
        cluster_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for failure in failures:
            pattern_name = self._classify_failure(failure)
            cluster_map[pattern_name].append(failure)
        
        # Build patterns
        patterns: List[FailurePattern] = []
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
            
            pattern = FailurePattern(
                pattern_id=pattern_name,
                description=pattern_info.get("description", pattern_name),
                size=len(pattern_failures),
                avg_error=avg_error,
                characteristics=pattern_info.get("characteristics", {}),
                recommended_fix=pattern_info.get("fix", "Investigate and improve"),
                sample_ids=[f"failure_{f['index']}" for f in pattern_failures[:5]],
            )
            
            patterns.append(pattern)
            attack_surfaces[pattern_name] = len(pattern_failures)
        
        return FailurePatternReport(
            total_failures=len(failures),
            num_patterns=len(patterns),
            patterns=patterns,
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