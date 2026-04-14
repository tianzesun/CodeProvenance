"""Error Attribution Model (EAM) for code similarity detection.

Per-pair decomposition of similarity score errors into component contributions.
Answers: "WHY exactly did the detector fail on this pair?"

Each failure is broken down as:
{
    "pair_id": "pair_042",
    "ground_truth": 1.0,
    "predicted_score": 0.32,
    "error": -0.68,
    "attribution": {
        "token_component": 0.45,
        "ast_component": 0.15,
        "structure_component": 0.20,
        "semantic_component": 0.10
    },
    "loss_contribution": {
        "token_loss": 0.55,   # How much token mismatch contributed to error
        "ast_loss": 0.30,     # How much AST mismatch contributed
        "structure_loss": 0.15 # How much structure mismatch contributed
    },
    "primary_cause": "token_loss",
    "confidence": 0.85
}

Usage:
    from benchmark.analysis.error_attribution import ErrorAttributionModel

    eam = ErrorAttributionModel()
    results = eam.attribute(dataset.pairs, engine)
    print(results.summary())
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from benchmark.datasets.synthetic_generator import SyntheticPair
from benchmark.similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)


@dataclass
class ComponentScore:
    """Score from a single similarity component."""
    name: str
    score: float
    weight: float = 1.0
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class ErrorAttribution:
    """Error attribution for a single code pair.
    
    Decomposes the similarity error into component contributions.
    """
    pair_id: str
    ground_truth: float  # 0.0 or 1.0
    predicted_score: float
    error: float  # predicted - ground_truth (negative = under-detection)
    
    # Component scores (raw, before weighting)
    component_scores: Dict[str, float] = field(default_factory=dict)
    
    # Weighted contribution of each component
    component_weights: Dict[str, float] = field(default_factory=dict)
    
    # Loss decomposition: how much each component contributed to error
    loss_contribution: Dict[str, float] = field(default_factory=dict)
    
    # Primary cause of error
    primary_cause: str = ""
    
    # Confidence in attribution (how well components explain the error)
    confidence: float = 1.0
    
    # Clone type context
    clone_type: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_false_positive(self) -> bool:
        return self.predicted_score >= 0.5 and self.ground_truth < 0.5
    
    @property
    def is_false_negative(self) -> bool:
        return self.predicted_score < 0.5 and self.ground_truth >= 0.5
    
    @property
    def error_magnitude(self) -> float:
        return abs(self.error)


@dataclass
class AttributionReport:
    """Aggregate error attribution report across all pairs."""
    total_pairs: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_positives: int = 0
    true_negatives: int = 0
    
    # Per-component aggregate loss
    component_losses: Dict[str, float] = field(default_factory=dict)
    
    # Primary cause distribution
    primary_cause_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Per-clone-type breakdown
    by_clone_type: Dict[int, "CloneTypeAttribution"] = field(default_factory=dict)
    
    # Per-component effectiveness
    component_effectiveness: Dict[str, ComponentEffectiveness] = field(default_factory=dict)
    
    # Top failure patterns
    top_failures: List[ErrorAttribution] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "ERROR ATTRIBUTION MODEL (EAM) REPORT",
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


@dataclass
class CloneTypeAttribution:
    """Attribution breakdown for a specific clone type."""
    clone_type: int
    count: int
    avg_error: float = 0.0
    component_losses: Dict[str, float] = field(default_factory=dict)
    primary_causes: Dict[str, int] = field(default_factory=dict)


@dataclass
class ComponentEffectiveness:
    """How effective each component is at detecting clones."""
    name: str
    correlation: float = 0.0  # Correlation with ground truth
    discrimination: float = 0.0  # AUC-like discrimination score
    clone_type_sensitivity: Dict[int, float] = field(default_factory=dict)


class ErrorAttributionModel:
    """Per-pair error attribution for similarity detection.
    
    Decomposes similarity errors into component contributions:
    - Token-based loss
    - AST-based loss
    - Structure-based loss
    - Semantic-based loss
    
    Usage:
        eam = ErrorAttributionModel()
        report = eam.analyze(pairs, hybrid_engine)
        print(report.summary())
    """
    
    def __init__(
        self,
        component_engines: Optional[Dict[str, Callable[[str, str], float]]] = None,
        engine_weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the attribution model.
        
        Args:
            component_engines: Dict of component_name -> similarity_function.
                If None, uses default components (token, ast, structure).
            engine_weights: Dict of component_name -> weight.
                If None, uses equal weights.
        """
        if component_engines is None:
            self.component_engines = self._default_components()
        else:
            self.component_engines = component_engines
        
        if engine_weights is None:
            # Default weights based on typical hybrid engine
            self.engine_weights = {
                "token": 0.5,
                "ast": 0.3,
                "structure": 0.2,
            }
        else:
            self.engine_weights = engine_weights
    
    def _default_components(
        self
    ) -> Dict[str, Callable[[str, str], float]]:
        """Create default component similarity functions.
        
        Returns:
            Dict of component name to similarity function.
        """
        token_engine = TokenWinnowingEngine()
        ast_engine = ASTEngine()
        
        return {
            "token": token_engine.compare,
            "ast": ast_engine.compare,
            "structure": _structural_similarity,
        }
    
    def analyze(
        self,
        pairs: List[SyntheticPair],
        main_engine: Any = None,
        threshold: float = 0.5,
    ) -> AttributionReport:
        """Run error attribution analysis on all pairs.
        
        Args:
            pairs: List of synthetic pairs with ground truth.
            main_engine: Main engine used for benchmark.
            threshold: Decision threshold.
            
        Returns:
            AttributionReport with analysis.
        """
        report = AttributionReport()
        report.total_pairs = len(pairs)
        
        all_attributions: List[ErrorAttribution] = []
        fn_attributions: List[ErrorAttribution] = []
        
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
            attribution = ErrorAttribution(
                pair_id=pair.id,
                ground_truth=ground_truth,
                predicted_score=predicted,
                error=error,
                component_scores=component_scores,
                component_weights=dict(self.engine_weights),
                loss_contribution=loss_contribution,
                primary_cause=self._find_primary_cause(loss_contribution, error),
                confidence=self._compute_confidence(loss_contribution, error),
                clone_type=pair.clone_type,
            )
            
            all_attributions.append(attribution)
            
            if attribution.is_false_negative:
                fn_attributions.append(attribution)
        
        # Aggregate component losses
        total_error = sum(abs(a.error) for a in all_attributions if a.error != 0)
        if total_error > 0:
            for comp in self.component_engines:
                total_loss = sum(
                    a.loss_contribution.get(comp, 0.0)
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
        type_attributions: Dict[int, List[ErrorAttribution]] = {}
        for a in all_attributions:
            type_attributions.setdefault(a.clone_type, []).append(a)
        
        for clone_type, attributions in type_attributions.items():
            errors = [a.error for a in attributions]
            type_report = CloneTypeAttribution(
                clone_type=clone_type,
                count=len(attributions),
                avg_error=sum(errors) / len(errors) if errors else 0.0,
            )
            
            # Component losses for this type
            for comp in self.component_engines:
                comp_loss = sum(
                    a.loss_contribution.get(comp, 0.0)
                    for a in attributions
                )
                type_report.component_losses[comp] = comp_loss
            
            # Primary causes for this type
            for a in attributions:
                type_report.primary_causes[a.primary_cause] = (
                    type_report.primary_causes.get(a.primary_cause, 0) + 1
                )
            
            report.by_clone_type[clone_type] = type_report
        
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
        
        Uses Shapley-value-inspired decomposition:
        For each component, compute how much the score would change if
        that component was at ground truth vs its current value.
        
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
        
        # Weighted component contribution to final score
        weighted_scores = {
            comp: score * self.engine_weights.get(comp, 1.0) / total_weight
            for comp, score in component_scores.items()
        }
        
        # For negative error (under-detection): which components are below ground truth?
        # For positive error (over-detection): which components are above ground truth?
        
        loss_contribution: Dict[str, float] = {}
        for comp, comp_score in component_scores.items():
            weight = self.engine_weights.get(comp, 1.0) / total_weight
            comp_contribution = comp_score * weight
            
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
    
    def compute_clone_type_sensitivity(
        self,
        pairs: List[SyntheticPair],
        engines: Dict[str, Any],
        threshold: float = 0.5,
    ) -> Dict[str, Dict[int, float]]:
        """Compute clone-type sensitivity matrix.
        
        Generates the diagnostic table used in research papers:
                        Type1  Type2  Type3  Type4
        token_engine     1.0    0.4    0.2    0.1
        ast_engine       0.9    0.6    0.8    0.5
        hybrid           1.0    0.8    0.7    0.6
        
        Args:
            pairs: List of synthetic pairs.
            engines: Dict of engine_name -> engine instance.
            threshold: Decision threshold.
            
        Returns:
            Dict of engine_name -> {clone_type: sensitivity},
            where sensitivity is recall for that clone type.
        """
        # Group pairs by clone type
        type_pairs: Dict[int, List[SyntheticPair]] = {}
        for p in pairs:
            if p.label == 1:  # Only clone pairs
                type_pairs.setdefault(p.clone_type, []).append(p)
        
        # For each engine, compute sensitivity per type
        sensitivity: Dict[str, Dict[int, float]] = {}
        
        for engine_name, engine in engines.items():
            sensitivity[engine_name] = {}
            
            for clone_type, type_specific_pairs in type_pairs.items():
                if not type_specific_pairs:
                    sensitivity[engine_name][clone_type] = 0.0
                    continue
                
                tp = fn = 0
                for pair in type_specific_pairs:
                    score = engine.compare(pair.code_a, pair.code_b)
                    if score >= threshold:
                        tp += 1
                    else:
                        fn += 1
                
                sensitivity[engine_name][clone_type] = (
                    tp / (tp + fn) if (tp + fn) > 0 else 0.0
                )
        
        return sensitivity
    
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
        
        # Simple discrimination (AUC-like):
        # P(component score for positive > component score for negative)
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


def _structural_similarity(code_a: str, code_b: str) -> float:
    """Compute structural similarity from raw code features.
    
    Measures similarity in control flow structure, nesting, etc.
    
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