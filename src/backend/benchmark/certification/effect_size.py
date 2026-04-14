"""Effect size calculations for classifier comparison.

Effect sizes answer the critical question: "Is the improvement meaningful or trivial?"
Statistical significance alone is not enough - we need to quantify the magnitude
of the difference.

Effect Size Measures:
    - Cohen's d: Standardized mean difference (parametric)
    - Cliff's Delta: Non-parametric effect size (robust to outliers)

References:
    - Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences.
    - Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class EffectSizeResult:
    """Result of effect size calculation.

    Attributes:
        value: The effect size value.
        interpretation: Human-readable interpretation.
        magnitude: Magnitude category ('negligible', 'small', 'medium', 'large').
        method: Method used to compute effect size.
    """
    value: float
    interpretation: str
    magnitude: str
    method: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "interpretation": self.interpretation,
            "magnitude": self.magnitude,
            "method": self.method,
        }


def cohens_d(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    paired: bool = True,
) -> EffectSizeResult:
    """Compute Cohen's d effect size.

    Cohen's d measures the standardized difference between two means.
    For paired samples, it uses the standard deviation of the differences.

    Interpretation (Cohen, 1988):
        - |d| < 0.2: Negligible effect
        - 0.2 <= |d| < 0.5: Small effect
        - 0.5 <= |d| < 0.8: Medium effect
        - |d| >= 0.8: Large effect

    Args:
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        paired: Whether samples are paired (default True).

    Returns:
        EffectSizeResult with Cohen's d and interpretation.

    Raises:
        ValueError: If arrays have different lengths (paired=True) or are empty.
    """
    scores_a = np.asarray(scores_a, dtype=float)
    scores_b = np.asarray(scores_b, dtype=float)

    if len(scores_a) == 0 or len(scores_b) == 0:
        raise ValueError("Input arrays cannot be empty")

    if paired and len(scores_a) != len(scores_b):
        raise ValueError(
            f"For paired samples, arrays must have same length: "
            f"scores_a={len(scores_a)}, scores_b={len(scores_b)}"
        )

    if paired:
        # Paired Cohen's d: mean of differences / std of differences
        differences = scores_a - scores_b
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)  # Sample standard deviation

        if std_diff == 0:
            # No variance in differences
            d_value = 0.0 if mean_diff == 0 else np.inf * np.sign(mean_diff)
        else:
            d_value = mean_diff / std_diff
    else:
        # Independent Cohen's d: difference of means / pooled standard deviation
        mean_a = np.mean(scores_a)
        mean_b = np.mean(scores_b)
        std_a = np.std(scores_a, ddof=1)
        std_b = np.std(scores_b, ddof=1)
        n_a = len(scores_a)
        n_b = len(scores_b)

        # Pooled standard deviation
        pooled_std = np.sqrt(
            ((n_a - 1) * std_a ** 2 + (n_b - 1) * std_b ** 2) / (n_a + n_b - 2)
        )

        if pooled_std == 0:
            d_value = 0.0 if mean_a == mean_b else np.inf * np.sign(mean_a - mean_b)
        else:
            d_value = (mean_a - mean_b) / pooled_std

    # Interpret magnitude
    abs_d = abs(d_value)
    if abs_d < 0.2:
        magnitude = "negligible"
        interpretation = f"Negligible effect (d={d_value:.3f}). Difference is trivial."
    elif abs_d < 0.5:
        magnitude = "small"
        interpretation = f"Small effect (d={d_value:.3f}). Noticeable but modest improvement."
    elif abs_d < 0.8:
        magnitude = "medium"
        interpretation = f"Medium effect (d={d_value:.3f}). Meaningful practical improvement."
    else:
        magnitude = "large"
        interpretation = f"Large effect (d={d_value:.3f}). Substantial practical improvement."

    return EffectSizeResult(
        value=float(d_value),
        interpretation=interpretation,
        magnitude=magnitude,
        method="cohens_d_paired" if paired else "cohens_d_independent",
    )


def cliffs_delta(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
) -> EffectSizeResult:
    """Compute Cliff's Delta effect size.

    Cliff's Delta is a non-parametric effect size measure that quantifies
    the amount of overlap between two distributions. It's robust to outliers
    and doesn't assume normality.

    Interpretation (Romano et al., 2006):
        - |d| < 0.147: Negligible effect
        - 0.147 <= |d| < 0.33: Small effect
        - 0.33 <= |d| < 0.474: Medium effect
        - |d| >= 0.474: Large effect

    Args:
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.

    Returns:
        EffectSizeResult with Cliff's Delta and interpretation.

    Raises:
        ValueError: If arrays are empty.
    """
    scores_a = np.asarray(scores_a, dtype=float)
    scores_b = np.asarray(scores_b, dtype=float)

    if len(scores_a) == 0 or len(scores_b) == 0:
        raise ValueError("Input arrays cannot be empty")

    # Compute Cliff's Delta using efficient algorithm
    # Delta = P(A > B) - P(A < B)
    n_a = len(scores_a)
    n_b = len(scores_b)

    # Count comparisons
    greater = 0
    less = 0

    for score_a in scores_a:
        greater += np.sum(score_a > scores_b)
        less += np.sum(score_a < scores_b)

    # Compute delta
    delta = (greater - less) / (n_a * n_b)

    # Interpret magnitude
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        magnitude = "negligible"
        interpretation = f"Negligible effect (δ={delta:.3f}). Distributions nearly identical."
    elif abs_delta < 0.33:
        magnitude = "small"
        interpretation = f"Small effect (δ={delta:.3f}). Slight advantage for one classifier."
    elif abs_delta < 0.474:
        magnitude = "medium"
        interpretation = f"Medium effect (δ={delta:.3f}). Clear advantage for one classifier."
    else:
        magnitude = "large"
        interpretation = f"Large effect (δ={delta:.3f}). Strong advantage for one classifier."

    return EffectSizeResult(
        value=float(delta),
        interpretation=interpretation,
        magnitude=magnitude,
        method="cliffs_delta",
    )


def interpret_effect_size(
    value: float,
    method: str = "cohens_d",
) -> Tuple[str, str]:
    """Interpret effect size value.

    Args:
        value: Effect size value.
        method: Method used ('cohens_d' or 'cliffs_delta').

    Returns:
        Tuple of (magnitude, interpretation).
    """
    if method == "cohens_d":
        abs_value = abs(value)
        if abs_value < 0.2:
            return "negligible", "Negligible effect - difference is trivial"
        elif abs_value < 0.5:
            return "small", "Small effect - noticeable but modest improvement"
        elif abs_value < 0.8:
            return "medium", "Medium effect - meaningful practical improvement"
        else:
            return "large", "Large effect - substantial practical improvement"

    elif method == "cliffs_delta":
        abs_value = abs(value)
        if abs_value < 0.147:
            return "negligible", "Negligible effect - distributions nearly identical"
        elif abs_value < 0.33:
            return "small", "Small effect - slight advantage"
        elif abs_value < 0.474:
            return "medium", "Medium effect - clear advantage"
        else:
            return "large", "Large effect - strong advantage"

    else:
        raise ValueError(f"Unknown method: {method}")


def compute_all_effect_sizes(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    paired: bool = True,
) -> Dict[str, EffectSizeResult]:
    """Compute all effect size measures.

    Args:
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        paired: Whether samples are paired.

    Returns:
        Dictionary mapping effect size names to results.
    """
    results = {}

    # Cohen's d
    try:
        results["cohens_d"] = cohens_d(scores_a, scores_b, paired=paired)
    except (ValueError, ZeroDivisionError) as e:
        results["cohens_d"] = EffectSizeResult(
            value=0.0,
            interpretation=f"Could not compute: {e}",
            magnitude="unknown",
            method="cohens_d",
        )

    # Cliff's Delta
    try:
        results["cliffs_delta"] = cliffs_delta(scores_a, scores_b)
    except ValueError as e:
        results["cliffs_delta"] = EffectSizeResult(
            value=0.0,
            interpretation=f"Could not compute: {e}",
            magnitude="unknown",
            method="cliffs_delta",
        )

    return results


def effect_size_summary(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    engine_a: str = "Engine A",
    engine_b: str = "Engine B",
    paired: bool = True,
) -> str:
    """Generate human-readable effect size summary.

    Args:
        scores_a: Scores from classifier A.
        scores_b: Scores from classifier B.
        engine_a: Name of classifier A.
        engine_b: Name of classifier B.
        paired: Whether samples are paired.

    Returns:
        Formatted summary string.
    """
    effects = compute_all_effect_sizes(scores_a, scores_b, paired=paired)

    lines = [
        "=" * 60,
        f"EFFECT SIZE ANALYSIS: {engine_a} vs {engine_b}",
        "=" * 60,
        "",
    ]

    for name, result in effects.items():
        lines.append(f"{name.upper().replace('_', ' ')}:")
        lines.append(f"  Value: {result.value:.4f}")
        lines.append(f"  Magnitude: {result.magnitude}")
        lines.append(f"  Interpretation: {result.interpretation}")
        lines.append("")

    # Overall assessment
    cohens = effects.get("cohens_d")
    cliffs = effects.get("cliffs_delta")

    if cohens and cliffs:
        if cohens.value > 0 and cliffs.value > 0:
            direction = f"{engine_a} outperforms {engine_b}"
        elif cohens.value < 0 and cliffs.value < 0:
            direction = f"{engine_b} outperforms {engine_a}"
        else:
            direction = "Results are mixed"

        lines.append("OVERALL ASSESSMENT:")
        lines.append(f"  Direction: {direction}")
        lines.append(f"  Effect magnitude: {cohens.magnitude} (Cohen's d), {cliffs.magnitude} (Cliff's δ)")

    lines.append("=" * 60)
    return "\n".join(lines)