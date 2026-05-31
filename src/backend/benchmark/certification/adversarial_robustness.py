"""Adversarial robustness testing for benchmark validation.

Ensures benchmark metrics are stable under adversarial perturbations.
This prevents overfitting to specific dataset characteristics.

Tests robustness by:
1. Creating adversarial variants of test pairs
2. Re-evaluating tools on adversarial pairs
3. Computing metric stability scores
4. Flagging metrics that degrade significantly
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np


@dataclass(frozen=True)
class AdversarialRobustnessResult:
    """Result of adversarial robustness evaluation.
    
    Attributes:
        original_metric: Original metric value (e.g., F1 score).
        adversarial_metrics: Metric values on adversarial variants.
        stability_score: How stable metric is under adversarial attacks (0-1).
        mean_degradation: Average metric drop on adversarial variants (0-1).
        max_degradation: Worst-case metric drop (0-1).
        is_robust: Whether metric passes robustness threshold (>0.85).
        attack_details: Per-attack degradation breakdown.
    """
    original_metric: float
    adversarial_metrics: List[float]
    stability_score: float
    mean_degradation: float
    max_degradation: float
    is_robust: bool
    attack_details: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_metric": round(self.original_metric, 4),
            "adversarial_metrics": [round(m, 4) for m in self.adversarial_metrics],
            "stability_score": round(self.stability_score, 4),
            "mean_degradation": round(self.mean_degradation, 4),
            "max_degradation": round(self.max_degradation, 4),
            "is_robust": self.is_robust,
            "attack_details": {k: round(v, 4) for k, v in self.attack_details.items()},
        }


class AdversarialAttack:
    """Base class for adversarial attacks on code pairs."""
    
    name: str = "base_attack"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Apply adversarial perturbation to code pair.
        
        Args:
            code_a: First code sample.
            code_b: Second code sample.
            
        Returns:
            Tuple of (perturbed_code_a, perturbed_code_b).
        """
        raise NotImplementedError


class WhitespaceNoise(AdversarialAttack):
    """Add varying whitespace without changing logic."""
    
    name = "whitespace_noise"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Add extra blank lines and indentation variations."""
        import re
        
        def add_noise(code: str) -> str:
            # Add extra blank lines
            code = re.sub(r'\n\n+', '\n\n\n', code)
            # Add trailing whitespace
            lines = code.split('\n')
            lines = [line + '  ' if line.strip() else line for line in lines]
            return '\n'.join(lines)
        
        return add_noise(code_a), add_noise(code_b)


class IdentifierNoise(AdversarialAttack):
    """Slight identifier renaming that preserves semantics."""
    
    name = "identifier_noise"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Rename some (not all) identifiers to add noise."""
        import re
        import random
        
        def add_identifier_noise(code: str, seed: int = 42) -> str:
            rng = random.Random(seed)
            keywords = {
                'if', 'else', 'for', 'while', 'return', 'def', 'class',
                'import', 'from', 'try', 'except', 'with', 'as', 'in',
                'not', 'and', 'or', 'is', 'None', 'True', 'False'
            }
            
            id_map = {}
            
            def replace_id(match):
                name = match.group(0)
                if name in keywords:
                    return name
                # Only rename 30% of identifiers to add subtle noise
                if name not in id_map:
                    if rng.random() < 0.3:
                        id_map[name] = f"__{rng.randint(1000, 9999)}"
                    else:
                        id_map[name] = name
                return id_map[name]
            
            return re.sub(r'\b[a-zA-Z_]\w*\b', replace_id, code)
        
        return add_identifier_noise(code_a, 42), add_identifier_noise(code_b, 43)


class CommentNoise(AdversarialAttack):
    """Add adversarial comments that might confuse pattern matching."""
    
    name = "comment_noise"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Insert confusing comments."""
        comments = [
            "# TODO: fix this",
            "# HACK: workaround for edge case",
            "# NOTE: important",
            "# FIXME: optimize later",
            "# XXX: needs review",
        ]
        
        def add_comments(code: str, seed: int = 42) -> str:
            import random
            rng = random.Random(seed)
            lines = code.split('\n')
            result = []
            
            for i, line in enumerate(lines):
                result.append(line)
                if line.strip() and i < len(lines) - 1 and rng.random() < 0.2:
                    result.append(f"  {rng.choice(comments)}")
            
            return '\n'.join(result)
        
        return add_comments(code_a, 44), add_comments(code_b, 45)


class TokenBoundaryNoise(AdversarialAttack):
    """Add slight changes at token boundaries."""
    
    name = "token_boundary_noise"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Change operator spacing, bracket placement, etc."""
        import re
        
        def perturb_tokens(code: str) -> str:
            # Vary spacing around operators
            code = re.sub(r' (\+|\-|\*|/|==|!=) ', r'\1', code)
            code = re.sub(r'(\+|\-|\*|/|==|!=)', r' \1 ', code)
            return code
        
        return perturb_tokens(code_a), perturb_tokens(code_b)


