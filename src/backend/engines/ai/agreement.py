"""Signal agreement analysis framework.

Detects when signals agree or contradict each other.
Agreement analysis is used to adjust confidence during aggregation.

Agreement levels (as a share of the signals that carry evidence):
- High: at least 75% in the same direction (6+ of 8)
- Medium: at least 50% in the same direction (4-5 of 8)
- Low: fewer

Reliability awareness
---------------------
Several signals return 0.0 when the file is too small to measure them (see
``reliability``). 0.0 reads as "human-like", so a short file used to look like a
unanimous human verdict, and one AI-like signal among that silence triggered the
"single signal dominance" penalty. Every function here takes an optional
``reliabilities`` mapping; signals below ``RELIABILITY_FLOOR`` are then ignored.
Without it the behaviour is exactly as before (all eight signals count).
"""

from src.backend.engines.ai.models import SignalScores

#: A signal whose reliability is below this carries no evidence for this file.
RELIABILITY_FLOOR = 0.25

AI_LIKE_ABOVE = 0.6
HUMAN_LIKE_BELOW = 0.4
STRONG_AI_ABOVE = 0.7
STRONG_HUMAN_BELOW = 0.3
#: Fewer evidence-carrying signals than this cannot establish agreement or dominance.
MIN_ACTIVE_SIGNALS = 4


