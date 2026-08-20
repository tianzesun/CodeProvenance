import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


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
    Target: 90%+ Accuracy for GPT-4/Claude patterns.
    """

    def __init__(self, model_name: str = "microsoft/codebert-base"):
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._device = None
        # Human vs AI centroids in embedding space (Pre-calculated from benchmark)
        self._human_centroid = None
        self._ai_centroid = None

    def _load_model(self):
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
        """Extract mean-pooled CodeBERT embedding."""
        import torch

        inputs = self._tokenizer(
            code, return_tensors="pt", truncation=True, max_length=512, padding=True
        ).to(self._device)
        with torch.no_grad():
            outputs = self._model(**inputs)
            # Use [CLS] token or mean pooling
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
        Detects 'AI-Fingerprints' in code:
        - Perfect PEP8 adherence (too perfect)
        - Descriptive but generic variable names (input_data, result_list)
        - Balanced cyclomatic complexity
        - High presence of standard library idioms
        """
        score = 0.0
        lines = code.splitlines()
        if not lines:
            return 0.0

        # 1. Structural Entropy (AI is often lower entropy/more predictable)
        # 2. Comment Pattern (AI uses very specific docstring/comment styles)
        if '"""' in code and ":" in code:
            score += 0.2  # Standard docstrings

        # 3. List Comprehension / Functional Density
        if ".map(" in code or "[" in code and "for" in code:
            score += 0.1

        # 4. Perfect Indentation
        if all(
            len(line) - len(line.lstrip()) % 4 == 0 for line in lines if line.strip()
        ):
            score += 0.2

        return score + 0.4  # Baseline for modern LLMs


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

    def analyze(self, code: str) -> dict[str, Any]:
        """Deep forensic analysis for AI presence."""
        result = self._orchestrator.analyze(code)
        ai_prob = result.get("ai_probability", 0.0)
        confidence = result.get("confidence", 0.0)

        if ai_prob >= 0.7:
            decision = "likely_ai"
        elif ai_prob >= 0.4:
            decision = "review"
        else:
            decision = "likely_human"

        return {
            "ai_probability": round(ai_prob, 4),
            "is_ai_generated": ai_prob > 0.85,
            "confidence": round(confidence, 4),
            "decision": decision,
            "methodology": "Heuristic signal ensemble",
            "indicators": result.get("indicators", []),
            "signals": result.get("signals", {}),
            "forensic_markers": result.get("signal_labels", {}),
        }
