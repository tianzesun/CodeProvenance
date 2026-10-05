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

#: Below this average reliability there is too little evidence for an "extreme score"
#: to mean anything (a file with no measurable signals scores 0.0, which used to
#: earn the full +0.1 "very confident it is human" bonus).
MIN_RELIABILITY_FOR_BONUS = 0.25


def _average_reliability(reliabilities: dict[str, float]) -> float:
    """Mean reliability; 0.0 for an empty mapping (it used to be a ZeroDivisionError)."""
    if not reliabilities:
        return 0.0
    return sum(reliabilities.values()) / len(reliabilities)


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
    base_confidence = _calculate_base_confidence(reliabilities, agreement)

    # Variance is measured over the signals that carry evidence.
    variance = calculate_signal_variance(signals, reliabilities)
    variance_penalty = _calculate_variance_penalty(variance)

    extreme_bonus = (
        _calculate_extreme_bonus(ai_probability)
        if _average_reliability(reliabilities) >= MIN_RELIABILITY_FOR_BONUS
        else 0.0
    )

    final_confidence = base_confidence - variance_penalty + extreme_bonus
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
    avg_reliability = _average_reliability(reliabilities)
    agreement_score = agreement["agreement_score"]
    return (agreement_score + avg_reliability) / 2


def _calculate_variance_penalty(variance: float) -> float:
    """Calculate penalty for high signal variance.

    Args:
        variance: Signal variance in [0.0, 0.25]

    Returns:
        Penalty in [0.0, 0.15]
    """
    normalized_variance = min(1.0, max(0.0, variance / 0.25))
    return normalized_variance * 0.15


def _calculate_extreme_bonus(ai_probability: float) -> float:
    """Calculate bonus for extreme AI probability scores.

    Args:
        ai_probability: AI probability in [0.0, 1.0]

    Returns:
        Bonus in [0.0, 0.1]
    """
    if ai_probability > 0.8 or ai_probability < 0.2:
        return 0.1
    elif ai_probability > 0.7 or ai_probability < 0.3:
        return 0.05
    return 0.0


def get_confidence_level(confidence: float) -> str:
    """Get confidence level label.

    The single definition: ``reporting`` used to carry an identical copy.

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
    return "Very Low"


def should_flag_low_confidence(ai_probability: float, confidence: float) -> bool:
    """Determine if result should be flagged for low confidence.

    Args:
        ai_probability: AI probability in [0.0, 1.0]
        confidence: Confidence in [0.0, 1.0]

    Returns:
        True if result should be flagged, False otherwise
    """
    return bool(
        (ai_probability > 0.7 and confidence < 0.4)
        or (ai_probability > 0.5 and confidence < 0.3)
        or (ai_probability < 0.3 and confidence < 0.3)
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
        adjustment = 0.2  # very short: reduce confidence by 20%
    elif code_length < 500:
        adjustment = 0.1  # short: reduce confidence by 10%
    elif code_length < 2000:
        adjustment = 0.0  # medium: no adjustment
    else:
        adjustment = -0.05  # long: increase confidence by 5%

    return round(max(0.0, min(1.0, confidence - adjustment)), 3)


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
    agreement_level = agreement.get("agreement_level", "unknown")

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
            "Some signal disagreement or moderate reliability."
        )
    elif confidence >= 0.3:
        return (
            f"Low confidence ({confidence:.1%}). "
            f"Signals show {agreement_level} agreement with mixed reliability."
        )
    return (
        f"Very low confidence ({confidence:.1%}). "
        "Result should be treated with caution."
    )
