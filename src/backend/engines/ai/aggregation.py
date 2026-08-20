"""Signal aggregation framework.

Combines signals with weights and reliability adjustments to produce
a final AI probability score.

Algorithm:
1. Adjust each signal by reliability: adjusted = signal * reliability
2. Apply weights: weighted = adjusted * weight
3. Sum: final = Σ(weighted)
4. Normalize: final = final / Σ(reliability * weight)
"""

from src.backend.engines.ai.models import SignalScores


def aggregate_signals(signals: SignalScores, reliabilities: dict[str, float]) -> float:
    """Aggregate signals with weights and reliability adjustments.

    Args:
        signals: SignalScores object with all 8 signal scores
        reliabilities: Dictionary mapping signal names to reliability scores

    Returns:
        Final AI probability score in [0.0, 1.0]
    """
    signal_dict = signals.to_dict()
    weights = SignalScores.WEIGHTS

    # Calculate weighted sum with reliability adjustments
    weighted_sum = 0.0
    normalization_factor = 0.0

    for signal_name, score in signal_dict.items():
        reliability = reliabilities.get(signal_name, 0.5)
        weight = weights.get(signal_name, 0.0)

        # Adjust signal by reliability
        adjusted_score = score * reliability

        # Apply weight
        weighted_score = adjusted_score * weight

        weighted_sum += weighted_score
        normalization_factor += reliability * weight

    # Normalize
    if normalization_factor > 0:
        final_score = weighted_sum / normalization_factor
    else:
        final_score = 0.0

    # Ensure score is in [0.0, 1.0]
    return round(max(0.0, min(1.0, final_score)), 3)


def aggregate_signals_with_agreement(
    signals: SignalScores,
    reliabilities: dict[str, float],
    agreement: dict,
) -> float:
    """Aggregate signals with agreement-based adjustments.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores
        agreement: Agreement analysis dictionary

    Returns:
        Final AI probability score in [0.0, 1.0]
    """
    # Get base aggregation
    base_score = aggregate_signals(signals, reliabilities)

    # Apply agreement-based adjustment
    agreement_level = agreement["agreement_level"]
    supporting_count = agreement["supporting_count"]
    contradicting_count = agreement["contradicting_count"]

    if agreement_level == "high":
        # High agreement: boost score toward direction
        if supporting_count > contradicting_count:
            # Boost toward AI-like
            adjustment = 0.05
        else:
            # Boost toward human-like
            adjustment = -0.05
    elif agreement_level == "medium":
        # Medium agreement: slight adjustment
        if supporting_count > contradicting_count:
            adjustment = 0.02
        else:
            adjustment = -0.02
    else:
        # Low agreement: no adjustment
        adjustment = 0.0

    final_score = base_score + adjustment
    return round(max(0.0, min(1.0, final_score)), 3)


def get_signal_contribution(
    signal_name: str,
    signal_score: float,
    reliability: float,
) -> float:
    """Calculate the contribution of a single signal to final score.

    Args:
        signal_name: Name of the signal
        signal_score: Score of the signal [0.0, 1.0]
        reliability: Reliability of the signal [0.0, 1.0]

    Returns:
        Contribution to final score
    """
    weights = SignalScores.WEIGHTS
    weight = weights.get(signal_name, 0.0)

    # Contribution = signal * reliability * weight
    contribution = signal_score * reliability * weight

    return round(contribution, 4)


def get_all_signal_contributions(
    signals: SignalScores, reliabilities: dict[str, float]
) -> dict[str, float]:
    """Calculate contributions of all signals.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores

    Returns:
        Dictionary mapping signal names to contributions
    """
    signal_dict = signals.to_dict()

    contributions = {}
    for signal_name, score in signal_dict.items():
        reliability = reliabilities.get(signal_name, 0.5)
        contribution = get_signal_contribution(signal_name, score, reliability)
        contributions[signal_name] = contribution

    return contributions


def get_most_influential_signals(
    signals: SignalScores, reliabilities: dict[str, float], top_n: int = 3
) -> list:
    """Get the most influential signals in the aggregation.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores
        top_n: Number of top signals to return

    Returns:
        List of (signal_name, contribution) tuples, sorted by contribution
    """
    contributions = get_all_signal_contributions(signals, reliabilities)

    # Sort by absolute contribution
    sorted_signals = sorted(
        contributions.items(), key=lambda x: abs(x[1]), reverse=True
    )

    return sorted_signals[:top_n]
