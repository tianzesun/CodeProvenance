"""Fusion orchestrator for AI detection pipeline.

Coordinates all components of the fusion layer:
1. Signal reliability assessment
2. Signal agreement analysis
3. Weighted signal aggregation
4. Confidence calibration
5. False positive reduction
6. Risk categorization
"""

from typing import Dict

from src.backend.engines.ai.agreement import analyze_signal_agreement
from src.backend.engines.ai.aggregation import (
    aggregate_signals_with_agreement,
    get_all_signal_contributions,
    get_most_influential_signals,
)
from src.backend.engines.ai.confidence import calibrate_confidence
from src.backend.engines.ai.false_positive_reduction import (
    apply_false_positive_reduction,
    get_all_false_positive_checks,
)
from src.backend.engines.ai.models import AIDetectionResult, SignalScores
from src.backend.engines.ai.reliability import assess_all_signal_reliabilities


def fuse_signals(
    signals: SignalScores,
    code: str,
    language: str = "python",
) -> Dict:
    """Fuse all signals into final detection result.

    Args:
        signals: SignalScores object with all 8 signal scores
        code: Source code being analyzed
        language: Programming language (default: 'python')

    Returns:
        Dictionary with:
        - ai_probability: Final AI probability [0.0, 1.0]
        - confidence: Confidence in result [0.0, 1.0]
        - risk_level: Risk category
        - agreement: Signal agreement analysis
        - reliabilities: Signal reliability scores
        - contributions: Signal contributions to final score
        - false_positive_checks: Results of FP reduction checks
        - influential_signals: Top 3 most influential signals
    """
    # Step 1: Assess signal reliability
    reliabilities = assess_all_signal_reliabilities(code, language)

    # Step 2: Analyze signal agreement
    agreement = analyze_signal_agreement(signals)

    # Step 3: Aggregate signals with agreement
    ai_probability = aggregate_signals_with_agreement(signals, reliabilities, agreement)

    # Step 4: Calibrate confidence
    confidence = calibrate_confidence(signals, reliabilities, agreement, ai_probability)

    # Step 5: Apply false positive reduction
    ai_probability, confidence = apply_false_positive_reduction(
        ai_probability, confidence, signals, reliabilities
    )

    # Step 6: Categorize risk
    risk_level = _categorize_risk(ai_probability, confidence)

    # Additional analysis
    signal_contributions = get_all_signal_contributions(signals, reliabilities)
    influential_signals = get_most_influential_signals(signals, reliabilities, top_n=3)
    false_positive_checks = get_all_false_positive_checks(signals, reliabilities)

    return {
        "ai_probability": ai_probability,
        "confidence": confidence,
        "risk_level": risk_level,
        "agreement": agreement,
        "reliabilities": reliabilities,
        "signal_contributions": signal_contributions,
        "influential_signals": influential_signals,
        "false_positive_checks": false_positive_checks,
    }


def _categorize_risk(ai_probability: float, confidence: float) -> str:
    """Categorize risk level based on AI probability and confidence.

    Args:
        ai_probability: AI probability in [0.0, 1.0]
        confidence: Confidence in [0.0, 1.0]

    Returns:
        Risk level: "Very Low" / "Low" / "Moderate" / "Elevated" / "High"
    """
    if ai_probability < 0.25:
        return "Very Low"
    elif ai_probability < 0.45:
        return "Low"
    elif ai_probability < 0.65:
        return "Moderate"
    elif ai_probability < 0.80:
        return "Elevated"
    else:
        return "High"


def create_detection_result(
    signals: SignalScores,
    code: str,
    language: str = "python",
    flagged_lines: list = None,
) -> AIDetectionResult:
    """Create a complete detection result from signals.

    Args:
        signals: SignalScores object
        code: Source code being analyzed
        language: Programming language
        flagged_lines: Optional list of flagged line numbers

    Returns:
        AIDetectionResult object
    """
    # Fuse signals
    fusion_result = fuse_signals(signals, code, language)

    # Extract key information
    ai_probability = fusion_result["ai_probability"]
    confidence = fusion_result["confidence"]
    agreement = fusion_result["agreement"]
    influential_signals = fusion_result["influential_signals"]

    # Create signal labels
    signal_labels = {
        "perplexity": "Token Entropy",
        "burstiness": "Line Complexity",
        "stylometry": "Code Style",
        "pattern_library": "LLM Patterns",
        "structural_entropy": "AST Uniformity",
        "vocabulary_richness": "Token Diversity",
        "whitespace_rhythm": "Spacing Rhythm",
        "docstring_density": "Documentation",
    }

    # Create indicators from influential signals
    indicators = []
    for signal_name, contribution in influential_signals:
        if contribution > 0.01:
            indicators.append(f"{signal_labels.get(signal_name, signal_name)}: {contribution:.1%}")

    # Add agreement indicator
    if agreement["agreement_level"] == "high":
        indicators.append(f"High signal agreement ({agreement['agreement_score']:.0%})")
    elif agreement["agreement_level"] == "low":
        indicators.append(f"Low signal agreement ({agreement['agreement_score']:.0%})")

    # Create result
    result = AIDetectionResult(
        ai_probability=ai_probability,
        confidence=confidence,
        signals=signals,
        signal_labels=signal_labels,
        indicators=indicators[:6],  # Limit to 6 indicators
        flagged_lines=flagged_lines or [],
        language=language,
    )

    return result


def get_fusion_summary(fusion_result: Dict) -> str:
    """Get human-readable summary of fusion result.

    Args:
        fusion_result: Result from fuse_signals()

    Returns:
        Summary string
    """
    ai_prob = fusion_result["ai_probability"]
    confidence = fusion_result["confidence"]
    risk_level = fusion_result["risk_level"]
    agreement = fusion_result["agreement"]

    summary = (
        f"AI Probability: {ai_prob:.1%} | "
        f"Confidence: {confidence:.1%} | "
        f"Risk: {risk_level} | "
        f"Agreement: {agreement['agreement_level'].capitalize()}"
    )

    return summary
