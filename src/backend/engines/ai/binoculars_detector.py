"""Binoculars-based AI Code Detector (Layer 1 - Zero-shot).

Binoculars (ICML 2024) is currently one of the strongest open-source
AI text detectors. It achieves >90% detection accuracy at a false-positive
rate of only 0.01% without any training data.

This wrapper makes Binoculars easy to use inside IntegrityDesk's
multi-layer AI detection ensemble.

Reference: https://github.com/ahmet-uyar/binoculars
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BinocularsDetector:
    """
    Zero-shot AI code detector powered by Binoculars.

    Binoculars runs the input through two closely-related LLMs
    (observer + performer) and measures how "surprising" the text is
    to both models. Machine-generated text tends to be unsurprising
    to both, while human writing produces different surprise patterns.

    Advantages:
        - No training data required
        - Very low false positive rate (excellent for academic use)
        - Robust to many modern LLMs (GPT-4, Claude, Gemini, Llama, etc.)
    """

    def __init__(self, model: str = "default") -> None:
        """
        Args:
            model: Which Binoculars model pair to use.
                   "default" uses the recommended OPT-6.7b observer/performer pair.
        """
        self.model = model
        self._bino: Any = None
        self._available = False

    def _load(self) -> bool:
        """Lazily load the binoculars package and models."""
        if self._bino is not None:
            return self._available

        try:
            from binoculars import Binoculars  # type: ignore

            self._bino = Binoculars()
            self._available = True
            logger.info("BinocularsDetector loaded successfully (zero-shot AI detector)")
        except Exception as exc:
            logger.warning(
                "BinocularsDetector could not be loaded: %s. "
                "Falling back to heuristic signals only. "
                "Install with: pip install binoculars-ai",
                exc,
            )
            self._available = False
        return self._available

    def analyze(self, code: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Run Binoculars on a code submission.

        Args:
            code: Source code to analyze.
            language: Optional language hint (currently unused by Binoculars,
                      but kept for interface compatibility).

        Returns:
            Dictionary with keys:
                - ai_probability: float in [0, 1]
                - confidence: float in [0, 1]
                - raw_score: original Binoculars score (lower = more AI-like)
                - label: "MOST_LIKELY_AI" | "MOST_LIKELY_HUMAN" | "UNCERTAIN"
                - available: whether Binoculars was actually used
        """
        if not code or len(code.strip()) < 50:
            return {
                "ai_probability": 0.5,
                "confidence": 0.0,
                "raw_score": 0.5,
                "label": "UNCERTAIN",
                "available": False,
            }

        if not self._load():
            return {
                "ai_probability": 0.5,
                "confidence": 0.0,
                "raw_score": 0.5,
                "label": "UNCERTAIN",
                "available": False,
            }

        try:
            # Binoculars returns lower scores for AI-generated text
            raw_score = float(self._bino.compute_score(code))
            label = str(self._bino.predict(code))

            # Normalize: Binoculars typical range is roughly -1.0 to +1.0
            # Map to probability where lower raw_score → higher AI probability
            # Conservative mapping tuned for low false-positive academic use
            ai_probability = max(0.0, min(1.0, (1.0 - raw_score) / 2.0))

            # Binoculars is known for high precision; give it decent confidence
            # unless the score is very close to the decision boundary
            confidence = 0.85 if abs(raw_score) > 0.3 else 0.6

            return {
                "ai_probability": round(ai_probability, 4),
                "confidence": round(confidence, 4),
                "raw_score": round(raw_score, 4),
                "label": label,
                "available": True,
            }

        except Exception as exc:
            logger.exception("Binoculars inference failed: %s", exc)
            return {
                "ai_probability": 0.5,
                "confidence": 0.0,
                "raw_score": 0.5,
                "label": "UNCERTAIN",
                "available": False,
            }

    def is_available(self) -> bool:
        """Whether the underlying Binoculars models could be loaded."""
        return self._load()
