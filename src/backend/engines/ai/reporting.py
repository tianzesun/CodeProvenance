"""Report generation for AI detection results.

Generates comprehensive, instructor-facing reports with:
- Executive summary
- Signal breakdown
- Agreement analysis
- Evidence summary
- Limitations and caveats
"""

from datetime import datetime

from src.backend.engines.ai.agreement import analyze_signal_agreement
from src.backend.engines.ai.models import AIDetectionResult, SignalScores
from src.backend.engines.ai.reliability import assess_all_signal_reliabilities


def generate_detection_report(
    result: AIDetectionResult,
    code: str,
    language: str = "python",
) -> dict:
    """Generate comprehensive detection report.

    Args:
        result: Detection result
        code: Source code analyzed
        language: Programming language

    Returns:
        Dictionary with complete report
    """
    signals = result.signals
    reliabilities = assess_all_signal_reliabilities(code, language)
    agreement = analyze_signal_agreement(signals)

    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "language": language,
            "code_length": len(code),
            "code_lines": len(code.splitlines()),
        },
        "executive_summary": generate_executive_summary(result),
        "overall_assessment": generate_overall_assessment(result),
        "signal_breakdown": generate_signal_breakdown(signals, reliabilities),
        "agreement_analysis": generate_agreement_analysis(agreement),
        "evidence_summary": generate_evidence_summary(result, code),
        "limitations": generate_limitations_section(),
        "recommendations": generate_recommendations(result),
    }

    return report


def generate_executive_summary(result: AIDetectionResult) -> dict:
    """Generate executive summary section.

    Args:
        result: Detection result

    Returns:
        Executive summary dictionary
    """
    return {
        "overall_risk": result.risk_level,
        "ai_probability": f"{result.ai_probability:.1%}",
        "confidence": f"{result.confidence:.1%}",
        "summary": _get_risk_summary(result),
        "key_findings": result.indicators[:3],  # Top 3 indicators
    }


def _get_risk_summary(result: AIDetectionResult) -> str:
    """Get human-readable risk summary.

    Args:
        result: Detection result

    Returns:
        Summary string
    """
    if result.risk_level == "Very Low":
        return (
            "This submission shows minimal indicators of AI-generated code. "
            "The code exhibits characteristics typical of human-written work."
        )
    elif result.risk_level == "Low":
        return (
            "This submission shows few indicators of AI-generated code. "
            "While some signals are present, they are not conclusive."
        )
    elif result.risk_level == "Moderate":
        return (
            "This submission shows moderate indicators of AI-generated code. "
            "Further investigation may be warranted."
        )
    elif result.risk_level == "Elevated":
        return (
            "This submission shows elevated indicators of AI-generated code. "
            "Instructor review is recommended."
        )
    else:  # High
        return (
            "This submission shows strong indicators of AI-generated code. "
            "Immediate instructor review is recommended."
        )


def generate_overall_assessment(result: AIDetectionResult) -> dict:
    """Generate overall assessment section.

    Args:
        result: Detection result

    Returns:
        Overall assessment dictionary
    """
    return {
        "risk_level": result.risk_level,
        "ai_probability": result.ai_probability,
        "confidence": result.confidence,
        "confidence_level": _get_confidence_level(result.confidence),
        "recommendation": _get_recommendation(result),
    }


