"""AI Detection Pipeline - Complete end-to-end orchestration.

Coordinates all components of the AI detection system:
1. Signal computation
2. Fusion and calibration
3. Report generation
4. Evidence annotation
"""

import bisect
import logging
import re
from collections.abc import Callable

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

# (signal name, function(code, language) -> score)
_SIGNAL_COMPUTERS: tuple[tuple[str, Callable[[str, str], float]], ...] = (
    ("perplexity", lambda code, language: compute_perplexity_signal(code)),
    ("burstiness", lambda code, language: compute_burstiness_signal(code)),
    ("stylometry", lambda code, language: compute_stylometry_signal(code)),
    ("pattern_library", lambda code, language: compute_pattern_library_signal(code)),
    ("structural_entropy", compute_structural_entropy_signal),
    ("vocabulary_richness", lambda code, language: compute_vocabulary_richness_signal(code)),
    ("whitespace_rhythm", lambda code, language: compute_whitespace_rhythm_signal(code)),
    ("docstring_density", lambda code, language: compute_docstring_density_signal(code)),
)

# Compiled once. They were passed to ``re.search`` as strings on every line of
# every file.
_LINE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"#\s*(Let's|Let us|We can|We will|We need to)",  # LLM comments
        r"#\s*(Here we|Here is|Here's|This function|This method)",
        r"raise\s+(ValueError|TypeError|Exception)\s*\(",  # Exception handling
        r"Optional\[|Union\[|Dict\[|List\[",  # Type hints
        r"if\s+\w+\s+is\s+None\s*:",  # None checks
        r"logging\.(debug|info|warning|error)\s*\(",  # Logging
    )
)
_DOCSTRING_RE = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')


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

    Each signal is computed independently. One failing signal falls back to its
    neutral default and is logged with its traceback; previously a single
    exception reset ALL eight signals to neutral (and logged only the message),
    silently turning a bug in one signal into a "no evidence" verdict.

    Args:
        code: Source code to analyze
        language: Programming language

    Returns:
        SignalScores object with all 8 signal scores
    """
    values: dict[str, float] = {}
    for name, compute in _SIGNAL_COMPUTERS:
        try:
            values[name] = compute(code, language)
        except Exception:
            logger.warning("Signal %r failed; using its neutral default", name, exc_info=True)
            values[name] = 0.0
    # ``SignalScores`` is strict: a signal returning NaN or a value a hair outside
    # [0, 1] would raise here and abort the whole analysis. ``sanitized`` clamps
    # those (and maps non-numeric/non-finite values to "no evidence").
    return SignalScores.sanitized(values)


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
    result.flagged_lines = find_llm_pattern_lines(code)  # already capped at 30
    return result


def find_llm_pattern_lines(code: str, max_lines: int = 30) -> list[int]:
    """Find lines with LLM-specific patterns.

    Args:
        code: Source code to analyze
        max_lines: Maximum number of lines to return

    Returns:
        Sorted list of line numbers (1-indexed) with LLM patterns
    """
    flagged: set[int] = set()

    # Docstrings are matched over the WHOLE text and reported at the line they
    # start on. The pattern used to be applied line by line, so only a docstring
    # that opened and closed on a single line was ever found.
    if '"""' in code or "'''" in code:
        newline_offsets = [i for i, ch in enumerate(code) if ch == "\n"]
        for match in _DOCSTRING_RE.finditer(code):
            flagged.add(bisect.bisect_left(newline_offsets, match.start()) + 1)

    for line_num, line in enumerate(code.splitlines(), 1):
        if any(pattern.search(line) for pattern in _LINE_PATTERNS):
            flagged.add(line_num)

    return sorted(flagged)[:max_lines]


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
) -> dict[str, AIDetectionResult | None]:
    """Detect AI-generated code in batch.

    Args:
        code_samples: Dictionary mapping sample names to code
        language: Programming language

    Returns:
        Dictionary mapping sample names to detection results (None when a
        sample could not be analysed)
    """
    results: dict[str, AIDetectionResult | None] = {}

    for name, code in code_samples.items():
        try:
            results[name] = detect_ai_generated_code(code, language)
        except Exception:
            logger.error("Error detecting %s", name, exc_info=True)
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
