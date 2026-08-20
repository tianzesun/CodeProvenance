"""Signal agreement analysis framework.

Detects when signals agree or contradict each other.
Agreement analysis is used to adjust confidence during aggregation.

Agreement levels:
- High: 6+ signals in same direction
- Medium: 4-5 signals in same direction
- Low: 3 or fewer signals in same direction
"""

from src.backend.engines.ai.models import SignalScores


def analyze_signal_agreement(signals: SignalScores) -> dict:
    """Analyze agreement between signals.

    Args:
        signals: SignalScores object with all 8 signal scores

    Returns:
        Dictionary with:
        - agreement_level: "high" / "medium" / "low"
        - supporting_signals: List of signals > 0.6 (AI-like)
        - contradicting_signals: List of signals < 0.4 (human-like)
        - neutral_signals: List of signals 0.4-0.6 (neutral)
        - agreement_score: 0.0-1.0 (how much signals agree)
        - direction: "ai_like" / "human_like" / "mixed"
    """
    signal_dict = signals.to_dict()

    # Categorize signals
    supporting = []  # > 0.6 (AI-like)
    contradicting = []  # < 0.4 (human-like)
    neutral = []  # 0.4-0.6 (neutral)

    for signal_name, score in signal_dict.items():
        if score > 0.6:
            supporting.append((signal_name, score))
        elif score < 0.4:
            contradicting.append((signal_name, score))
        else:
            neutral.append((signal_name, score))

    # Determine agreement level
    total_signals = len(signal_dict)
    max_agreement_count = max(len(supporting), len(contradicting))

    if max_agreement_count >= 6:
        agreement_level = "high"
    elif max_agreement_count >= 4:
        agreement_level = "medium"
    else:
        agreement_level = "low"

    # Determine direction
    if len(supporting) > len(contradicting):
        direction = "ai_like"
    elif len(contradicting) > len(supporting):
        direction = "human_like"
    else:
        direction = "mixed"

    # Calculate agreement score
    # High agreement when signals cluster together
    agreement_score = max_agreement_count / total_signals

    return {
        "agreement_level": agreement_level,
        "supporting_signals": supporting,
        "contradicting_signals": contradicting,
        "neutral_signals": neutral,
        "agreement_score": round(agreement_score, 3),
        "direction": direction,
        "supporting_count": len(supporting),
        "contradicting_count": len(contradicting),
        "neutral_count": len(neutral),
    }


def get_agreement_confidence_adjustment(agreement: dict) -> float:
    """Get confidence adjustment based on signal agreement.

    Args:
        agreement: Agreement analysis dictionary

    Returns:
        Confidence adjustment factor in [-0.3, 0.2]:
        - Positive: increase confidence (signals agree)
        - Negative: decrease confidence (signals contradict)
    """
    agreement_level = agreement["agreement_level"]
    supporting_count = agreement["supporting_count"]
    contradicting_count = agreement["contradicting_count"]

    if agreement_level == "high":
        # High agreement: increase confidence
        return 0.2
    elif agreement_level == "medium":
        # Medium agreement: slight increase
        return 0.1
    else:
        # Low agreement: check for contradiction
        if supporting_count > 0 and contradicting_count > 0:
            # Signals contradict: decrease confidence
            return -0.2
        else:
            # Signals are neutral: no adjustment
            return 0.0


def detect_signal_contradiction(signals: SignalScores) -> bool:
    """Detect if signals contradict each other.

    Contradiction occurs when:
    - Some signals > 0.7 (strong AI-like)
    - Some signals < 0.3 (strong human-like)

    Args:
        signals: SignalScores object

    Returns:
        True if signals contradict, False otherwise
    """
    signal_dict = signals.to_dict()

    strong_ai = sum(1 for s in signal_dict.values() if s > 0.7)
    strong_human = sum(1 for s in signal_dict.values() if s < 0.3)

    return strong_ai > 0 and strong_human > 0


def detect_single_signal_dominance(signals: SignalScores) -> bool:
    """Detect if a single signal dominates the others.

    Dominance occurs when:
    - Only 1 signal > 0.6 (AI-like)
    - All other signals < 0.4 (human-like)

    Args:
        signals: SignalScores object

    Returns:
        True if single signal dominates, False otherwise
    """
    signal_dict = signals.to_dict()

    ai_like = sum(1 for s in signal_dict.values() if s > 0.6)
    human_like = sum(1 for s in signal_dict.values() if s < 0.4)

    # Single signal dominance: 1 AI-like, 7 human-like (or vice versa)
    return (ai_like == 1 and human_like >= 6) or (human_like == 1 and ai_like >= 6)


def get_dominant_signal(signals: SignalScores) -> str:
    """Get the name of the dominant signal if one exists.

    Args:
        signals: SignalScores object

    Returns:
        Name of dominant signal, or empty string if no dominance
    """
    signal_dict = signals.to_dict()

    # Find signals that stand out
    ai_like = [(name, score) for name, score in signal_dict.items() if score > 0.6]
    human_like = [(name, score) for name, score in signal_dict.items() if score < 0.4]

    if len(ai_like) == 1 and len(human_like) >= 6:
        return ai_like[0][0]
    elif len(human_like) == 1 and len(ai_like) >= 6:
        return human_like[0][0]
    else:
        return ""


def calculate_signal_variance(signals: SignalScores) -> float:
    """Calculate variance of signal scores.

    Args:
        signals: SignalScores object

    Returns:
        Variance of signal scores in [0.0, 0.25]
    """
    signal_dict = signals.to_dict()
    scores = list(signal_dict.values())

    if len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)

    # Normalize to [0.0, 0.25]
    return min(variance, 0.25)
