"""Binoculars-based AI Code Detector (Layer 1 - Zero-shot).

Binoculars (ICML 2024) is currently one of the strongest open-source
AI text detectors. It achieves >90% detection accuracy at a false-positive
rate of only 0.01% without any training data.

This wrapper makes Binoculars easy to use inside IntegrityDesk's
multi-layer AI detection ensemble.

Reference: https://github.com/ahans30/Binoculars (arXiv:2401.12070)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Default observer/performer pair.
#
# The upstream Binoculars defaults are two Falcon-7B checkpoints (~14GB each),
# which cannot run on a CPU-only host. This pair is roughly 1GB total in
# bfloat16 and is the smallest pair that still preserves the
# observer-vs-instruction-tuned contrast the method depends on.
#
# Override with BINOCULARS_OBSERVER_MODEL / BINOCULARS_PERFORMER_MODEL.
DEFAULT_OBSERVER_MODEL = "Qwen/Qwen2.5-0.5B"
DEFAULT_PERFORMER_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

# Binoculars' own decision thresholds, copied from
# binoculars/detector.py (selected on Falcon-7B / Falcon-7B-Instruct).
#
# The raw score is ``perplexity / cross_entropy`` — a POSITIVE ratio where
# LOWER means MORE machine-like. These are the score values at which the
# reference implementation calls a sample AI / human.
BINOCULARS_FPR_THRESHOLD = 0.8536432310785527
BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843

# Probability assigned at (and beyond) each anchor, so the mapped value uses
# the same semantics as the rest of the ensemble: 1.0 = certainly AI.
AI_ANCHOR_PROBABILITY = 0.95
HUMAN_ANCHOR_PROBABILITY = 0.05


def binoculars_score_to_probability(raw_score: float) -> float:
    """Map a raw Binoculars score to an AI probability in [0, 1].

    The raw score is a positive ``perplexity / cross_entropy`` ratio where
    *lower* means more machine-like; the reference implementation classifies
    anything below ``BINOCULARS_FPR_THRESHOLD`` as AI-generated.

    The mapping is therefore linear *downward* between the two published
    thresholds, anchored at 0.95 (at/below the low-FPR threshold) and 0.05
    (at/above the accuracy threshold).

    Args:
        raw_score: Value returned by ``Binoculars.compute_score``.

    Returns:
        Probability that the input is AI-generated, clamped to [0, 1].
    """
    if raw_score != raw_score:  # NaN guard
        return 0.5
    if raw_score <= BINOCULARS_FPR_THRESHOLD:
        return AI_ANCHOR_PROBABILITY
    if raw_score >= BINOCULARS_ACCURACY_THRESHOLD:
        return HUMAN_ANCHOR_PROBABILITY
    span = BINOCULARS_ACCURACY_THRESHOLD - BINOCULARS_FPR_THRESHOLD
    # 0 at the FPR threshold, 1 at the accuracy threshold.
    position = (raw_score - BINOCULARS_FPR_THRESHOLD) / span
    return AI_ANCHOR_PROBABILITY - position * (
        AI_ANCHOR_PROBABILITY - HUMAN_ANCHOR_PROBABILITY
    )


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

    def __init__(
        self,
        model: str | None = None,
        performer: str | None = None,
    ) -> None:
        """Configure the observer/performer model pair.

        Binoculars compares an "observer" (base) model against a "performer"
        (instruction-tuned) model. The upstream defaults are two Falcon-7B
        checkpoints (~14GB each), which is impractical on CPU-only hosts.

        Args:
            model: Observer checkpoint. Defaults to ``BINOCULARS_OBSERVER_MODEL``
                (or the small CPU-friendly pair when that is unset).
            performer: Performer checkpoint. Defaults to
                ``BINOCULARS_PERFORMER_MODEL``.

        Both models must share a tokenizer; ``binoculars`` asserts this.
        """
        self.model = model or os.environ.get(
            "BINOCULARS_OBSERVER_MODEL", DEFAULT_OBSERVER_MODEL
        )
        self.performer = performer or os.environ.get(
            "BINOCULARS_PERFORMER_MODEL", DEFAULT_PERFORMER_MODEL
        )
        self._bino: Any = None
        self._available = False

    def _load(self) -> bool:
        """Lazily load the binoculars package and models.

        Set ``BINOCULARS_ENABLED=0`` to force the heuristic-only fallback without
        uninstalling anything. This is also what the test suite uses, so unit
        tests never pull ~1GB of weights or depend on a model download.

        An already-injected instance is honoured first, so tests can substitute
        a stub without needing the package installed.
        """
        if self._bino is not None:
            return self._available
        if os.environ.get("BINOCULARS_ENABLED", "1") != "1":
            return False

        try:
            from binoculars import Binoculars  # type: ignore

            self._bino = Binoculars(
                observer_name_or_path=self.model,
                performer_name_or_path=self.performer,
                # bfloat16 halves memory. On CPUs without AVX512-BF16 it is
                # emulated, so callers can opt out via the environment.
                use_bfloat16=os.environ.get("BINOCULARS_BF16", "1") != "0",
                max_token_observed=int(os.environ.get("BINOCULARS_MAX_TOKENS", "512")),
            )
            self._available = True
            logger.info(
                "BinocularsDetector loaded (observer=%s, performer=%s)",
                self.model,
                self.performer,
            )
        except Exception as exc:
            logger.warning(
                "BinocularsDetector could not be loaded: %s. "
                "Falling back to heuristic signals only. "
                "Install with: pip install "
                "git+https://github.com/ahans30/Binoculars.git "
                "(the PyPI 'binoculars' package is an unrelated statistics "
                "library, not the AI detector)",
                exc,
            )
            self._available = False
        return self._available

    def analyze(self, code: str, language: str | None = None) -> dict[str, Any]:
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
            # compute_score returns perplexity / cross_entropy: a positive
            # ratio where LOWER means more machine-like.
            raw_score = float(self._bino.compute_score(code))
            label = str(self._bino.predict(code))

            ai_probability = binoculars_score_to_probability(raw_score)

            # Confidence reflects how far the score sits from the decision
            # band, not an assumed model property.
            midpoint = (BINOCULARS_FPR_THRESHOLD + BINOCULARS_ACCURACY_THRESHOLD) / 2
            distance = abs(raw_score - midpoint)
            half_band = (BINOCULARS_ACCURACY_THRESHOLD - BINOCULARS_FPR_THRESHOLD) / 2
            confidence = (
                min(0.9, 0.4 + 2.0 * (distance / half_band)) if half_band else 0.5
            )

            return {
                "ai_probability": round(ai_probability, 4),
                "confidence": round(min(0.9, max(0.1, confidence)), 4),
                "raw_score": round(raw_score, 4),
                "label": label,
                "available": True,
            }

        except Exception:
            logger.exception("Binoculars inference failed")
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