class SemanticPreservingTransform(AdversarialAttack):
    """Apply semantically-preserving but syntactically different transformations."""
    
    name = "semantic_transform"
    
    def apply(self, code_a: str, code_b: str) -> Tuple[str, str]:
        """Convert equivalent expressions."""
        import re
        
        def transform(code: str) -> str:
            # x != 0 -> not (x == 0)
            code = re.sub(r'(\w+)\s*!=\s*0', r'not (\1 == 0)', code)
            # x == True -> x is True (only in conditionals)
            code = re.sub(r'if\s+(\w+)\s*==\s*True:', r'if \1 is True:', code)
            return code
        
        return transform(code_a), transform(code_b)


# All available attacks
ALL_ATTACKS: List[AdversarialAttack] = [
    WhitespaceNoise(),
    IdentifierNoise(),
    CommentNoise(),
    TokenBoundaryNoise(),
    SemanticPreservingTransform(),
]


class AdversarialRobustnessValidator:
    """Validates benchmark metrics against adversarial perturbations."""
    
    def __init__(self, attacks: Optional[List[AdversarialAttack]] = None):
        """Initialize validator.
        
        Args:
            attacks: List of attacks to apply. Defaults to ALL_ATTACKS.
        """
        self.attacks = attacks or ALL_ATTACKS
    
    def evaluate(
        self,
        metric_fn: Callable[[List[str], List[str], List[str], List[str]], float],
        code_pairs: List[Tuple[str, str]],
        labels: List[int],
        robustness_threshold: float = 0.85,
    ) -> AdversarialRobustnessResult:
        """Evaluate robustness of a metric.
        
        Args:
            metric_fn: Function that takes (scores_a, scores_b, labels, decisions)
                      and returns a float metric value.
            code_pairs: List of (code_a, code_b) tuples.
            labels: Ground truth labels for pairs.
            robustness_threshold: Minimum stability score to consider robust.
            
        Returns:
            AdversarialRobustnessResult.
        """
        # Compute original metric
        code_a_list = [a for a, b in code_pairs]
        code_b_list = [b for a, b in code_pairs]
        
        original_metric = metric_fn(code_a_list, code_b_list, labels, [])
        
        # Apply adversarial attacks
        adversarial_metrics = []
        attack_details = {}
        
        for attack in self.attacks:
            adversarial_pairs = [
                attack.apply(a, b) for a, b in code_pairs
            ]
            adv_code_a = [a for a, b in adversarial_pairs]
            adv_code_b = [b for a, b in adversarial_pairs]
            
            adv_metric = metric_fn(adv_code_a, adv_code_b, labels, [])
            adversarial_metrics.append(adv_metric)
            
            # Track degradation per attack
            degradation = max(0.0, original_metric - adv_metric) / (original_metric + 1e-6)
            attack_details[attack.name] = float(degradation)
        
        # Compute stability metrics
        mean_degradation = float(np.mean([
            max(0.0, original_metric - m) / (original_metric + 1e-6)
            for m in adversarial_metrics
        ]))
        max_degradation = float(np.max([
            max(0.0, original_metric - m) / (original_metric + 1e-6)
            for m in adversarial_metrics
        ]))
        
        # Stability = 1 - mean_degradation
        stability_score = float(1.0 - mean_degradation)
        is_robust = stability_score >= robustness_threshold
        
        return AdversarialRobustnessResult(
            original_metric=original_metric,
            adversarial_metrics=adversarial_metrics,
            stability_score=stability_score,
            mean_degradation=mean_degradation,
            max_degradation=max_degradation,
            is_robust=is_robust,
            attack_details=attack_details,
        )


def validate_benchmark_robustness(
    metrics: Dict[str, float],
    code_pairs: List[Tuple[str, str]],
    labels: List[int],
    validators: Optional[List[AdversarialRobustnessValidator]] = None,
) -> Dict[str, AdversarialRobustnessResult]:
    """Validate robustness of multiple metrics.
    
    Args:
        metrics: Dictionary mapping metric names to metric functions.
        code_pairs: List of code pairs.
        labels: Ground truth labels.
        validators: Optional custom validators.
        
    Returns:
        Dictionary mapping metric names to robustness results.
    """
    if validators is None:
        validators = [AdversarialRobustnessValidator()]
    
    results = {}
    
    for metric_name, metric_fn in metrics.items():
        for validator in validators:
            result = validator.evaluate(metric_fn, code_pairs, labels)
            results[f"{metric_name}_robustness"] = result
    
    return results