"""AI Detection Pipeline - Complete end-to-end orchestration.

Coordinates all components of the AI detection system:
1. Signal computation
2. Fusion and calibration
3. Report generation
4. Evidence annotation
"""

import logging

from src.backend.engines.ai.fusion import create_detection_result
from src.backend.engines.ai.models import AIDetectionResult, SignalScores
from src.backend.engines.ai.signals import (
    compute_burstiness_signal,
    compute_docstring_density_signal,
    compute_pattern_library_signal,
    compute_perplexity_signal,
    compute_structural_entropy_signal,
    compute_stylometry_signal,
    compute_vocabulary_richness_signal,
    compute_whitespace_rhythm_signal,
)

logger = logging.getLogger(__name__)


def detect_ai_generated_code(
    code: str,
    language: str = "python",
    include_evidence: bool = True,
) -> AIDetectionResult:
    """Complete AI detection pipeline.

    Args:
        code: Source code to analyze
        language: Programming language (default: 'python')
        include_evidence: Whether to include evidence annotation

    Returns:
        AIDetectionResult with detection scores and confidence
    """
    # Step 1: Compute all signals
    signals = compute_all_signals(code, language)

    # Step 2: Create detection result with fusion
    result = create_detection_result(signals, code, language)

    # Step 3: Annotate evidence if requested
    if include_evidence:
        result = annotate_evidence(result, code, signals)

    return result


def compute_all_signals(code: str, language: str = "python") -> SignalScores:
    """Compute all 8 signals for given code.

    Args:
        code: Source code to analyze
        language: Programming language

    Returns:
        SignalScores object with all 8 signal scores
    """
    try:
        perplexity = compute_perplexity_signal(code)
        burstiness = compute_burstiness_signal(code)
        stylometry = compute_stylometry_signal(code)
        pattern_library = compute_pattern_library_signal(code)
        structural_entropy = compute_structural_entropy_signal(code, language)
        vocabulary_richness = compute_vocabulary_richness_signal(code)
        whitespace_rhythm = compute_whitespace_rhythm_signal(code)
        docstring_density = compute_docstring_density_signal(code)

        signals = SignalScores(
            perplexity=perplexity,
            burstiness=burstiness,
            stylometry=stylometry,
            pattern_library=pattern_library,
            structural_entropy=structural_entropy,
            vocabulary_richness=vocabulary_richness,
            whitespace_rhythm=whitespace_rhythm,
            docstring_density=docstring_density,
        )

        return signals

    except Exception as e:
        logger.error(f"Error computing signals: {e}")
        # Return neutral signals on error
        return SignalScores()


def annotate_evidence(
    result: AIDetectionResult,
    code: str,
    signals: SignalScores,
) -> AIDetectionResult:
    """Annotate evidence for detection result.

    Args:
        result: Detection result to annotate
        code: Source code
        signals: Signal scores

    Returns:
        Updated detection result with evidence annotation
    """
    # Find lines with LLM patterns
    flagged_lines = find_llm_pattern_lines(code)

    # Update result with flagged lines
    result.flagged_lines = flagged_lines[:30]  # Limit to 30 lines

    return result


def find_llm_pattern_lines(code: str, max_lines: int = 30) -> list[int]:
    """Find lines with LLM-specific patterns.

    Args:
        code: Source code to analyze
        max_lines: Maximum number of lines to return

    Returns:
        List of line numbers (1-indexed) with LLM patterns
    """
    import re

    # LLM pattern indicators
    patterns = [
        r'"""[\s\S]*?"""',  # Docstrings
        r"'''[\s\S]*?'''",  # Docstrings
        r"#\s*(Let's|Let us|We can|We will|We need to)",  # LLM comments
        r"#\s*(Here we|Here is|Here's|This function|This method)",
        r"raise\s+(ValueError|TypeError|Exception)\s*\(",  # Exception handling
        r"Optional\[|Union\[|Dict\[|List\[",  # Type hints
        r"if\s+\w+\s+is\s+None\s*:",  # None checks
        r"logging\.(debug|info|warning|error)\s*\(",  # Logging
    ]

    flagged_lines = []
    lines = code.splitlines()

    for line_num, line in enumerate(lines, 1):
        for pattern in patterns:
            if re.search(pattern, line):
                flagged_lines.append(line_num)
                break

        if len(flagged_lines) >= max_lines:
            break

    return flagged_lines


def get_detection_summary(result: AIDetectionResult) -> dict:
    """Get summary of detection result.

    Args:
        result: Detection result

    Returns:
        Dictionary with summary information
    """
    return {
        "ai_probability": result.ai_probability,
        "confidence": result.confidence,
        "risk_level": result.risk_level,
        "is_high_confidence": result.is_high_confidence,
        "is_medium_confidence": result.is_medium_confidence,
        "is_low_confidence": result.is_low_confidence,
        "indicators_count": len(result.indicators),
        "flagged_lines_count": len(result.flagged_lines),
    }


def batch_detect_ai_code(
    code_samples: dict[str, str],
    language: str = "python",
) -> dict[str, AIDetectionResult]:
    """Detect AI-generated code in batch.

    Args:
        code_samples: Dictionary mapping sample names to code
        language: Programming language

    Returns:
        Dictionary mapping sample names to detection results
    """
    results = {}

    for name, code in code_samples.items():
        try:
            result = detect_ai_generated_code(code, language)
            results[name] = result
        except Exception as e:
            logger.error(f"Error detecting {name}: {e}")
            results[name] = None

    return results


def compare_detection_results(
    result1: AIDetectionResult,
    result2: AIDetectionResult,
) -> dict:
    """Compare two detection results.

    Args:
        result1: First detection result
        result2: Second detection result

    Returns:
        Dictionary with comparison information
    """
    return {
        "ai_probability_diff": abs(result1.ai_probability - result2.ai_probability),
        "confidence_diff": abs(result1.confidence - result2.confidence),
        "risk_level_same": result1.risk_level == result2.risk_level,
        "result1_risk": result1.risk_level,
        "result2_risk": result2.risk_level,
        "result1_confidence": result1.confidence,
        "result2_confidence": result2.confidence,
    }
