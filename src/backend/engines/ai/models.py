"""Data models for AI Detection Engine.

Defines the core data structures for AI detection results, signal scores,
and confidence metrics. All models include validation to ensure scores
are properly bounded and calibrated.
"""

import math
from dataclasses import dataclass
from typing import Any, ClassVar

#: The eight signals, in canonical order. The list used to be repeated in
#: ``_get_signal_names``, ``to_dict``, ``from_dict``, ``reliability`` and
#: ``pipeline``; they all derive from this one now.
SIGNAL_NAMES: tuple[str, ...] = (
    "perplexity",
    "burstiness",
    "stylometry",
    "pattern_library",
    "structural_entropy",
    "vocabulary_richness",
    "whitespace_rhythm",
    "docstring_density",
)

#: ``AIDetectionResult.risk_level`` cut-offs. NOTE: the shared config
#: (ai_ensemble_config.yaml) and the server's ``_ai_bucket`` use 0.40 for the medium
#: band; this module has always used 0.45. They are kept as named constants so the
#: difference is visible and can be reconciled in one place.
MEDIUM_RISK_THRESHOLD = 0.45
HIGH_RISK_THRESHOLD = 0.70

#: Confidence bands used by ``is_*_confidence``.
LOW_CONFIDENCE_THRESHOLD = 0.3
HIGH_CONFIDENCE_THRESHOLD = 0.7

#: Below this confidence a "High"/"Elevated" probability is reported one band lower.
UNCERTAIN_CONFIDENCE = 0.2


def categorize_risk(ai_probability: float, confidence: float = 1.0) -> str:
    """Five-level risk label: "Very Low" / "Low" / "Moderate" / "Elevated" / "High".

    A very uncertain result (``confidence < UNCERTAIN_CONFIDENCE``) never reaches
    "High": an uncertain 0.9 must not read the same as a confident 0.9. This is
    the single definition used by fusion and by ``AIDetectionResult.risk_band``.
    """
    if ai_probability >= 0.80 and confidence < UNCERTAIN_CONFIDENCE:
        return "Elevated"
    if ai_probability < 0.25:
        return "Very Low"
    if ai_probability < 0.45:
        return "Low"
    if ai_probability < 0.65:
        return "Moderate"
    if ai_probability < 0.80:
        return "Elevated"
    return "High"


def _is_real_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass
class SignalScores:
    """Container for all 8 signal scores.

    Each signal measures a different aspect of code characteristics.
    All scores are normalized to [0.0, 1.0] where:
    - 0.0 = human-like
    - 1.0 = AI-like

    Attributes:
        perplexity: Token-level entropy (0.18 weight)
        burstiness: Line complexity variation (0.14 weight)
        stylometry: Code style profile (0.16 weight)
        pattern_library: LLM fingerprints (0.20 weight)
        structural_entropy: AST uniformity (0.12 weight)
        vocabulary_richness: Token diversity (0.08 weight)
        whitespace_rhythm: Blank-line spacing (0.06 weight)
        docstring_density: Documentation prevalence (0.06 weight)
    """

    perplexity: float = 0.0
    burstiness: float = 0.0
    stylometry: float = 0.0
    pattern_library: float = 0.0
    structural_entropy: float = 0.0
    vocabulary_richness: float = 0.0
    whitespace_rhythm: float = 0.0
    docstring_density: float = 0.0

    # Signal weights (must sum to 1.0; checked once at import, below)
    WEIGHTS: ClassVar[dict] = {
        "perplexity": 0.18,
        "burstiness": 0.14,
        "stylometry": 0.16,
        "pattern_library": 0.20,
        "structural_entropy": 0.12,
        "vocabulary_richness": 0.08,
        "whitespace_rhythm": 0.06,
        "docstring_density": 0.06,
    }

    def __post_init__(self):
        """Validate signal scores are properly bounded."""
        self._validate_bounds()

    def _validate_bounds(self):
        """Ensure all signal scores are finite numbers in [0.0, 1.0]."""
        for signal_name in SIGNAL_NAMES:
            score = getattr(self, signal_name)
            # ``bool`` is an ``int`` subclass; ``True`` is not a score.
            if not _is_real_number(score):
                raise TypeError(f"{signal_name} must be numeric")
            if not (0.0 <= score <= 1.0):  # also rejects NaN
                raise ValueError(f"{signal_name} must be in [0.0, 1.0], got {score}")

    @classmethod
    def _validate_weights(cls):
        """Ensure weights cover every signal and sum to 1.0.

        Run ONCE at import (see the bottom of this module) instead of on every
        instance, where it re-summed a constant dict for each score object.
        """
        if set(cls.WEIGHTS) != set(SIGNAL_NAMES):
            raise ValueError("Signal weights must be defined for exactly the 8 signals")
        weight_sum = sum(cls.WEIGHTS.values())
        if not math.isclose(weight_sum, 1.0, rel_tol=1e-9):
            raise ValueError(f"Signal weights must sum to 1.0, got {weight_sum}")

    def _get_signal_names(self) -> list[str]:
        """Return list of all signal names."""
        return list(SIGNAL_NAMES)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {name: getattr(self, name) for name in SIGNAL_NAMES}

    @classmethod
    def from_dict(cls, data: dict[str, float] | None) -> "SignalScores":
        """Create from dictionary (missing signals default to 0.0, unknown keys are ignored)."""
        data = data or {}
        return cls(**{name: data.get(name, 0.0) for name in SIGNAL_NAMES})

    @classmethod
    def sanitized(cls, data: dict[str, Any] | None) -> "SignalScores":
        """Create from raw signal outputs, forcing every value into [0, 1].

        A signal function that returns NaN or a value a hair outside [0, 1] must
        not abort a whole analysis: the strict constructor raises, so callers
        that compute signals use this instead. Non-numeric and non-finite values
        become 0.0 (no evidence), others are clamped.
        """
        clean: dict[str, float] = {}
        for name in SIGNAL_NAMES:
            value = (data or {}).get(name, 0.0)
            if not _is_real_number(value) or not math.isfinite(value):
                value = 0.0
            clean[name] = min(1.0, max(0.0, float(value)))
        return cls(**clean)


