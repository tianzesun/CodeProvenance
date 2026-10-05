"""Signal reliability assessment framework.

Determines the reliability of each signal based on code characteristics.
Reliability scores are used to adjust signal weights during aggregation.

Reliability factors:
- Code length (some signals need minimum code)
- Language (Python vs other)
- Code structure (some signals need functions/classes)
- Amount of the specific evidence a signal measures (tokens, lines, blank runs)

The statistics every signal needs (token count, line counts, blank-line runs,
function counts) are computed ONCE per file by :func:`assess_all_signal_reliabilities`;
each signal used to re-scan the whole source with its own regex.
"""

import re
from dataclasses import dataclass

from src.backend.engines.ai.models import SIGNAL_NAMES

_TOKEN_RE = re.compile(r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:]")
# ``async def`` is a function too (it was missed, so async code looked function-free).
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+\w+", re.MULTILINE)
_CLASS_RE = re.compile(r"^\s*class\s+\w+", re.MULTILINE)

_PYTHON_NAMES = frozenset({"python", "py", "python3", ""})

#: Signals built on Python-specific syntax (``def``, ``#`` comments, triple-quoted
#: docstrings, Python type hints). On other languages they measure nothing
#: meaningful, so their reliability is capped rather than letting them vote at full
#: weight. The reports already state that the detector is calibrated for Python.
PYTHON_ONLY_SIGNALS = frozenset({"stylometry", "docstring_density", "pattern_library"})
NON_PYTHON_RELIABILITY_CAP = 0.3


@dataclass(frozen=True)
class CodeStats:
    """Measurements shared by all reliability checks."""

    tokens: int
    total_lines: int
    nonblank_lines: int
    blank_runs: int
    functions: int
    classes: int


def compute_code_stats(code: str) -> CodeStats:
    """Scan ``code`` once for everything the reliability checks need."""
    lines = code.splitlines()
    nonblank = 0
    runs = 0
    in_run = False
    for line in lines:
        if line.strip():
            nonblank += 1
            in_run = False
        elif not in_run:
            runs += 1  # a run of blank lines, counted when it starts
            in_run = True
    return CodeStats(
        tokens=len(_TOKEN_RE.findall(code)),
        total_lines=len(lines),
        nonblank_lines=nonblank,
        blank_runs=runs,
        functions=len(_DEF_RE.findall(code)),
        classes=len(_CLASS_RE.findall(code)),
    )


def _step(value: int, steps: tuple[tuple[int, float], ...], top: float = 1.0) -> float:
    """Reliability for ``value``: the first step whose threshold it is below, else ``top``."""
    for threshold, reliability in steps:
        if value < threshold:
            return reliability
    return top


def _is_python(language: str | None) -> bool:
    return (language or "").strip().lower() in _PYTHON_NAMES


# -- per-signal assessments (operate on shared stats) ------------------------


def _perplexity(s: CodeStats, language: str) -> float:
    """Needs tokens: 10 for basic reliability, 100+ for full."""
    return _step(s.tokens, ((10, 0.0), (50, 0.3), (100, 0.6)))


def _burstiness(s: CodeStats, language: str) -> float:
    """Needs non-blank lines: 5 for basic reliability, 20+ for full."""
    return _step(s.nonblank_lines, ((5, 0.0), (10, 0.3), (20, 0.6)))


def _stylometry(s: CodeStats, language: str) -> float:
    """Needs lines: 20 for basic reliability, 100+ for full."""
    return _step(s.total_lines, ((20, 0.0), (50, 0.3), (100, 0.6)))


def _pattern_library(s: CodeStats, language: str) -> float:
    """Reliable for all code; rises with length."""
    return _step(s.total_lines, ((5, 0.5), (20, 0.7)))


def _structural_entropy(s: CodeStats, language: str) -> float:
    """AST uniformity: best for Python with several functions/classes.

    Non-Python code and Python without any function or class fall back to the
    indent-level measure, which is less reliable.
    """
    if not _is_python(language):
        return 0.3 if s.total_lines < 10 else 0.6
    structures = s.functions + s.classes
    if structures == 0:
        return 0.3 if s.total_lines < 10 else 0.6
    if structures < 3:
        return 0.6
    return 1.0


def _vocabulary_richness(s: CodeStats, language: str) -> float:
    """Needs tokens: 20 for basic reliability, 100+ for full."""
    return _step(s.tokens, ((20, 0.0), (50, 0.3), (100, 0.6)))


def _whitespace_rhythm(s: CodeStats, language: str) -> float:
    """Measures the spacing between blank-line RUNS, so it needs runs, not lines.

    The signal returns 0.0 ("human-like") when a file has fewer than 3 blank-line
    runs. Reliability used to depend on the total line count, so a 200-line file
    with no blank lines was rated fully reliable and its empty measurement voted
    as human evidence at full weight.
    """
    return _step(s.blank_runs, ((3, 0.0), (5, 0.3), (10, 0.6)))


def _docstring_density(s: CodeStats, language: str) -> float:
    """Needs functions: 1 for basic reliability, 5+ for full."""
    return _step(s.functions, ((1, 0.0), (3, 0.3), (5, 0.6)))


_ASSESSORS = {
    "perplexity": _perplexity,
    "burstiness": _burstiness,
    "stylometry": _stylometry,
    "pattern_library": _pattern_library,
    "structural_entropy": _structural_entropy,
    "vocabulary_richness": _vocabulary_richness,
    "whitespace_rhythm": _whitespace_rhythm,
    "docstring_density": _docstring_density,
}
assert set(_ASSESSORS) == set(SIGNAL_NAMES)


def _assess(signal_name: str, stats: CodeStats, language: str) -> float:
    assessor = _ASSESSORS.get(signal_name)
    if assessor is None:
        return 0.5  # Default to moderate reliability
    reliability = assessor(stats, language)
    if signal_name in PYTHON_ONLY_SIGNALS and not _is_python(language):
        reliability = min(reliability, NON_PYTHON_RELIABILITY_CAP)
    return reliability


def assess_signal_reliability(
    signal_name: str, code: str, language: str = "python"
) -> float:
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
    return _assess(signal_name, compute_code_stats(code), language)


def assess_all_signal_reliabilities(
    code: str, language: str = "python"
) -> dict[str, float]:
    """Assess reliability of all signals for given code.

    Args:
        code: Source code to analyze
        language: Programming language (default: 'python')

    Returns:
        Dictionary mapping signal names to reliability scores
    """
    stats = compute_code_stats(code)
    return {signal: _assess(signal, stats, language) for signal in SIGNAL_NAMES}


# -- backward-compatible per-signal helpers ----------------------------------


def _assess_perplexity_reliability(code: str) -> float:
    return _perplexity(compute_code_stats(code), "python")


def _assess_burstiness_reliability(code: str) -> float:
    return _burstiness(compute_code_stats(code), "python")


def _assess_stylometry_reliability(code: str) -> float:
    return _stylometry(compute_code_stats(code), "python")


def _assess_pattern_library_reliability(code: str) -> float:
    return _pattern_library(compute_code_stats(code), "python")


def _assess_structural_entropy_reliability(code: str, language: str = "python") -> float:
    return _structural_entropy(compute_code_stats(code), language)


def _assess_vocabulary_richness_reliability(code: str) -> float:
    return _vocabulary_richness(compute_code_stats(code), "python")


def _assess_whitespace_rhythm_reliability(code: str) -> float:
    return _whitespace_rhythm(compute_code_stats(code), "python")


def _assess_docstring_density_reliability(code: str) -> float:
    return _docstring_density(compute_code_stats(code), "python")
