"""Signal reliability assessment framework.

Determines the reliability of each signal based on code characteristics.
Reliability scores are used to adjust signal weights during aggregation.

Reliability factors:
- Code length (some signals need minimum code)
- Language (Python vs other)
- Code structure (some signals need functions/classes)
- Entropy levels (extreme values indicate unreliability)
"""

import re
from typing import Dict


def assess_signal_reliability(signal_name: str, code: str, language: str = "python") -> float:
    """Assess the reliability of a signal for given code.

    Args:
        signal_name: Name of the signal to assess
        code: Source code to analyze
        language: Programming language (default: 'python')

    Returns:
        Reliability score in [0.0, 1.0] where:
        - 1.0 = highly reliable
        - 0.5 = moderately reliable
        - 0.0 = unreliable
    """
    if signal_name == "perplexity":
        return _assess_perplexity_reliability(code)
    elif signal_name == "burstiness":
        return _assess_burstiness_reliability(code)
    elif signal_name == "stylometry":
        return _assess_stylometry_reliability(code)
    elif signal_name == "pattern_library":
        return _assess_pattern_library_reliability(code)
    elif signal_name == "structural_entropy":
        return _assess_structural_entropy_reliability(code, language)
    elif signal_name == "vocabulary_richness":
        return _assess_vocabulary_richness_reliability(code)
    elif signal_name == "whitespace_rhythm":
        return _assess_whitespace_rhythm_reliability(code)
    elif signal_name == "docstring_density":
        return _assess_docstring_density_reliability(code)
    else:
        return 0.5  # Default to moderate reliability


def _assess_perplexity_reliability(code: str) -> float:
    """Assess perplexity signal reliability.

    Perplexity is reliable for code with sufficient tokens.
    Minimum: 10 tokens for basic reliability.
    Optimal: 100+ tokens for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    tokens = re.findall(r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:]", code)
    token_count = len(tokens)

    if token_count < 10:
        return 0.0
    elif token_count < 50:
        return 0.3
    elif token_count < 100:
        return 0.6
    else:
        return 1.0


def _assess_burstiness_reliability(code: str) -> float:
    """Assess burstiness signal reliability.

    Burstiness is reliable for code with sufficient lines.
    Minimum: 5 lines for basic reliability.
    Optimal: 20+ lines for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    lines = [ln.rstrip() for ln in code.splitlines() if ln.strip()]
    line_count = len(lines)

    if line_count < 5:
        return 0.0
    elif line_count < 10:
        return 0.3
    elif line_count < 20:
        return 0.6
    else:
        return 1.0


def _assess_stylometry_reliability(code: str) -> float:
    """Assess stylometry signal reliability.

    Stylometry is reliable for code with sufficient length.
    Minimum: 50 lines for basic reliability.
    Optimal: 100+ lines for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    lines = code.splitlines()
    line_count = len(lines)

    if line_count < 20:
        return 0.0
    elif line_count < 50:
        return 0.3
    elif line_count < 100:
        return 0.6
    else:
        return 1.0


def _assess_pattern_library_reliability(code: str) -> float:
    """Assess pattern library signal reliability.

    Pattern library is reliable for all code.
    Reliability increases with code length.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    lines = code.splitlines()
    line_count = len(lines)

    if line_count < 5:
        return 0.5
    elif line_count < 20:
        return 0.7
    else:
        return 1.0


def _assess_structural_entropy_reliability(code: str, language: str = "python") -> float:
    """Assess structural entropy signal reliability.

    Structural entropy is reliable for Python code with functions.
    For non-Python code, uses indent-level fallback (less reliable).

    Args:
        code: Source code to analyze
        language: Programming language

    Returns:
        Reliability score in [0.0, 1.0]
    """
    if language not in ("python", "py", ""):
        # Non-Python code uses indent-level fallback (less reliable)
        lines = code.splitlines()
        if len(lines) < 10:
            return 0.3
        else:
            return 0.6

    # Python code: check for functions/classes
    func_count = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))
    class_count = len(re.findall(r"^\s*class\s+\w+", code, re.MULTILINE))
    struct_count = func_count + class_count

    if struct_count == 0:
        # No functions/classes: use indent-level fallback
        lines = code.splitlines()
        if len(lines) < 10:
            return 0.3
        else:
            return 0.6
    elif struct_count < 3:
        return 0.6
    else:
        return 1.0


def _assess_vocabulary_richness_reliability(code: str) -> float:
    """Assess vocabulary richness signal reliability.

    Vocabulary richness is reliable for code with sufficient tokens.
    Minimum: 20 tokens for basic reliability.
    Optimal: 100+ tokens for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    tokens = re.findall(r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:]", code)
    token_count = len(tokens)

    if token_count < 20:
        return 0.0
    elif token_count < 50:
        return 0.3
    elif token_count < 100:
        return 0.6
    else:
        return 1.0


def _assess_whitespace_rhythm_reliability(code: str) -> float:
    """Assess whitespace rhythm signal reliability.

    Whitespace rhythm is reliable for code with sufficient lines.
    Minimum: 10 lines for basic reliability.
    Optimal: 30+ lines for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    lines = code.splitlines()
    line_count = len(lines)

    if line_count < 10:
        return 0.0
    elif line_count < 20:
        return 0.3
    elif line_count < 30:
        return 0.6
    else:
        return 1.0


def _assess_docstring_density_reliability(code: str) -> float:
    """Assess docstring density signal reliability.

    Docstring density is reliable for code with functions.
    Minimum: 1 function for basic reliability.
    Optimal: 3+ functions for high reliability.

    Args:
        code: Source code to analyze

    Returns:
        Reliability score in [0.0, 1.0]
    """
    func_count = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))

    if func_count == 0:
        return 0.0
    elif func_count < 3:
        return 0.3
    elif func_count < 5:
        return 0.6
    else:
        return 1.0


def assess_all_signal_reliabilities(code: str, language: str = "python") -> Dict[str, float]:
    """Assess reliability of all signals for given code.

    Args:
        code: Source code to analyze
        language: Programming language (default: 'python')

    Returns:
        Dictionary mapping signal names to reliability scores
    """
    signal_names = [
        "perplexity",
        "burstiness",
        "stylometry",
        "pattern_library",
        "structural_entropy",
        "vocabulary_richness",
        "whitespace_rhythm",
        "docstring_density",
    ]

    return {signal: assess_signal_reliability(signal, code, language) for signal in signal_names}
