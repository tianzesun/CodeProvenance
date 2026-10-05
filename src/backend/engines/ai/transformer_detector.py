"""Compatibility layers around the heuristic AI detector.

The CodeBERT fine-tuned detector was never checked in and the zero-shot centroids
were never trained, so these classes delegate to the shipped detection engines
instead of fabricating constant scores that would corrupt fusion results.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # numpy is only needed for a type hint; do not import it eagerly
    import numpy as np

logger = logging.getLogger(__name__)

#: ``is_ai_generated`` is True only above this probability: a deliberately
#: stricter bar than the "likely AI" band.
DEFINITE_AI_PROBABILITY = 0.85


def _engine_analyze(code: str) -> dict[str, Any]:
    """Lazily delegate to the heuristic AIDetectionEngine.

    The CodeBERT fine-tuned detector was never checked in and the zero-shot
    centroids were never trained, so both learned layers delegate to the
    shipped heuristic engine (the single source of truth for AI scoring)
    instead of fabricating constant scores that would corrupt fusion results.
    """
    from src.backend.engines.similarity.ai_detection import AIDetectionEngine

    return AIDetectionEngine().analyze(code)


class ZeroShotAIDetector:
    """
    Zero-Shot / Few-Shot AI Code Detector.
    Uses CodeBERT embeddings and cosine similarity against a known
    'Human-Baseline' and 'AI-Template' set to classify code without
    extensive fine-tuning.
    """

    def __init__(self, model_name: str = "microsoft/codebert-base"):
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._device = None
        # Human vs AI centroids in embedding space (Pre-calculated from benchmark)
        self._human_centroid = None
        self._ai_centroid = None

    def _load_model(self) -> bool:
        if self._tokenizer is None:
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModel.from_pretrained(self.model_name)
                self._device = torch.device(
                    "cuda" if torch.cuda.is_available() else "cpu"
                )
                self._model.to(self._device)
                self._model.eval()
            except ImportError:
                return False
        return True

    def get_embedding(self, code: str) -> np.ndarray:
        """Extract mean-pooled CodeBERT embedding.

        Raises:
            RuntimeError: if torch/transformers are not installed (this used to
                fail with an opaque ``'NoneType' object is not callable``).
        """
        if not self._load_model():
            raise RuntimeError("transformers/torch are not installed; cannot embed code")
        import torch

        inputs = self._tokenizer(
            code, return_tensors="pt", truncation=True, max_length=512
        ).to(self._device)
        with torch.no_grad():
            outputs = self._model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]
        return embeddings

    def predict_zero_shot(self, code: str) -> float:
        """
        Compare input code embedding to AI vs Human centroids.
        Returns AI probability.

        The CodeBERT model and the human/AI centroids are not trained in this
        environment, so this returns the heuristic engine score rather than a
        fabricated constant.
        """
        return _engine_analyze(code).get("ai_probability", 0.0)

    def _detect_ai_patterns(self, code: str) -> float:
        """
        Cheap stylistic cues, in [0, 1]. Not used by the fusion path.

        Two defects are fixed here:

        * The indentation test was ``len(line) - len(line.lstrip()) % 4 == 0``;
          ``%`` binds tighter than ``-`` so it compared the line length to a
          remainder and was effectively never true.
        * ``return score + 0.4  # Baseline for modern LLMs`` handed EVERY file
          at least 0.40 (the medium-risk threshold). A constant offset is not
          evidence, so it is gone.
        """
        lines = code.splitlines()
        if not lines:
            return 0.0

        score = 0.0
        # Standard docstrings
        if '"""' in code and ":" in code:
            score += 0.2

        # List comprehension / functional density
        if ".map(" in code or ("[" in code and "for" in code):
            score += 0.1

        # Perfectly regular indentation (multiples of four)
        code_lines = [line for line in lines if line.strip()]
        if code_lines and all(
            (len(line) - len(line.lstrip())) % 4 == 0 for line in code_lines
        ):
            score += 0.2

        return min(1.0, score)


class CodeBERTDetector:
    """Compatibility wrapper for the missing fine-tuned detector.

    The original implementation was never checked in, so we delegate to the
    stable heuristic detector that ships with the app and keep the same
    ``predict()`` interface expected by older services.
    """

    def __init__(self):
        self._engine = None

    def predict(self, code: str) -> dict[str, Any]:
        if self._engine is None:
            from src.backend.engines.similarity.ai_detection import AIDetectionEngine

            self._engine = AIDetectionEngine()

        result = self._engine.analyze(code)
        return {
            "ai_prob": float(result.get("ai_probability", 0.0)),
            "confidence": float(result.get("confidence", 0.0)),
            "signals": result.get("signals", {}),
            "indicators": result.get("indicators", []),
        }


class AIDetectionLayer:
    """
    High-Accuracy AI Detection Layer.

    Fuses the heuristic signal engine for a calibrated AI probability. The
    CodeBERT zero-shot/fine-tuned layers are not trained in this environment,
    so they delegate to the heuristic engine rather than returning constant
    scores that would falsely inflate downstream risk.
    """

    def __init__(self):
        from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

        self._orchestrator = AIDetectionOrchestrator()

    @staticmethod
    def _thresholds() -> tuple[float, float]:
        """(medium, high) risk cut-offs from ai_ensemble_config.yaml.

        They were hard-coded as 0.4 / 0.7 here, so editing the config moved
        every other consumer but not this one.
        """
        try:
            from src.backend.engines.ai.ensemble import AIEnsembleConfig

            config = AIEnsembleConfig.get_instance()
            return config.threshold("medium_risk", 0.40), config.threshold("high_risk", 0.70)
        except Exception:
            return 0.40, 0.70

    def analyze(self, code: str, language: str = "python") -> dict[str, Any]:
        """Deep forensic analysis for AI presence.

        ``language`` is passed through (it was dropped, so every file was
        analysed as Python).
        """
        result = self._orchestrator.analyze(code, language=language)
        ai_prob = result.get("ai_probability", 0.0)
        confidence = result.get("confidence", 0.0)

        medium, high = self._thresholds()
        if ai_prob >= high:
            decision = "likely_ai"
        elif ai_prob >= medium:
            decision = "review"
        else:
            decision = "likely_human"

        return {
            "ai_probability": round(ai_prob, 4),
            "is_ai_generated": ai_prob > DEFINITE_AI_PROBABILITY,
            "confidence": round(confidence, 4),
            "decision": decision,
            # Reports the layers that actually ran (it always said "Heuristic
            # signal ensemble", even when Binoculars or the classifier was used).
            "methodology": result.get("model") or "Heuristic signal ensemble",
            "method": result.get("method", "heuristic"),
            "indicators": result.get("indicators", []),
            "signals": result.get("signals", {}),
            "forensic_markers": result.get("signal_labels", {}),
        }
