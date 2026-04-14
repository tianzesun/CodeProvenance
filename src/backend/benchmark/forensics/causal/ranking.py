"""Causal Ranking Engine for similarity detection improvement.

Converts failure attribution into self-guided improvement ranking.

Takes root cause output and produces actionable optimization targets ranked
by expected impact on overall detection quality.

This module provides strategic intelligence for detector improvement by:
- Ranking improvement targets by expected causal impact
- Providing actionable recommendations
- Estimating confidence and implementation complexity

Usage:
    from src.backend.benchmark.forensics.causal.ranking import CausalRankingEngine

    engine = CausalRankingEngine(root_cause_report)
    ranking = engine.rank_improvements()
    print(ranking.summary())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImprovementCandidate:
    """A potential improvement with estimated impact.
    
    Attributes:
        target: Improvement target identifier.
        description: Human-readable description.
        estimated_impact: Expected F1 improvement (0.0 to 1.0).
        confidence: Confidence in the estimate (0.0 to 1.0).
        affected_failures: Number of failures this would address.
        affected_clone_types: List of clone types that would benefit.
        implementation_complexity: Complexity level (easy, medium, hard).
        recommended_action: Specific action to take.
    """
    target: str
    description: str
    estimated_impact: float  # 0.0 to 1.0, relative F1 improvement
    confidence: float  # How confident we are in the estimate
    affected_failures: int
    affected_clone_types: List[int] = field(default_factory=list)
    implementation_complexity: str = "medium"  # easy, medium, hard
    recommended_action: str = ""


@dataclass
class CausalRankingReport:
    """Ranked list of improvements.
    
    Attributes:
        candidates: List of improvement candidates ranked by impact.
        overall_priority_score: Aggregate priority score.
        system_health: Health assessment (healthy, needs_attention, critical).
    """
    candidates: List[ImprovementCandidate] = field(default_factory=list)
    overall_priority_score: float = 0.0
    system_health: str = ""  # "healthy", "needs_attention", "critical"
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "CAUSAL RANKING REPORT",
            "=" * 70,
            "",
            f"System Health: {self.system_health}",
            f"Overall Priority Score: {self.overall_priority_score:.4f}",
            f"Improvement Candidates: {len(self.candidates)}",
            "",
            "RANKED IMPROVEMENT TARGETS:",
        ]
        
        for i, cand in enumerate(self.candidates[:5], 1):
            lines.append(
                f"  {i}. [{cand.target}] (impact: {cand.estimated_impact:.2f}, "
                f"confidence: {cand.confidence:.2f})"
            )
            lines.append(f"     Description: {cand.description}")
            lines.append(f"     Affected failures: {cand.affected_failures}")
            if cand.recommended_action:
                lines.append(f"     Action: {cand.recommended_action}")
            lines.append("")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "system_health": self.system_health,
            "overall_priority_score": self.overall_priority_score,
            "candidate_count": len(self.candidates),
            "candidates": [
                {
                    "target": c.target,
                    "description": c.description,
                    "estimated_impact": c.estimated_impact,
                    "confidence": c.confidence,
                    "affected_failures": c.affected_failures,
                    "implementation_complexity": c.implementation_complexity,
                    "recommended_action": c.recommended_action,
                }
                for c in self.candidates
            ],
        }


class CausalRankingEngine:
    """Ranks improvement targets by expected causal impact.
    
    Converts root cause data into a prioritized improvement roadmap.
    
    Known improvement patterns with impact estimates:
    - identifier_normalization: Handle renamed identifiers (Type-2 clones)
    - loop_normalization: Normalize control flow patterns (Type-3 clones)
    - semantic_embedding: ML-based semantic similarity (Type-4 clones)
    - ast_subtree_matching: Improve AST matching depth
    - token_weighting: Improve token importance weighting
    - threshold_calibration: Optimize decision threshold
    - boilerplate_removal: Remove common templates
    - api_normalization: Normalize substitutable APIs
    
    Usage:
        causal = CausalRankingEngine(root_cause_report, stability_report, clustering_report)
        ranking = causal.rank_improvements()
        print(ranking.summary())
    """
    
    # Known improvement patterns with impact estimates
    KNOWN_IMPROVEMENTS = {
        "identifier_normalization": {
            "description": "Add canonical identifier renaming (v_1, v_2, ...)",
            "target": "Type-2 clone detection",
            "trigger": "rename_heavy",
            "base_impact": 0.30,
            "recommended_action": "Add identifier normalization in canonicalization layer",
            "complexity": "easy",
        },
        "loop_normalization": {
            "description": "Normalize for/while loop patterns to common form",
            "target": "Type-3 clone detection",
            "trigger": "restructure_heavy",
            "base_impact": 0.15,
            "recommended_action": "Add control-flow normalization to canonicalizer",
            "complexity": "medium",
        },
        "semantic_embedding": {
            "description": "Add semantic embedding similarity (CodeBERT/UniXcoder)",
            "target": "Type-4 clone detection",
            "trigger": "semantic_equivalent",
            "base_impact": 0.40,
            "recommended_action": "Integrate ML-based embedding model into pipeline",
            "complexity": "hard",
        },
        "ast_subtree_matching": {
            "description": "Improve AST subtree matching depth and granularity",
            "target": "Structural similarity",
            "trigger": "ast_loss",
            "base_impact": 0.10,
            "recommended_action": "Increase max_depth parameter, add node type weighting",
            "complexity": "medium",
        },
        "token_weighting": {
            "description": "Improve token weighting (keyword vs identifier importance)",
            "target": "Token-based discrimination",
            "trigger": "token_loss",
            "base_impact": 0.20,
            "recommended_action": "Add TF-IDF weighting or keyword boost to token engine",
            "complexity": "medium",
        },
        "threshold_calibration": {
            "description": "Recalibrate decision threshold for optimal F1",
            "target": "Decision boundary",
            "trigger": "threshold_instability",
            "base_impact": 0.05,
            "recommended_action": "Use validation set to find optimal operating point",
            "complexity": "easy",
        },
        "boilerplate_removal": {
            "description": "Remove common boilerplate/template code",
            "target": "False positive reduction",
            "trigger": "template_similarity",
            "base_impact": 0.25,
            "recommended_action": "Add template detection and boilerplate stripping",
            "complexity": "medium",
        },
        "api_normalization": {
            "description": "Normalize substitutable API calls (map/for/filter)",
            "target": "API equivalence detection",
            "trigger": "api_substitution",
            "base_impact": 0.15,
            "recommended_action": "Build API substitution groups and normalize before comparison",
            "complexity": "hard",
        },
    }
    
    def __init__(
        self,
        root_cause_report: Any = None,
        stability_report: Any = None,
        clustering_report: Any = None,
    ):
        """Initialize causal ranking engine.
        
        Args:
            root_cause_report: Root cause report from RootCauseAttributor.
            stability_report: Threshold stability report.
            clustering_report: Failure clustering report.
        """
        self.root_cause_report = root_cause_report
        self.stability_report = stability_report
        self.clustering_report = clustering_report
    
    def rank_improvements(self) -> CausalRankingReport:
        """Generate ranked list of improvement candidates.
        
        Returns:
            CausalRankingReport with prioritized improvements.
        """
        candidates: List[ImprovementCandidate] = []
        
        # 1. From root cause report: Component-based improvements
        if self.root_cause_report:
            candidates.extend(self._rank_from_root_causes())
        
        # 2. From clustering: Pattern-based improvements
        if self.clustering_report:
            candidates.extend(self._rank_from_clustering())
        
        # 3. From stability: Robustness-based improvements
        if self.stability_report:
            candidates.extend(self._rank_from_stability())
        
        # Deduplicate and combine
        combined = self._combine_duplicates(candidates)
        
        # Rank by priority score
        combined.sort(key=lambda c: c.estimated_impact * c.confidence, reverse=True)
        
        # Compute overall health
        if combined:
            top_impact = combined[0].estimated_impact if combined else 0
            if top_impact > 0.25:
                health = "needs_attention"
            elif top_impact > 0.10:
                health = "watch"
            else:
                health = "healthy"
        else:
            health = "healthy"
        
        overall_priority = (
            sum(c.estimated_impact * c.confidence for c in combined)
            if combined else 0.0
        )
        
        return CausalRankingReport(
            candidates=combined,
            overall_priority_score=overall_priority,
            system_health=health,
        )
    
    def _rank_from_root_causes(self) -> List[ImprovementCandidate]:
        """Generate candidates from root cause report.
        
        Returns:
            List of improvement candidates.
        """
        candidates: List[ImprovementCandidate] = []
        
        if not self.root_cause_report:
            return candidates
        
        # Primary causes from root cause report
        causes = getattr(self.root_cause_report, 'primary_cause_distribution', {})
        total_failures = sum(causes.values()) if causes else 1
        
        for cause_name, count in causes.items():
            proportion = count / total_failures if total_failures > 0 else 0
            
            # Map cause to known improvement
            known = self._map_cause_to_improvement(cause_name)
            if known:
                candidates.append(ImprovementCandidate(
                    target=known["target"],
                    description=known["description"],
                    estimated_impact=known["base_impact"] * proportion,
                    confidence=0.8 if proportion > 0.3 else 0.5,
                    affected_failures=count,
                    recommended_action=known.get("recommended_action", ""),
                    implementation_complexity=known.get("complexity", "medium"),
                ))
        
        # Component effectiveness
        eff_map = getattr(self.root_cause_report, 'component_effectiveness', {})
        for comp_name, eff in eff_map.items():
            correlation = getattr(eff, 'correlation', 0.5)
            if correlation < 0.3:
                candidates.append(ImprovementCandidate(
                    target=f"{comp_name}_effectiveness",
                    description=f"Improve {comp_name} correlation with ground truth",
                    estimated_impact=0.10 * (1 - correlation),
                    confidence=0.6,
                    affected_failures=0,
                    recommended_action=f"Enhance {comp_name} feature extraction",
                    implementation_complexity="hard",
                ))
        
        return candidates
    
    def _rank_from_clustering(self) -> List[ImprovementCandidate]:
        """Generate candidates from failure clustering.
        
        Returns:
            List of improvement candidates.
        """
        candidates: List[ImprovementCandidate] = []
        
        if not self.clustering_report:
            return candidates
        
        attack_surfaces = getattr(self.clustering_report, 'attack_surfaces', {})
        total_failures = sum(attack_surfaces.values()) if attack_surfaces else 1
        
        for surface_name, count in attack_surfaces.items():
            proportion = count / total_failures if total_failures > 0 else 0
            
            known = self._map_cause_to_improvement(surface_name)
            if known:
                candidates.append(ImprovementCandidate(
                    target=known["target"],
                    description=known["description"],
                    estimated_impact=known["base_impact"] * proportion,
                    confidence=0.7 if proportion > 0.2 else 0.4,
                    affected_failures=count,
                    recommended_action=known.get("recommended_action", ""),
                    implementation_complexity=known.get("complexity", "medium"),
                ))
        
        # Cluster-specific recommendations
        clusters = getattr(self.clustering_report, 'clusters', [])
        for cluster in clusters:
            if getattr(cluster, 'recommended_fix', '') and getattr(cluster, 'size', 0) > 5:
                pattern = getattr(cluster, 'dominant_pattern', '')
                trigger = self._pattern_to_trigger(pattern)
                known = self._map_cause_to_improvement(trigger)
                if known:
                    candidates.append(ImprovementCandidate(
                        target=known["target"],
                        description=cluster.recommended_fix,
                        estimated_impact=known["base_impact"] * 0.5,
                        confidence=0.5,
                        affected_failures=cluster.size,
                        recommended_action=cluster.recommended_fix,
                        implementation_complexity=known.get("complexity", "medium"),
                    ))
        
        return candidates
    
    def _rank_from_stability(self) -> List[ImprovementCandidate]:
        """Generate candidates from stability analysis.
        
        Returns:
            List of improvement candidates.
        """
        candidates: List[ImprovementCandidate] = []
        
        if not self.stability_report:
            return candidates
        
        robustness = getattr(self.stability_report, 'robustness_score', 1.0)
        if robustness < 0.7:
            candidates.append(ImprovementCandidate(
                target="threshold_stability",
                description="Improve model robustness across threshold range",
                estimated_impact=0.05 * (1 - robustness),
                confidence=0.6,
                recommended_action="Ensemble multiple thresholds or use learned threshold",
                implementation_complexity="easy",
            ))
        
        sensitivity = getattr(self.stability_report, 'avg_sensitivity', 0.0)
        if sensitivity > 1.0:
            candidates.append(ImprovementCandidate(
                target="sensitivity_reduction",
                description="Reduce threshold sensitivity",
                estimated_impact=0.03,
                confidence=0.4,
                recommended_action="Add score calibration layer",
                implementation_complexity="medium",
            ))
        
        return candidates
    
    def _combine_duplicates(
        self, candidates: List[ImprovementCandidate]
    ) -> List[ImprovementCandidate]:
        """Combine duplicate candidates for the same target.
        
        Args:
            candidates: List of candidates (may have duplicates).
            
        Returns:
            Combined list.
        """
        by_target: Dict[str, List[ImprovementCandidate]] = {}
        for c in candidates:
            by_target.setdefault(c.target, []).append(c)
        
        combined = []
        for target, cands in by_target.items():
            if len(cands) == 1:
                combined.append(cands[0])
            else:
                # Average impact, max confidence, sum failures
                avg_impact = sum(c.estimated_impact for c in cands) / len(cands)
                max_conf = max(c.confidence for c in cands)
                total_failures = sum(c.affected_failures for c in cands)
                
                combined.append(ImprovementCandidate(
                    target=target,
                    description=max(cands, key=lambda c: c.estimated_impact).description,
                    estimated_impact=avg_impact,
                    confidence=max_conf,
                    affected_failures=total_failures,
                    recommended_action=max(
                        cands, key=lambda c: c.estimated_impact
                    ).recommended_action,
                    implementation_complexity=min(
                        cands, key=lambda c: {"easy": 0, "medium": 1, "hard": 2}.get(c.implementation_complexity, 1)
                    ).implementation_complexity,
                ))
        
        return combined
    
    def _map_cause_to_improvement(
        self, cause_name: str
    ) -> Optional[Dict[str, Any]]:
        """Map failure cause name to known improvement pattern.
        
        Args:
            cause_name: Failure cause identifier.
            
        Returns:
            Known improvement pattern dict or None.
        """
        # Direct matches
        if cause_name in self.KNOWN_IMPROVEMENTS:
            return self.KNOWN_IMPROVEMENTS[cause_name]
        
        # Partial matches
        mapping = {
            "token_loss": "token_weighting",
            "ast_loss": "ast_subtree_matching",
            "structure_loss": "loop_normalization",
            "semantic_loss": "semantic_embedding",
            "rename_heavy": "identifier_normalization",
            "restructure_heavy": "loop_normalization",
            "semantic_equivalent": "semantic_embedding",
            "partial_overlap": "boilerplate_removal",
            "api_substitution": "api_normalization",
            "template_similarity": "boilerplate_removal",
        }
        
        for key, value in mapping.items():
            if key in cause_name.lower():
                return self.KNOWN_IMPROVEMENTS.get(value)
        
        return None
    
    def _pattern_to_trigger(self, pattern: str) -> str:
        """Convert failure pattern name to trigger name.
        
        Args:
            pattern: Pattern description string.
            
        Returns:
            Trigger name for known improvements.
        """
        pattern_lower = pattern.lower()
        if "rename" in pattern_lower:
            return "rename_heavy"
        elif "restructure" in pattern_lower or "reorder" in pattern_lower:
            return "restructure_heavy"
        elif "semantic" in pattern_lower:
            return "semantic_equivalent"
        elif "api" in pattern_lower:
            return "api_substitution"
        elif "template" in pattern_lower or "boilerplate" in pattern_lower:
            return "template_similarity"
        elif "partial" in pattern_lower or "overlap" in pattern_lower:
            return "partial_overlap"
        return "token_loss"