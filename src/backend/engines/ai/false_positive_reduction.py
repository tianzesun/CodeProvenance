"""False positive reduction framework.

Implements safeguards to reduce false positives in AI detection.

Safeguards:
1. Single Signal Dominance: If only 1 signal is elevated, reduce confidence
2. Contradiction Detection: If signals contradict, reduce confidence
3. Low Reliability: If average reliability is low, reduce confidence
4. Extreme Variance: If signal variance is high, reduce confidence
5. Confidence Floor: Never allow confidence below threshold for medium risk
"""

from src.backend.engines.ai.agreement import (
    calculate_signal_variance,
    detect_signal_contradiction,
    detect_single_signal_dominance,
    get_dominant_signal,
)
from src.backend.engines.ai.models import SignalScores


def apply_false_positive_reduction(
    ai_probability: float,
    confidence: float,
    signals: SignalScores,
    reliabilities: dict[str, float],
) -> tuple[float, float]:
    """Apply false positive reduction safeguards.

    Args:
        ai_probability: AI probability in [0.0, 1.0]
        confidence: Confidence in [0.0, 1.0]
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores

    Returns:
        Tuple of (adjusted_ai_probability, adjusted_confidence)
    """
    adjusted_confidence = confidence

    # Safeguard 1: Single Signal Dominance
    if detect_single_signal_dominance(signals):
        adjusted_confidence -= 0.3

    # Safeguard 2: Contradiction Detection
    if detect_signal_contradiction(signals):
        adjusted_confidence -= 0.2

    # Safeguard 3: Low Reliability
    avg_reliability = sum(reliabilities.values()) / len(reliabilities)
    if avg_reliability < 0.5:
        adjusted_confidence -= 0.25

    # Safeguard 4: Extreme Variance
    variance = calculate_signal_variance(signals)
    if variance > 0.3:
        adjusted_confidence -= 0.15

    # Safeguard 5: Confidence Floor
    # Never allow confidence below threshold for medium risk
    if 0.4 <= ai_probability <= 0.6:
        adjusted_confidence = max(adjusted_confidence, 0.3)

    # Ensure confidence is in [0.0, 1.0]
    adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

    # AI probability may also be adjusted based on confidence
    # If confidence is very low, reduce AI probability slightly
    if adjusted_confidence < 0.2:
        # Move toward 0.5 (neutral)
        ai_probability = ai_probability * 0.8 + 0.5 * 0.2

    return (
        round(ai_probability, 3),
        round(adjusted_confidence, 3),
    )


def check_single_signal_dominance(signals: SignalScores) -> dict:
    """Check for single signal dominance and return details.

    Args:
        signals: SignalScores object

    Returns:
        Dictionary with:
        - is_dominant: bool
        - dominant_signal: str (signal name or empty)
        - confidence_penalty: float
        - explanation: str
    """
    is_dominant = detect_single_signal_dominance(signals)
    dominant_signal = get_dominant_signal(signals)

    if is_dominant:
        penalty = 0.3
        explanation = (
            f"Single signal dominance detected: {dominant_signal}. "
            f"Reducing confidence by {penalty:.0%}."
        )
    else:
        penalty = 0.0
        explanation = "No single signal dominance detected."

    return {
        "is_dominant": is_dominant,
        "dominant_signal": dominant_signal,
        "confidence_penalty": penalty,
        "explanation": explanation,
    }


def check_signal_contradiction(signals: SignalScores) -> dict:
    """Check for signal contradiction and return details.

    Args:
        signals: SignalScores object

    Returns:
        Dictionary with:
        - is_contradictory: bool
        - confidence_penalty: float
        - explanation: str
    """
    is_contradictory = detect_signal_contradiction(signals)

    if is_contradictory:
        penalty = 0.2
        explanation = (
            "Signal contradiction detected: some signals indicate AI-like, "
            "others indicate human-like. Reducing confidence by 20%."
        )
    else:
        penalty = 0.0
        explanation = "No signal contradiction detected."

    return {
        "is_contradictory": is_contradictory,
        "confidence_penalty": penalty,
        "explanation": explanation,
    }


def check_low_reliability(reliabilities: dict[str, float]) -> dict:
    """Check for low average reliability and return details.

    Args:
        reliabilities: Dictionary of reliability scores

    Returns:
        Dictionary with:
        - is_low_reliability: bool
        - avg_reliability: float
        - confidence_penalty: float
        - explanation: str
    """
    avg_reliability = sum(reliabilities.values()) / len(reliabilities)
    is_low = avg_reliability < 0.5

    if is_low:
        penalty = 0.25
        explanation = (
            f"Low average reliability ({avg_reliability:.1%}). "
            f"Reducing confidence by {penalty:.0%}."
        )
    else:
        penalty = 0.0
        explanation = f"Adequate average reliability ({avg_reliability:.1%})."

    return {
        "is_low_reliability": is_low,
        "avg_reliability": round(avg_reliability, 3),
        "confidence_penalty": penalty,
        "explanation": explanation,
    }


def check_extreme_variance(signals: SignalScores) -> dict:
    """Check for extreme signal variance and return details.

    Args:
        signals: SignalScores object

    Returns:
        Dictionary with:
        - is_extreme_variance: bool
        - variance: float
        - confidence_penalty: float
        - explanation: str
    """
    variance = calculate_signal_variance(signals)
    is_extreme = variance > 0.3

    if is_extreme:
        penalty = 0.15
        explanation = (
            f"Extreme signal variance ({variance:.3f}). "
            f"Reducing confidence by {penalty:.0%}."
        )
    else:
        penalty = 0.0
        explanation = f"Acceptable signal variance ({variance:.3f})."

    return {
        "is_extreme_variance": is_extreme,
        "variance": round(variance, 3),
        "confidence_penalty": penalty,
        "explanation": explanation,
    }


def get_all_false_positive_checks(
    signals: SignalScores, reliabilities: dict[str, float]
) -> dict:
    """Run all false positive reduction checks.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores

    Returns:
        Dictionary with results of all checks
    """
    return {
        "single_signal_dominance": check_single_signal_dominance(signals),
        "signal_contradiction": check_signal_contradiction(signals),
        "low_reliability": check_low_reliability(reliabilities),
        "extreme_variance": check_extreme_variance(signals),
    }


def calculate_total_confidence_penalty(
    signals: SignalScores, reliabilities: dict[str, float]
) -> float:
    """Calculate total confidence penalty from all safeguards.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores

    Returns:
        Total penalty in [0.0, 1.0]
    """
    penalty = 0.0

    # Single signal dominance
    if detect_single_signal_dominance(signals):
        penalty += 0.3

    # Signal contradiction
    if detect_signal_contradiction(signals):
        penalty += 0.2

    # Low reliability
    avg_reliability = sum(reliabilities.values()) / len(reliabilities)
    if avg_reliability < 0.5:
        penalty += 0.25

    # Extreme variance
    variance = calculate_signal_variance(signals)
    if variance > 0.3:
        penalty += 0.15

    # Cap penalty at 1.0
    return min(penalty, 1.0)