def _get_confidence_level(confidence: float) -> str:
    """Get confidence level label.

    Args:
        confidence: Confidence score

    Returns:
        Confidence level string
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


def _get_recommendation(result: AIDetectionResult) -> str:
    """Get recommendation based on result.

    Args:
        result: Detection result

    Returns:
        Recommendation string
    """
    if result.risk_level == "High" and result.confidence >= 0.7:
        return "Strong evidence of AI generation. Recommend immediate review."
    elif result.risk_level in ["Elevated", "Moderate"] and result.confidence >= 0.6:
        return "Moderate evidence of AI generation. Recommend review."
    elif result.risk_level == "Low" or result.confidence < 0.4:
        return "Insufficient evidence of AI generation. No action needed."
    else:
        return "Mixed signals. Manual review recommended."


def generate_signal_breakdown(
    signals: SignalScores,
    reliabilities: dict[str, float],
) -> dict:
    """Generate signal breakdown section.

    Args:
        signals: Signal scores
        reliabilities: Signal reliability scores

    Returns:
        Signal breakdown dictionary
    """
    signal_dict = signals.to_dict()
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

    breakdown = {}
    for signal_name, score in signal_dict.items():
        reliability = reliabilities.get(signal_name, 0.5)
        label = signal_labels.get(signal_name, signal_name)

        breakdown[signal_name] = {
            "label": label,
            "score": f"{score:.1%}",
            "reliability": f"{reliability:.1%}",
            "interpretation": _interpret_signal(signal_name, score),
        }

    return breakdown


def _interpret_signal(signal_name: str, score: float) -> str:
    """Interpret a signal score.

    Args:
        signal_name: Name of the signal
        score: Signal score

    Returns:
        Interpretation string
    """
    if score > 0.7:
        indicator = "Strong AI indicator"
    elif score > 0.5:
        indicator = "Moderate AI indicator"
    elif score > 0.3:
        indicator = "Weak AI indicator"
    else:
        indicator = "Human-like"

    return indicator


def generate_agreement_analysis(agreement: dict) -> dict:
    """Generate signal agreement analysis section.

    Args:
        agreement: Agreement analysis dictionary

    Returns:
        Agreement analysis dictionary
    """
    return {
        "agreement_level": agreement["agreement_level"],
        "agreement_score": f"{agreement['agreement_score']:.1%}",
        "direction": agreement["direction"],
        "supporting_signals": len(agreement["supporting_signals"]),
        "contradicting_signals": len(agreement["contradicting_signals"]),
        "neutral_signals": len(agreement["neutral_signals"]),
        "interpretation": _interpret_agreement(agreement),
    }


def _interpret_agreement(agreement: dict) -> str:
    """Interpret signal agreement.

    Args:
        agreement: Agreement analysis dictionary

    Returns:
        Interpretation string
    """
    level = agreement["agreement_level"]
    direction = agreement["direction"]

    if level == "high":
        if direction == "ai_like":
            return "Signals strongly agree on AI-like characteristics."
        else:
            return "Signals strongly agree on human-like characteristics."
    elif level == "medium":
        return "Signals show moderate agreement with some variation."
    else:
        return "Signals show low agreement with significant variation."


def generate_evidence_summary(result: AIDetectionResult, code: str) -> dict:
    """Generate evidence summary section.

    Args:
        result: Detection result
        code: Source code

    Returns:
        Evidence summary dictionary
    """
    return {
        "indicators": result.indicators,
        "flagged_lines": result.flagged_lines,
        "flagged_lines_count": len(result.flagged_lines),
        "total_lines": len(code.splitlines()),
        "flagged_percentage": (
            f"{len(result.flagged_lines) / max(1, len(code.splitlines())) * 100:.1f}%"
        ),
    }


def generate_limitations_section() -> dict:
    """Generate limitations section.

    Returns:
        Limitations dictionary
    """
    return {
        "title": "Important Limitations",
        "limitations": [
            (
                "This analysis detects patterns associated with AI-generated code, "
                "but cannot definitively prove AI generation."
            ),
            (
                "False positives can occur with code that happens to match AI patterns "
                "(e.g., well-documented code, code following best practices)."
            ),
            (
                "False negatives can occur with AI code that is heavily modified "
                "or uses uncommon patterns."
            ),
            (
                "The detector is calibrated for Python code. Results for other languages "
                "may be less reliable."
            ),
            (
                "This tool should be used as one factor in academic integrity assessment, "
                "not as the sole determinant."
            ),
            (
                "Student context matters: code written during office hours, with instructor "
                "guidance, or using AI as a learning tool may legitimately show AI patterns."
            ),
        ],
        "recommendations": [
            "Use this report as a starting point for instructor investigation.",
            "Consider the student's prior work and coding patterns.",
            "Conduct interviews or code walkthroughs to verify understanding.",
            "Review submission metadata (timestamps, edit history) if available.",
            "Consider institutional policies on AI tool usage.",
        ],
    }


def generate_recommendations(result: AIDetectionResult) -> dict:
    """Generate recommendations section.

    Args:
        result: Detection result

    Returns:
        Recommendations dictionary
    """
    recommendations = []

    if result.risk_level == "High":
        recommendations.append(
            "Schedule a meeting with the student to discuss the submission."
        )
        recommendations.append(
            "Ask the student to explain their code and problem-solving approach."
        )
        recommendations.append(
            "Consider requesting a code walkthrough or live coding demonstration."
        )

    elif result.risk_level == "Elevated":
        recommendations.append(
            "Review the submission more carefully for signs of AI generation."
        )
        recommendations.append(
            "Compare with the student's previous submissions for style changes."
        )
        recommendations.append("Consider asking clarifying questions about the code.")

    elif result.risk_level == "Moderate":
        recommendations.append(
            "Note the moderate indicators but do not take action without additional evidence."
        )
        recommendations.append("Monitor the student's future submissions for patterns.")

    else:
        recommendations.append("No action needed based on AI detection analysis.")

    return {
        "risk_level": result.risk_level,
        "recommendations": recommendations,
    }


def format_report_as_text(report: dict) -> str:
    """Format report as human-readable text.

    Args:
        report: Report dictionary

    Returns:
        Formatted text report
    """
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("AI DETECTION REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Metadata
    metadata = report["metadata"]
    lines.append(f"Generated: {metadata['generated_at']}")
    lines.append(f"Language: {metadata['language']}")
    lines.append(
        f"Code Length: {metadata['code_length']} characters, {metadata['code_lines']} lines"
    )
    lines.append("")

    # Executive Summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 80)
    summary = report["executive_summary"]
    lines.append(f"Overall Risk: {summary['overall_risk']}")
    lines.append(f"AI Probability: {summary['ai_probability']}")
    lines.append(f"Confidence: {summary['confidence']}")
    lines.append(f"Summary: {summary['summary']}")
    lines.append("")

    # Overall Assessment
    lines.append("OVERALL ASSESSMENT")
    lines.append("-" * 80)
    assessment = report["overall_assessment"]
    lines.append(f"Risk Level: {assessment['risk_level']}")
    lines.append(f"Confidence Level: {assessment['confidence_level']}")
    lines.append(f"Recommendation: {assessment['recommendation']}")
    lines.append("")

    # Signal Breakdown
    lines.append("SIGNAL BREAKDOWN")
    lines.append("-" * 80)
    for signal_info in report["signal_breakdown"].values():
        lines.append(
            f"{signal_info['label']}: {signal_info['score']} "
            f"(Reliability: {signal_info['reliability']}) - {signal_info['interpretation']}"
        )
    lines.append("")

    # Agreement Analysis
    lines.append("SIGNAL AGREEMENT ANALYSIS")
    lines.append("-" * 80)
    agreement = report["agreement_analysis"]
    lines.append(f"Agreement Level: {agreement['agreement_level']}")
    lines.append(f"Agreement Score: {agreement['agreement_score']}")
    lines.append(f"Direction: {agreement['direction']}")
    lines.append(f"Supporting Signals: {agreement['supporting_signals']}")
    lines.append(f"Contradicting Signals: {agreement['contradicting_signals']}")
    lines.append(f"Interpretation: {agreement['interpretation']}")
    lines.append("")

    # Evidence Summary
    lines.append("EVIDENCE SUMMARY")
    lines.append("-" * 80)
    evidence = report["evidence_summary"]
    lines.append(
        f"Flagged Lines: {evidence['flagged_lines_count']} / {evidence['total_lines']} ({evidence['flagged_percentage']})"
    )
    if evidence["indicators"]:
        lines.append("Key Indicators:")
        for indicator in evidence["indicators"][:5]:
            lines.append(f"  - {indicator}")
    lines.append("")

    # Limitations
    lines.append("IMPORTANT LIMITATIONS")
    lines.append("-" * 80)
    limitations = report["limitations"]
    for limitation in limitations["limitations"]:
        lines.append(f"• {limitation}")
    lines.append("")

    # Recommendations
    lines.append("RECOMMENDATIONS")
    lines.append("-" * 80)
    recommendations = report["recommendations"]
    for rec in recommendations["recommendations"]:
        lines.append(f"• {rec}")
    lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)
