"""Data models for AI Detection Engine.

Defines the core data structures for AI detection results, signal scores,
and confidence metrics. All models include validation to ensure scores
are properly bounded and calibrated.
"""

import math
from dataclasses import dataclass


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

    # Signal weights (must sum to 1.0)
    WEIGHTS = {
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
        self._validate_weights()

    def _validate_bounds(self):
        """Ensure all signal scores are in [0.0, 1.0]."""
        for signal_name in self._get_signal_names():
            score = getattr(self, signal_name)
            if not isinstance(score, (int, float)):
                raise ValueError(f"{signal_name} must be numeric")
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"{signal_name} must be in [0.0, 1.0], got {score}")

    def _validate_weights(self):
        """Ensure weights sum to 1.0 (with floating-point tolerance)."""
        weight_sum = sum(self.WEIGHTS.values())
        if not math.isclose(weight_sum, 1.0, rel_tol=1e-9):
            raise ValueError(f"Signal weights must sum to 1.0, got {weight_sum}")

    def _get_signal_names(self) -> list[str]:
        """Return list of all signal names."""
        return [
            "perplexity",
            "burstiness",
            "stylometry",
            "pattern_library",
            "structural_entropy",
            "vocabulary_richness",
            "whitespace_rhythm",
            "docstring_density",
        ]

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "perplexity": self.perplexity,
            "burstiness": self.burstiness,
            "stylometry": self.stylometry,
            "pattern_library": self.pattern_library,
            "structural_entropy": self.structural_entropy,
            "vocabulary_richness": self.vocabulary_richness,
            "whitespace_rhythm": self.whitespace_rhythm,
            "docstring_density": self.docstring_density,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "SignalScores":
        """Create from dictionary."""
        return cls(
            perplexity=data.get("perplexity", 0.0),
            burstiness=data.get("burstiness", 0.0),
            stylometry=data.get("stylometry", 0.0),
            pattern_library=data.get("pattern_library", 0.0),
            structural_entropy=data.get("structural_entropy", 0.0),
            vocabulary_richness=data.get("vocabulary_richness", 0.0),
            whitespace_rhythm=data.get("whitespace_rhythm", 0.0),
            docstring_density=data.get("docstring_density", 0.0),
        )


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
        if not (0.0 <= self.ai_probability <= 1.0):
            raise ValueError(
                f"ai_probability must be in [0.0, 1.0], got {self.ai_probability}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")

    def _validate_indicators(self):
        """Ensure indicators are valid."""
        if not isinstance(self.indicators, list):
            raise ValueError("indicators must be a list")
        if len(self.indicators) > 6:
            raise ValueError(
                f"indicators must have at most 6 items, got {len(self.indicators)}"
            )
        for indicator in self.indicators:
            if not isinstance(indicator, str):
                raise ValueError("each indicator must be a string")

    def _validate_flagged_lines(self):
        """Ensure flagged lines are valid."""
        if not isinstance(self.flagged_lines, list):
            raise ValueError("flagged_lines must be a list")
        if len(self.flagged_lines) > 30:
            raise ValueError(
                f"flagged_lines must have at most 30 items, got {len(self.flagged_lines)}"
            )
        for line_num in self.flagged_lines:
            if not isinstance(line_num, int) or line_num < 1:
                raise ValueError(
                    f"each flagged line must be a positive integer, got {line_num}"
                )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "ai_probability": round(self.ai_probability, 3),
            "confidence": round(self.confidence, 3),
            "signals": self.signals.to_dict(),
            "signal_labels": self.signal_labels,
            "indicators": self.indicators,
            "flagged_lines": self.flagged_lines,
            "language": self.language,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AIDetectionResult":
        """Create from dictionary."""
        signals = SignalScores.from_dict(data.get("signals", {}))
        return cls(
            ai_probability=data.get("ai_probability", 0.0),
            confidence=data.get("confidence", 0.0),
            signals=signals,
            signal_labels=data.get("signal_labels", {}),
            indicators=data.get("indicators", []),
            flagged_lines=data.get("flagged_lines", []),
            language=data.get("language", "python"),
            error=data.get("error"),
        )

    @property
    def risk_level(self) -> str:
        """Determine risk level based on AI probability.

        Returns:
            'Low' if ai_probability < 0.45
            'Medium' if 0.45 <= ai_probability < 0.70
            'High' if ai_probability >= 0.70
        """
        if self.ai_probability < 0.45:
            return "Low"
        elif self.ai_probability < 0.70:
            return "Medium"
        else:
            return "High"

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is high (>= 0.7)."""
        return self.confidence >= 0.7

    @property
    def is_medium_confidence(self) -> bool:
        """Check if confidence is medium (0.3-0.7)."""
        return 0.3 <= self.confidence < 0.7

    @property
    def is_low_confidence(self) -> bool:
        """Check if confidence is low (< 0.3)."""
        return self.confidence < 0.3
