"""Root Cause Attribution for code similarity detection.

Analyzes why detectors fail by attributing errors to specific components:
- Token-based failures
- AST-based failures
- Structure-based failures
- Semantic-based failures

Provides strategic intelligence for detector improvement by identifying
the primary causes of false positives and false negatives.

Usage:
    from src.backend.benchmark.forensics.causal.attribution import RootCauseAttributor

    attributor = RootCauseAttributor()
    report = attributor.analyze(pairs, engine)
    print(report.summary())
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class RootCause:
    """A single root cause attribution.
    
    Attributes:
        pair_id: Identifier for the code pair.
        ground_truth: Ground truth label (0.0 or 1.0).
        predicted_score: Predicted similarity score.
        error: Prediction error (predicted - ground_truth).
        primary_cause: Primary cause identifier.
        component_contributions: Per-component contribution to error.
        confidence: Confidence in attribution (0.0 to 1.0).
        clone_type: Clone type (0 for non-clone, 1-4 for clones).
    """
    pair_id: str
    ground_truth: float
    predicted_score: float
    error: float
    primary_cause: str
    component_contributions: Dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0
    clone_type: int = 0
    
    @property
    def is_false_positive(self) -> bool:
        """Check if this is a false positive."""
        return self.predicted_score >= 0.5 and self.ground_truth < 0.5
    
    @property
    def is_false_negative(self) -> bool:
        """Check if this is a false negative."""
        return self.predicted_score < 0.5 and self.ground_truth >= 0.5
    
    @property
    def error_magnitude(self) -> float:
        """Absolute error magnitude."""
        return abs(self.error)


@dataclass
class ComponentEffectiveness:
    """Effectiveness of a single component.
    
    Attributes:
        name: Component name.
        correlation: Correlation with ground truth.
        discrimination: AUC-like discrimination score.
        clone_type_sensitivity: Sensitivity per clone type.
    """
    name: str
    correlation: float = 0.0
    discrimination: float = 0.0
    clone_type_sensitivity: Dict[int, float] = field(default_factory=dict)


@dataclass
class RootCauseReport:
    """Aggregate root cause report.
    
    Attributes:
        total_pairs: Total number of pairs analyzed.
        false_positives: Number of false positives.
        false_negatives: Number of false negatives.
        true_positives: Number of true positives.
        true_negatives: Number of true negatives.
        component_losses: Per-component aggregate loss.
        primary_cause_distribution: Distribution of primary causes.
        component_effectiveness: Per-component effectiveness metrics.
        top_failures: Top failures by error magnitude.
        by_clone_type: Breakdown by clone type.
    """
    total_pairs: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_positives: int = 0
    true_negatives: int = 0
    
    # Per-component aggregate loss
    component_losses: Dict[str, float] = field(default_factory=dict)
    
    # Primary cause distribution
    primary_cause_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Per-component effectiveness
    component_effectiveness: Dict[str, ComponentEffectiveness] = field(default_factory=dict)
    
    # Top failure patterns
    top_failures: List[RootCause] = field(default_factory=list)
    
    # Per-clone-type breakdown
    by_clone_type: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "ROOT CAUSE ATTRIBUTION REPORT",
            "=" * 70,
            "",
            f"Total Pairs: {self.total_pairs}",
            f"  TP: {self.true_positives}  TN: {self.true_negatives}",
            f"  FP: {self.false_positives}  FN: {self.false_negatives}",
            "",
            "ERROR DECOMPOSITION:",
            "  Component losses (higher = more responsible for failure):",
        ]
        
        for comp, loss in sorted(
            self.component_losses.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"    {comp}: {loss:.4f}")
        
        lines.append("")
        lines.append("PRIMARY CAUSE DISTRIBUTION:")
        total_fp_fn = self.false_positives + self.false_negatives
        for cause, count in sorted(
            self.primary_cause_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            pct = count / total_fp_fn * 100 if total_fp_fn > 0 else 0
            lines.append(f"    {cause}: {count} ({pct:.1f}%)")
        
        lines.append("")
        lines.append("COMPONENT EFFECTIVENESS:")
        for comp, eff in self.component_effectiveness.items():
            lines.append(
                f"    {comp}: corr={eff.correlation:.3f}, "
                f"discrimination={eff.discrimination:.3f}"
            )
        
        if self.top_failures:
            lines.append("")
            lines.append("TOP 5 FAILURES:")
            for i, failure in enumerate(self.top_failures[:5], 1):
                lines.append(
                    f"  {i}. {failure.pair_id} (GT={failure.ground_truth:.0f}, "
                    f"pred={failure.predicted_score:.3f}, "
                    f"error={failure.error:.3f})"
                )
                lines.append(f"     Primary cause: {failure.primary_cause}")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "total_pairs": self.total_pairs,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "component_losses": self.component_losses,
            "primary_cause_distribution": self.primary_cause_distribution,
            "component_effectiveness": {
                name: {
                    "correlation": eff.correlation,
                    "discrimination": eff.discrimination,
                }
                for name, eff in self.component_effectiveness.items()
            },
        }


class RootCauseAttributor:
    """Root cause attribution for similarity detection.
    
    Decomposes similarity errors into component contributions:
    - Token-based loss
    - AST-based loss
    - Structure-based loss
    - Semantic-based loss
    
    This provides strategic intelligence for detector improvement by
    identifying WHY the detector fails on specific pairs.
    
    Usage:
        attributor = RootCauseAttributor()
        report = attributor.analyze(pairs, hybrid_engine)
        print(report.summary())
    """
    
    def __init__(
        self,
        component_engines: Optional[Dict[str, Callable[[str, str], float]]] = None,
        engine_weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the root cause attributor.
        
        Args:
            component_engines: Dict of component_name -> similarity_function.
                If None, uses default components (token, ast, structure).
            engine_weights: Dict of component_name -> weight.
                If None, uses equal weights.
        """
        self.component_engines = component_engines or self._default_components()
        self.engine_weights = engine_weights or {
            "token": 0.5,
            "ast": 0.3,
            "structure": 0.2,
        }
    
    def _default_components(
        self
    ) -> Dict[str, Callable[[str, str], float]]:
        """Create default component similarity functions.
        
        Returns:
            Dict of component name to similarity function.
        """
        from src.backend.benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine
        
        token_engine = TokenWinnowingEngine()
        ast_engine = ASTEngine()
        
        return {
            "token": token_engine.compare,
            "ast": ast_engine.compare,
            "structure": self._structural_similarity,
        }
    
    def _structural_similarity(self, code_a: str, code_b: str) -> float:
        """Compute structural similarity from raw code features.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score [0, 1].
        """
        import re
        
        def extract_features(code: str) -> Dict[str, float]:
            """Extract normalized structural features."""
            features: Dict[str, float] = {}
            
            # Control flow counts
            control_keywords = [
                'if', 'elif', 'else', 'for', 'while',
                'try', 'except', 'finally', 'with',
            ]
            total_keywords = 0
            for kw in control_keywords:
                count = len(re.findall(r'\b' + kw + r'\b', code))
                features[f"cf_{kw}"] = count
                total_keywords += count
            
            # Nesting depth (estimate from indentation)
            lines = code.split('\n')
            indent_levels = []
            for line in lines:
                stripped = line.lstrip()
                if stripped:
                    indent = len(line) - len(stripped)
                    indent_levels.append(indent)
            
            features["max_indent"] = max(indent_levels) if indent_levels else 0
            features["avg_indent"] = (
                sum(indent_levels) / len(indent_levels)
                if indent_levels else 0
            )
            
            # Function/method count
            features["func_count"] = len(re.findall(r'\bdef\b|\bfunction\b', code))
            
            # Loop types
            features["for_loops"] = len(re.findall(r'\bfor\b', code))
            features["while_loops"] = len(re.findall(r'\bwhile\b', code))
            
            # Normalize by code length
            code_len = len(code)
            if code_len > 0:
                for key in features:
                    features[key] = features[key] / max(code_len / 100, 1)
            
            return features
        
        feat_a = extract_features(code_a)
        feat_b = extract_features(code_b)
        
        all_keys = set(feat_a.keys()) | set(feat_b.keys())
        if not all_keys:
            return 0.0
        
        # Cosine similarity of feature vectors
        dot_product = sum(feat_a.get(k, 0) * feat_b.get(k, 0) for k in all_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in feat_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in feat_b.values()))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def analyze(
        self,
        pairs: List[Any],
        main_engine: Any = None,
        threshold: float = 0.5,
    ) -> RootCauseReport:
        """Run root cause analysis on all pairs.
        
        Args:
            pairs: List of pairs with code_a, code_b, label, clone_type attributes.
            main_engine: Main engine used for benchmark.
            threshold: Decision threshold.
            
        Returns:
            RootCauseReport with analysis.
        """
        report = RootCauseReport()
        report.total_pairs = len(pairs)
        
        all_attributions: List[RootCause] = []
        
        # Track component effectiveness
        component_gt: Dict[str, List[Tuple[float, float]]] = {
            comp: [] for comp in self.component_engines
        }
        
        for pair in pairs:
            # Get main engine prediction
            predicted = main_engine.compare(pair.code_a, pair.code_b) if main_engine else 0.0
            predicted = max(0.0, min(1.0, predicted))
            ground_truth = float(pair.label)
            error = predicted - ground_truth
            
            # Classify
            pred_label = 1 if predicted >= threshold else 0
            if pred_label == 1 and pair.label == 1:
                report.true_positives += 1
            elif pred_label == 0 and pair.label == 0:
                report.true_negatives += 1
            elif pred_label == 1 and pair.label == 0:
                report.false_positives += 1
            else:
                report.false_negatives += 1
            
            # Compute component scores
            component_scores: Dict[str, float] = {}
            for comp_name, comp_func in self.component_engines.items():
                try:
                    score = comp_func(pair.code_a, pair.code_b)
                    component_scores[comp_name] = max(0.0, min(1.0, score))
                except Exception:
                    component_scores[comp_name] = 0.0
                
                component_gt[comp_name].append((component_scores[comp_name], ground_truth))
            
            # Compute loss decomposition
            loss_contribution = self._decompose_loss(
                component_scores, error, ground_truth
            )
            
            # Create attribution
            attribution = RootCause(
                pair_id=getattr(pair, 'id', f"pair_{len(all_attributions)}"),
                ground_truth=ground_truth,
                predicted_score=predicted,
                error=error,
                primary_cause=self._find_primary_cause(loss_contribution, error),
                component_contributions=loss_contribution,
                confidence=self._compute_confidence(loss_contribution, error),
                clone_type=getattr(pair, 'clone_type', 0),
            )
            
            all_attributions.append(attribution)
        
        # Aggregate component losses
        total_error = sum(abs(a.error) for a in all_attributions if a.error != 0)
        if total_error > 0:
            for comp in self.component_engines:
                total_loss = sum(
                    a.component_contributions.get(comp, 0.0)
                    for a in all_attributions
                )
                report.component_losses[comp] = total_loss / total_error
        
        # Primary cause distribution
        for a in all_attributions:
            if a.error != 0:
                report.primary_cause_distribution[a.primary_cause] = (
                    report.primary_cause_distribution.get(a.primary_cause, 0) + 1
                )
        
        # Per-clone-type breakdown
        type_attributions: Dict[int, List[RootCause]] = {}
        for a in all_attributions:
            type_attributions.setdefault(a.clone_type, []).append(a)
        
        for clone_type, attributions in type_attributions.items():
            errors = [a.error for a in attributions]
            report.by_clone_type[clone_type] = {
                "count": len(attributions),
                "avg_error": sum(errors) / len(errors) if errors else 0.0,
                "primary_causes": {},
            }
            
            for a in attributions:
                report.by_clone_type[clone_type]["primary_causes"][a.primary_cause] = (
                    report.by_clone_type[clone_type]["primary_causes"].get(a.primary_cause, 0) + 1
                )
        
        # Component effectiveness
        for comp, scores in component_gt.items():
            if scores:
                report.component_effectiveness[comp] = self._compute_component_effectiveness(
                    comp, scores
                )
        
        # Top failures (by error magnitude)
        report.top_failures = sorted(
            [a for a in all_attributions if a.error != 0],
            key=lambda x: abs(x.error),
            reverse=True
        )[:5]
        
        return report
    
    def _decompose_loss(
        self,
        component_scores: Dict[str, float],
        error: float,
        ground_truth: float,
    ) -> Dict[str, float]:
        """Decompose similarity error into component contributions.
        
        Uses weighted component contribution to final score.
        
        Args:
            component_scores: Dict of component name to score.
            error: Total prediction error (predicted - ground_truth).
            ground_truth: Ground truth value (0 or 1).
            
        Returns:
            Dict of component name to loss contribution.
        """
        if error == 0:
            return {comp: 0.0 for comp in self.component_engines}
        
        total_weight = sum(
            self.engine_weights.get(c, 1.0)
            for c in self.component_engines
        )
        
        if total_weight == 0:
            return {comp: 0.0 for comp in self.component_engines}
        
        loss_contribution: Dict[str, float] = {}
        for comp, comp_score in component_scores.items():
            weight = self.engine_weights.get(comp, 1.0) / total_weight
            
            # Distance from ground truth, weighted by component importance
            if ground_truth > 0:
                # False negative: how far below ground truth?
                loss_contribution[comp] = (ground_truth - comp_score) * weight
            else:
                # False positive: how far above ground truth?
                loss_contribution[comp] = comp_score * weight
            
            loss_contribution[comp] = max(0.0, loss_contribution[comp])
        
        # Normalize to sum to |error|
        total_loss = sum(loss_contribution.values())
        if total_loss > 0:
            normalized = {
                comp: loss / total_loss * abs(error)
                for comp, loss in loss_contribution.items()
            }
            return normalized
        
        return {comp: 0.0 for comp in self.component_engines}
    
    def _find_primary_cause(
        self,
        loss_contribution: Dict[str, float],
        error: float,
    ) -> str:
        """Find the primary cause of error.
        
        Args:
            loss_contribution: Loss decomposition.
            error: Total error.
            
        Returns:
            Primary cause identifier.
        """
        if not loss_contribution or error == 0:
            return "none"
        
        primary = max(loss_contribution, key=loss_contribution.get)
        return f"{primary}_loss"
    
    def _compute_confidence(
        self,
        loss_contribution: Dict[str, float],
        error: float,
    ) -> float:
        """Compute confidence in attribution.
        
        Higher confidence when components explain error well
        and when primary cause is dominant.
        
        Args:
            loss_contribution: Loss decomposition.
            error: Total error.
            
        Returns:
            Confidence score [0, 1].
        """
        if error == 0:
            return 1.0
        
        total_loss = sum(loss_contribution.values())
        if total_loss == 0:
            return 0.0
        
        # How well do losses explain the total error?
        explained = min(total_loss / abs(error), 1.0) if abs(error) > 0.01 else 0.0
        
        # How concentrated is the primary cause?
        max_loss = max(loss_contribution.values()) if loss_contribution else 0
        concentration = max_loss / total_loss if total_loss > 0 else 0
        
        return 0.5 * explained + 0.5 * concentration
    
    def _compute_component_effectiveness(
        self,
        comp_name: str,
        scores: List[Tuple[float, float]],
    ) -> ComponentEffectiveness:
        """Compute effectiveness metrics for a component.
        
        Args:
            comp_name: Component name.
            scores: List of (component_score, ground_truth) pairs.
            
        Returns:
            ComponentEffectiveness with metrics.
        """
        eff = ComponentEffectiveness(name=comp_name)
        
        if not scores:
            return eff
        
        # Correlation with ground truth
        comp_vals = [s for s, _ in scores]
        gt_vals = [g for _, g in scores]
        
        # Pearson correlation
        n = len(scores)
        if n < 2:
            return eff
        
        mean_comp = sum(comp_vals) / n
        mean_gt = sum(gt_vals) / n
        
        numerator = sum(
            (c - mean_comp) * (g - mean_gt)
            for c, g in zip(comp_vals, gt_vals)
        )
        
        denom_comp = math.sqrt(sum((c - mean_comp) ** 2 for c in comp_vals))
        denom_gt = math.sqrt(sum((g - mean_gt) ** 2 for g in gt_vals))
        
        if denom_comp > 0 and denom_gt > 0:
            eff.correlation = numerator / (denom_comp * denom_gt)
        
        # Simple discrimination (AUC-like)
        positives = [c for c, g in scores if g > 0]
        negatives = [c for c, g in scores if g == 0]
        
        if positives and negatives:
            correct = sum(
                1 if p > n else (0.5 if p == n else 0)
                for p in positives
                for n in negatives
            )
            eff.discrimination = correct / (len(positives) * len(negatives))
        
        return eff