def active_signal_scores(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> dict[str, float]:
    """The signals that carry evidence (all of them when no reliabilities are given)."""
    scores = signals.to_dict()
    if reliabilities is None:
        return scores
    return {
        name: score
        for name, score in scores.items()
        if reliabilities.get(name, 0.5) >= RELIABILITY_FLOOR
    }


def _high_min(n: int) -> int:
    """Signals needed for "high" agreement: ceil(75% of n) (6 of 8)."""
    return (3 * n + 3) // 4


def _medium_min(n: int) -> int:
    """Signals needed for "medium" agreement: ceil(50% of n) (4 of 8)."""
    return (n + 1) // 2


def analyze_signal_agreement(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> dict:
    """Analyze agreement between signals.

    Args:
        signals: SignalScores object with all 8 signal scores
        reliabilities: Optional per-signal reliability; unreliable signals are ignored

    Returns:
        Dictionary with:
        - agreement_level: "high" / "medium" / "low"
        - supporting_signals: List of signals > 0.6 (AI-like)
        - contradicting_signals: List of signals < 0.4 (human-like)
        - neutral_signals: List of signals 0.4-0.6 (neutral)
        - agreement_score: 0.0-1.0 (how much signals agree)
        - direction: "ai_like" / "human_like" / "mixed"
        - active_signals: how many signals carried evidence
    """
    signal_dict = active_signal_scores(signals, reliabilities)

    supporting = []  # > 0.6 (AI-like)
    contradicting = []  # < 0.4 (human-like)
    neutral = []  # 0.4-0.6 (neutral)

    for signal_name, score in signal_dict.items():
        if score > AI_LIKE_ABOVE:
            supporting.append((signal_name, score))
        elif score < HUMAN_LIKE_BELOW:
            contradicting.append((signal_name, score))
        else:
            neutral.append((signal_name, score))

    total_signals = len(signal_dict)
    max_agreement_count = max(len(supporting), len(contradicting))

    if total_signals < MIN_ACTIVE_SIGNALS:
        agreement_level = "low"
    elif max_agreement_count >= _high_min(total_signals):
        agreement_level = "high"
    elif max_agreement_count >= _medium_min(total_signals):
        agreement_level = "medium"
    else:
        agreement_level = "low"

    if len(supporting) > len(contradicting):
        direction = "ai_like"
    elif len(contradicting) > len(supporting):
        direction = "human_like"
    else:
        direction = "mixed"

    # How much of the evidence-carrying signal set clusters on one side. (An empty
    # set used to be a ZeroDivisionError risk once signals can be excluded.)
    agreement_score = max_agreement_count / total_signals if total_signals else 0.0

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
        "active_signals": total_signals,
    }


def get_agreement_confidence_adjustment(agreement: dict) -> float:
    """Get confidence adjustment based on signal agreement.

    Args:
        agreement: Agreement analysis dictionary

    Returns:
        Confidence adjustment factor in [-0.2, 0.2]:
        - Positive: increase confidence (signals agree)
        - Negative: decrease confidence (signals contradict)
    """
    agreement_level = agreement["agreement_level"]
    supporting_count = agreement["supporting_count"]
    contradicting_count = agreement["contradicting_count"]

    if agreement_level == "high":
        return 0.2
    elif agreement_level == "medium":
        return 0.1
    elif supporting_count > 0 and contradicting_count > 0:
        # Low agreement with signals pulling both ways
        return -0.2
    return 0.0


def detect_signal_contradiction(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> bool:
    """Detect if signals contradict each other.

    Contradiction occurs when:
    - Some signals > 0.7 (strong AI-like)
    - Some signals < 0.3 (strong human-like)

    Args:
        signals: SignalScores object
        reliabilities: Optional per-signal reliability; unreliable signals are ignored

    Returns:
        True if signals contradict, False otherwise
    """
    scores = active_signal_scores(signals, reliabilities).values()
    strong_ai = sum(1 for s in scores if s > STRONG_AI_ABOVE)
    strong_human = sum(1 for s in scores if s < STRONG_HUMAN_BELOW)
    return strong_ai > 0 and strong_human > 0


def _dominance(
    signals: SignalScores, reliabilities: dict[str, float] | None
) -> tuple[str, str]:
    """Return (dominance kind, signal name): kind is "ai", "human" or "" when none.

    One signal stands against nearly all the others: exactly one on one side and
    at least ``n - 2`` on the other (6 of the remaining 7 when all eight carry
    evidence). Needs at least ``MIN_ACTIVE_SIGNALS`` signals.
    """
    scores = active_signal_scores(signals, reliabilities)
    n = len(scores)
    if n < MIN_ACTIVE_SIGNALS:
        return "", ""
    ai_like = [name for name, s in scores.items() if s > AI_LIKE_ABOVE]
    human_like = [name for name, s in scores.items() if s < HUMAN_LIKE_BELOW]
    if len(ai_like) == 1 and len(human_like) >= n - 2:
        return "ai", ai_like[0]
    if len(human_like) == 1 and len(ai_like) >= n - 2:
        return "human", human_like[0]
    return "", ""


def detect_single_signal_dominance(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> bool:
    """Detect if a single signal dominates the others.

    Dominance occurs when:
    - Only 1 signal > 0.6 (AI-like)
    - All but at most one of the others < 0.4 (human-like)
    (or vice versa)

    Args:
        signals: SignalScores object
        reliabilities: Optional per-signal reliability; unreliable signals are ignored

    Returns:
        True if single signal dominates, False otherwise
    """
    return bool(_dominance(signals, reliabilities)[0])


def get_dominant_signal(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> str:
    """Get the name of the dominant signal if one exists.

    Args:
        signals: SignalScores object
        reliabilities: Optional per-signal reliability; unreliable signals are ignored

    Returns:
        Name of dominant signal, or empty string if no dominance
    """
    return _dominance(signals, reliabilities)[1]


def calculate_signal_variance(
    signals: SignalScores, reliabilities: dict[str, float] | None = None
) -> float:
    """Calculate (population) variance of signal scores.

    Args:
        signals: SignalScores object
        reliabilities: Optional per-signal reliability; unreliable signals are ignored

    Returns:
        Variance of signal scores in [0.0, 0.25] (the maximum possible for values in [0, 1])
    """
    scores = list(active_signal_scores(signals, reliabilities).values())
    if len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    return min(variance, 0.25)
