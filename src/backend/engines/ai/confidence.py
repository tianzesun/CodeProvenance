"""Confidence calibration framework.

Assigns confidence scores based on signal agreement, reliability, and variance.

Confidence factors:
- Signal agreement (high agreement → high confidence)
- Signal reliability (high reliability → high confidence)
- Signal variance (low variance → high confidence)
- Extreme scores (very high/low → high confidence)
"""

from src.backend.engines.ai.agreement import calculate_signal_variance
from src.backend.engines.ai.models import SignalScores


def calibrate_confidence(
    signals: SignalScores,
    reliabilities: dict[str, float],
    agreement: dict,
    ai_probability: float,
) -> float:
    """Calibrate confidence score based on multiple factors.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores
        agreement: Agreement analysis dictionary
        ai_probability: Final AI probability score

    Returns:
        Confidence score in [0.0, 1.0]
    """
    # Calculate base confidence from agreement and reliability
    base_confidence = _calculate_base_confidence(reliabilities, agreement)

    # Apply variance penalty
    variance = calculate_signal_variance(signals)
    variance_penalty = _calculate_variance_penalty(variance)

    # Apply extreme score bonus
    extreme_bonus = _calculate_extreme_bonus(ai_probability)

    # Combine factors
    final_confidence = base_confidence - variance_penalty + extreme_bonus

    # Ensure confidence is in [0.0, 1.0]
    return round(max(0.0, min(1.0, final_confidence)), 3)


def _calculate_base_confidence(
    reliabilities: dict[str, float], agreement: dict
) -> float:
    """Calculate base confidence from agreement and reliability.

    Args:
        reliabilities: Dictionary of reliability scores
        agreement: Agreement analysis dictionary

    Returns:
        Base confidence in [0.0, 1.0]
    """
    # Average reliability
    avg_reliability = sum(reliabilities.values()) / len(reliabilities)

    # Agreement score
    agreement_score = agreement["agreement_score"]

    # Base confidence is average of agreement and reliability
    base_confidence = (agreement_score + avg_reliability) / 2

    return base_confidence


def _calculate_variance_penalty(variance: float) -> float:
    """Calculate penalty for high signal variance.

    Args:
        variance: Signal variance in [0.0, 0.25]

    Returns:
        Penalty in [0.0, 0.15]
    """
    # Normalize variance to [0.0, 1.0]
    normalized_variance = variance / 0.25

    # Penalty increases with variance
    penalty = normalized_variance * 0.15

    return penalty


def _calculate_extreme_bonus(ai_probability: float) -> float:
    """Calculate bonus for extreme AI probability scores.

    Args:
        ai_probability: AI probability in [0.0, 1.0]

    Returns:
        Bonus in [0.0, 0.1]
    """
    # Bonus for very high or very low scores
    if ai_probability > 0.8 or ai_probability < 0.2:
        return 0.1
    elif ai_probability > 0.7 or ai_probability < 0.3:
        return 0.05
    else:
        return 0.0


def get_confidence_level(confidence: float) -> str:
    """Get confidence level label.

    Args:
        confidence: Confidence score in [0.0, 1.0]

    Returns:
        Confidence level: "Very Low" / "Low" / "Medium" / "High" / "Very High"
    """
    if confidence >= 0.85:
        return "Very High"
    elif confidence >= 0.7:
        return "High"
    elif confidence >= 0.5:
        return "Medium"
    elif confidence >= 0.3:
        return "Low"
    else:
        return "Very Low"


def should_flag_low_confidence(ai_probability: float, confidence: float) -> bool:
    """Determine if result should be flagged for low confidence.

    Args:
        ai_probability: AI probability in [0.0, 1.0]
        confidence: Confidence in [0.0, 1.0]

    Returns:
        True if result should be flagged, False otherwise
    """
    # Flag if confidence is too low for the AI probability
    return bool(
        ai_probability > 0.7
        and confidence < 0.4
        or ai_probability > 0.5
        and confidence < 0.3
        or ai_probability < 0.3
        and confidence < 0.3
    )


def adjust_confidence_for_code_length(confidence: float, code_length: int) -> float:
    """Adjust confidence based on code length.

    Shorter code is less reliable, so reduce confidence.

    Args:
        confidence: Base confidence in [0.0, 1.0]
        code_length: Length of code in characters

    Returns:
        Adjusted confidence in [0.0, 1.0]
    """
    if code_length < 100:
        # Very short code: reduce confidence by 20%
        adjustment = 0.2
    elif code_length < 500:
        # Short code: reduce confidence by 10%
        adjustment = 0.1
    elif code_length < 2000:
        # Medium code: no adjustment
        adjustment = 0.0
    else:
        # Long code: increase confidence by 5%
        adjustment = -0.05

    adjusted_confidence = confidence - adjustment
    return round(max(0.0, min(1.0, adjusted_confidence)), 3)


def get_confidence_explanation(
    confidence: float,
    agreement: dict,
    reliabilities: dict[str, float],
) -> str:
    """Get human-readable explanation of confidence score.

    Args:
        confidence: Confidence score
        agreement: Agreement analysis dictionary
        reliabilities: Dictionary of reliability scores

    Returns:
        Explanation string
    """
    agreement_level = agreement["agreement_level"]

    if confidence >= 0.85:
        return (
            f"Very high confidence ({confidence:.1%}). "
            f"Signals show {agreement_level} agreement with strong reliability."
        )
    elif confidence >= 0.7:
        return (
            f"High confidence ({confidence:.1%}). "
            f"Signals show {agreement_level} agreement."
        )
    elif confidence >= 0.5:
        return (
            f"Medium confidence ({confidence:.1%}). "
            f"Some signal disagreement or moderate reliability."
        )
    elif confidence >= 0.3:
        return (
            f"Low confidence ({confidence:.1%}). "
            f"Signals show {agreement_level} agreement with mixed reliability."
        )
    else:
        return (
            f"Very low confidence ({confidence:.1%}). "
            f"Result should be treated with caution."
        )
