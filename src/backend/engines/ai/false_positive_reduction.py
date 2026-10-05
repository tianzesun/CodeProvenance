"""False positive reduction framework.

Implements safeguards to reduce false positives in AI detection.

Safeguards:
1. Single Signal Dominance: If only 1 signal is elevated, reduce confidence
2. Contradiction Detection: If signals contradict, reduce confidence
3. Low Reliability: If average reliability is low, reduce confidence
4. Extreme Variance: If signal variance is high, reduce confidence
5. Confidence Floor: Never allow confidence below threshold for medium risk
6. Low-confidence cap: a low-confidence result must not land in the high band

The penalties are computed in ONE place (:func:`compute_penalties`) and shared by
the apply path, the per-check reports and the total, so they cannot drift apart.
"""

from src.backend.engines.ai.agreement import (
    calculate_signal_variance,
    detect_signal_contradiction,
    detect_single_signal_dominance,
    get_dominant_signal,
)
from src.backend.engines.ai.models import SignalScores

SINGLE_SIGNAL_PENALTY = 0.30
CONTRADICTION_PENALTY = 0.20
LOW_RELIABILITY_PENALTY = 0.25
EXTREME_VARIANCE_PENALTY = 0.15

LOW_RELIABILITY_THRESHOLD = 0.5
#: Signal values are bounded to [0, 1], so their population variance cannot
#: exceed 0.25 and this threshold is never crossed. Kept at the value main has
#: always shipped, deliberately: lowering it (e.g. to 0.10) makes the rule fire
#: for ordinary disagreement between signals, applying a confidence penalty to
#: work that used to be scored normally. That quietly lowers AI scores on real
#: student submissions, which is a false-negative risk, so any move away from
#: 0.3 needs calibration evidence against a labelled set before it ships.
EXTREME_VARIANCE_THRESHOLD = 0.3

#: A medium-risk probability never reports confidence below this floor.
MEDIUM_RISK_CONFIDENCE_FLOOR = 0.3
#: Below this confidence a score is "uncertain".
LOW_CONFIDENCE_FLOOR = 0.2
HIGH_RISK_PROBABILITY = 0.70
#: Cap for an uncertain high score. Damping toward 0.5 by 20% (the old rule)
#: left 0.95 at 0.86, still firmly "High": an uncertain result must not look
#: like a confident one. Mirrors ``apply_fp_safeguards`` in the orchestrator.
LOW_CONFIDENCE_CAP = 0.66


def _average_reliability(reliabilities: dict[str, float]) -> float | None:
    """Mean reliability, or None when there are no reliability scores.

    ``sum(...) / len(...)`` raised ZeroDivisionError on an empty mapping.
    """
    if not reliabilities:
        return None
    return sum(reliabilities.values()) / len(reliabilities)


def compute_penalties(
    signals: SignalScores, reliabilities: dict[str, float]
) -> dict[str, float]:
    """Return the confidence penalty contributed by each safeguard (0.0 if not triggered).

    Dominance, contradiction and variance are judged over the signals that carry
    evidence for this file (see ``agreement``): signals that cannot be measured on a
    short file return 0.0 and used to count as confident human-like votes.
    """
    avg_reliability = _average_reliability(reliabilities)
    return {
        "single_signal_dominance": (
            SINGLE_SIGNAL_PENALTY
            if detect_single_signal_dominance(signals, reliabilities)
            else 0.0
        ),
        "signal_contradiction": (
            CONTRADICTION_PENALTY
            if detect_signal_contradiction(signals, reliabilities)
            else 0.0
        ),
        "low_reliability": (
            LOW_RELIABILITY_PENALTY
            if avg_reliability is not None and avg_reliability < LOW_RELIABILITY_THRESHOLD
            else 0.0
        ),
        "extreme_variance": (
            EXTREME_VARIANCE_PENALTY
            if calculate_signal_variance(signals, reliabilities) > EXTREME_VARIANCE_THRESHOLD
            else 0.0
        ),
    }


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
    adjusted_confidence = confidence - sum(compute_penalties(signals, reliabilities).values())

    # Safeguard 5: Confidence Floor
    # Never allow confidence below threshold for medium risk
    if 0.4 <= ai_probability <= 0.6:
        adjusted_confidence = max(adjusted_confidence, MEDIUM_RISK_CONFIDENCE_FLOOR)

    # Ensure confidence is in [0.0, 1.0]
    adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

    # Safeguard 6: an uncertain result must not look like a confident one.
    if adjusted_confidence < LOW_CONFIDENCE_FLOOR:
        if ai_probability >= HIGH_RISK_PROBABILITY:
            ai_probability = min(ai_probability, LOW_CONFIDENCE_CAP)
        else:
            # Move toward 0.5 (neutral)
            ai_probability = ai_probability * 0.8 + 0.5 * 0.2

    return (
        round(ai_probability, 3),
        round(adjusted_confidence, 3),
    )


def check_single_signal_dominance(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> dict:
    """Check for single signal dominance and return details.

    Args:
        signals: SignalScores object
        reliabilities: Optional reliability scores (unreliable signals are ignored)

    Returns:
        Dictionary with:
        - is_dominant: bool
        - dominant_signal: str (signal name or empty)
        - confidence_penalty: float
        - explanation: str
    """
    is_dominant = detect_single_signal_dominance(signals, reliabilities)
    dominant_signal = get_dominant_signal(signals, reliabilities)

    if is_dominant:
        penalty = SINGLE_SIGNAL_PENALTY
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


def check_signal_contradiction(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> dict:
    """Check for signal contradiction and return details.

    Args:
        signals: SignalScores object
        reliabilities: Optional reliability scores (unreliable signals are ignored)

    Returns:
        Dictionary with:
        - is_contradictory: bool
        - confidence_penalty: float
        - explanation: str
    """
    is_contradictory = detect_signal_contradiction(signals, reliabilities)

    if is_contradictory:
        penalty = CONTRADICTION_PENALTY
        explanation = (
            "Signal contradiction detected: some signals indicate AI-like, "
            f"others indicate human-like. Reducing confidence by {penalty:.0%}."
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
    avg_reliability = _average_reliability(reliabilities)
    if avg_reliability is None:
        return {
            "is_low_reliability": False,
            "avg_reliability": 0.0,
            "confidence_penalty": 0.0,
            "explanation": "No reliability scores available.",
        }
    is_low = avg_reliability < LOW_RELIABILITY_THRESHOLD

    if is_low:
        penalty = LOW_RELIABILITY_PENALTY
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


def check_extreme_variance(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> dict:
    """Check for extreme signal variance and return details.

    Args:
        signals: SignalScores object
        reliabilities: Optional reliability scores (unreliable signals are ignored)

    Returns:
        Dictionary with:
        - is_extreme_variance: bool
        - variance: float
        - confidence_penalty: float
        - explanation: str
    """
    variance = calculate_signal_variance(signals, reliabilities)
    is_extreme = variance > EXTREME_VARIANCE_THRESHOLD

    if is_extreme:
        penalty = EXTREME_VARIANCE_PENALTY
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
        "single_signal_dominance": check_single_signal_dominance(signals, reliabilities),
        "signal_contradiction": check_signal_contradiction(signals, reliabilities),
        "low_reliability": check_low_reliability(reliabilities),
        "extreme_variance": check_extreme_variance(signals, reliabilities),
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
    return min(sum(compute_penalties(signals, reliabilities).values()), 1.0)
