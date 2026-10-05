"""Signal aggregation framework.

Combines signals with weights and reliability adjustments to produce
a final AI probability score.

Algorithm:
1. Adjust each signal by reliability: adjusted = signal * reliability
2. Apply weights: weighted = adjusted * weight
3. Sum: final = Σ(weighted)
4. Normalize: final = final / Σ(reliability * weight)

i.e. the final score is the reliability-weighted mean of the signals. A signal
with zero reliability contributes nothing to either side of the division.
"""

from src.backend.engines.ai.models import SignalScores

#: Adjustment applied by agreement level when the signals cluster on one side.
HIGH_AGREEMENT_ADJUSTMENT = 0.05
MEDIUM_AGREEMENT_ADJUSTMENT = 0.02


def aggregate_signals(signals: SignalScores, reliabilities: dict[str, float]) -> float:
    """Aggregate signals with weights and reliability adjustments.

    Args:
        signals: SignalScores object with all 8 signal scores
        reliabilities: Dictionary mapping signal names to reliability scores

    Returns:
        Final AI probability score in [0.0, 1.0]. When no signal has any
        reliability there is no evidence and the score is 0.0.
    """
    weights = SignalScores.WEIGHTS

    weighted_sum = 0.0
    normalization_factor = 0.0
    for signal_name, score in signals.to_dict().items():
        reliability = reliabilities.get(signal_name, 0.5)
        weight = weights.get(signal_name, 0.0)
        weighted_sum += score * reliability * weight
        normalization_factor += reliability * weight

    final_score = weighted_sum / normalization_factor if normalization_factor > 0 else 0.0
    return round(max(0.0, min(1.0, final_score)), 3)


def _agreement_adjustment(agreement: dict) -> float:
    """Score adjustment toward the direction the signals agree on."""
    level = agreement["agreement_level"]
    supporting = agreement["supporting_count"]
    contradicting = agreement["contradicting_count"]

    if level == "high":
        magnitude = HIGH_AGREEMENT_ADJUSTMENT
    elif level == "medium":
        magnitude = MEDIUM_AGREEMENT_ADJUSTMENT
    else:
        return 0.0

    # A tie pushes toward neither side. It used to fall into the "else" branch and
    # nudge the score toward human on every 4-4 split.
    if supporting > contradicting:
        return magnitude
    if contradicting > supporting:
        return -magnitude
    return 0.0


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
    final_score = aggregate_signals(signals, reliabilities) + _agreement_adjustment(agreement)
    return round(max(0.0, min(1.0, final_score)), 3)


def get_signal_contribution(
    signal_name: str,
    signal_score: float,
    reliability: float,
) -> float:
    """Calculate the RAW contribution of a single signal (score * reliability * weight).

    This is not normalised by the reliability-weighted weight total, so values from
    different files are not comparable; see :func:`get_all_signal_contributions`.

    Args:
        signal_name: Name of the signal
        signal_score: Score of the signal [0.0, 1.0]
        reliability: Reliability of the signal [0.0, 1.0]

    Returns:
        Raw contribution
    """
    weight = SignalScores.WEIGHTS.get(signal_name, 0.0)
    return round(signal_score * reliability * weight, 4)


def get_all_signal_contributions(
    signals: SignalScores,
    reliabilities: dict[str, float],
    normalize: bool = True,
) -> dict[str, float]:
    """Calculate contributions of all signals.

    With ``normalize`` (the default) each contribution is divided by
    Σ(reliability * weight), so the contributions SUM TO the base aggregate score
    and each one is that signal's share of it. The raw values summed to less than
    the score (by a file-dependent factor), and the indicator text built from them
    ("Token Entropy: 12.0%") understated every signal.

    Args:
        signals: SignalScores object
        reliabilities: Dictionary of reliability scores
        normalize: Return shares of the aggregate score instead of raw products

    Returns:
        Dictionary mapping signal names to contributions
    """
    weights = SignalScores.WEIGHTS
    raw: dict[str, float] = {}
    total_weight = 0.0
    for signal_name, score in signals.to_dict().items():
        reliability = reliabilities.get(signal_name, 0.5)
        raw[signal_name] = score * reliability * weights.get(signal_name, 0.0)
        total_weight += reliability * weights.get(signal_name, 0.0)

    if normalize:
        if total_weight <= 0:
            return {name: 0.0 for name in raw}
        return {name: round(value / total_weight, 4) for name, value in raw.items()}
    return {name: round(value, 4) for name, value in raw.items()}


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
    return sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