@dataclass
class AIDetectionResult:
    """Result of AI detection analysis for a code submission.

    Contains the final AI probability score, confidence level, individual
    signal scores, evidence indicators, and flagged lines.

    Attributes:
        ai_probability: Final AI probability [0.0, 1.0]
        confidence: Confidence in the result [0.0, 1.0]
        signals: Individual signal scores
        signal_labels: Human-readable signal names
        indicators: Evidence indicators (up to 6)
        flagged_lines: Line numbers with LLM fingerprints (up to 30)
        language: Programming language of the code
        error: Error message if analysis failed
    """

    ai_probability: float
    confidence: float
    signals: SignalScores
    signal_labels: dict[str, str]
    indicators: list[str]
    flagged_lines: list[int]
    language: str = "python"
    error: str | None = None

    def __post_init__(self):
        """Validate result fields."""
        self._validate_probabilities()
        self._validate_indicators()
        self._validate_flagged_lines()

    def _validate_probabilities(self):
        """Ensure probabilities are properly bounded."""
        for name in ("ai_probability", "confidence"):
            value = getattr(self, name)
            if not _is_real_number(value):
                raise TypeError(f"{name} must be numeric")
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")

    def _validate_indicators(self):
        """Ensure indicators are valid."""
        if not isinstance(self.indicators, list):
            raise TypeError("indicators must be a list")
        if len(self.indicators) > 6:
            raise ValueError(
                f"indicators must have at most 6 items, got {len(self.indicators)}"
            )
        for indicator in self.indicators:
            if not isinstance(indicator, str):
                raise TypeError("each indicator must be a string")

    def _validate_flagged_lines(self):
        """Ensure flagged lines are valid."""
        if not isinstance(self.flagged_lines, list):
            raise TypeError("flagged_lines must be a list")
        if len(self.flagged_lines) > 30:
            raise ValueError(
                f"flagged_lines must have at most 30 items, got {len(self.flagged_lines)}"
            )
        for line_num in self.flagged_lines:
            if isinstance(line_num, bool) or not isinstance(line_num, int) or line_num < 1:
                raise ValueError(
                    f"each flagged line must be a positive integer, got {line_num}"
                )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "ai_probability": round(self.ai_probability, 3),
            "confidence": round(self.confidence, 3),
            "risk_level": self.risk_level,
            "signals": self.signals.to_dict(),
            "signal_labels": self.signal_labels,
            "indicators": self.indicators,
            "flagged_lines": self.flagged_lines,
            "language": self.language,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AIDetectionResult":
        """Create from dictionary (``risk_level`` is derived, so it is ignored)."""
        return cls(
            ai_probability=data.get("ai_probability", 0.0),
            confidence=data.get("confidence", 0.0),
            signals=SignalScores.from_dict(data.get("signals")),
            signal_labels=data.get("signal_labels") or {},
            indicators=data.get("indicators") or [],
            flagged_lines=data.get("flagged_lines") or [],
            language=data.get("language") or "python",
            error=data.get("error"),
        )

    @property
    def risk_level(self) -> str:
        """Determine risk level based on AI probability.

        Returns:
            'Low' if ai_probability < 0.45
            'Medium' if 0.45 <= ai_probability < 0.70
            'High' if ai_probability >= 0.70

        This is the three-level label the API and UI use. Consumers that need the
        finer five-level scale (``"Moderate"``, ``"Elevated"`` ...) use
        :attr:`risk_band`; ``reporting`` maps ``"Medium"`` to ``"Moderate"``.
        """
        if self.ai_probability < MEDIUM_RISK_THRESHOLD:
            return "Low"
        elif self.ai_probability < HIGH_RISK_THRESHOLD:
            return "Medium"
        else:
            return "High"

    @property
    def risk_band(self) -> str:
        """Five-level risk label that also accounts for confidence (see ``categorize_risk``)."""
        return categorize_risk(self.ai_probability, self.confidence)

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is high (>= 0.7)."""
        return self.confidence >= HIGH_CONFIDENCE_THRESHOLD

    @property
    def is_medium_confidence(self) -> bool:
        """Check if confidence is medium (0.3-0.7)."""
        return LOW_CONFIDENCE_THRESHOLD <= self.confidence < HIGH_CONFIDENCE_THRESHOLD

    @property
    def is_low_confidence(self) -> bool:
        """Check if confidence is low (< 0.3)."""
        return self.confidence < LOW_CONFIDENCE_THRESHOLD


SignalScores._validate_weights()
