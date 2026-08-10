"""AIDetectionOrchestrator

Multi-layer AI code detector orchestrator.

Current layers (code-only):
- Layer 1: Binoculars (zero-shot, high precision, low FPR)
- Layer 3: Statistical + Stylometric + Pattern signals (existing 8-signal engine)

Future layers (when data is available):
- Layer 2: Fine-tuned RoBERTa / CodeBERT classifier

The orchestrator runs all available detectors, applies calibrated weights,
and returns a unified result compatible with the existing AI detection pipeline.

This design makes it easy to later support plain-text/essay detection by
adding a TextOrchestrator or a "domain" parameter.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

from src.backend.engines.ai.binoculars_detector import BinocularsDetector
from src.backend.engines.similarity.ai_detection import AIDetectionEngine

logger = logging.getLogger(__name__)


class AIDetectionOrchestrator:
    """
    Coordinates multiple AI detection layers and produces a fused result.

    Usage:
        orchestrator = AIDetectionOrchestrator()
        result = orchestrator.analyze(code, language="python")
    """

    # Calibrated weights favoring Binoculars (Layer 1) for its published performance
    # Total weight = 1.0
    _LAYER_WEIGHTS: Dict[str, float] = {
        "binoculars": 0.40,  # Zero-shot SOTA (ICML 2024)
        "pattern_library": 0.15,
        "perplexity": 0.12,
        "stylometry": 0.10,
        "burstiness": 0.08,
        "structural_entropy": 0.07,
        "vocabulary_richness": 0.04,
        "whitespace_rhythm": 0.02,
        "docstring_density": 0.02,
    }

    def __init__(self) -> None:
        self.binoculars = BinocularsDetector()
        self.legacy_engine = AIDetectionEngine()
        self._ensemble = None
        self._ensemble_attempted = False

    def _get_ensemble(self) -> Any:
        """Lazily create the tree-sitter/perplexity/ML ensemble scorer.

        Constructing it instantiates the perplexity scorer and attempts to
        load a trained classifier — both cheap no-ops when absent, so deferring
        the import keeps orchestrator construction fast.
        """
        if self._ensemble is None and not self._ensemble_attempted:
            self._ensemble_attempted = True
            try:
                from src.backend.engines.ai.ensemble import AIEnsembleScorer

                self._ensemble = AIEnsembleScorer()
            except Exception as exc:  # pragma: no cover
                logger.info("AI ensemble scorer unavailable: %s", exc)
                self._ensemble = None
        return self._ensemble

    def analyze(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Run the full multi-layer detection pipeline.

        Returns the same shape as the legacy AIDetectionEngine.analyze()
        plus an extra "layers" key for debugging / UI.
        """
        if not code or len(code.strip()) < 20:
            return {
                "ai_probability": 0.0,
                "confidence": 0.0,
                "signals": {},
                "signal_labels": {},
                "indicators": ["Code too short for reliable detection"],
                "flagged_lines": [],
                "language": language,
                "layers": {},
            }

        # Layer 1: Binoculars
        bino_result = self.binoculars.analyze(code, language=language)

        # Layer 3: Legacy multi-signal engine
        legacy_result = self.legacy_engine.analyze(code, language=language)

        # Layer 4: tree-sitter AST + perplexity + (optional) ML ensemble
        ensemble_result: Dict[str, Any] = {}
        ensemble = self._get_ensemble()
        if ensemble is not None:
            try:
                ensemble_result = ensemble.score(
                    code,
                    language=language,
                    pattern_library=legacy_result.get("signals", {}).get(
                        "pattern_library", 0.0
                    ),
                )
            except Exception as exc:  # pragma: no cover
                logger.info("AI ensemble scoring failed: %s", exc)
                ensemble_result = {}

        # Merge signals
        signals: Dict[str, float] = legacy_result.get("signals", {}).copy()

        if bino_result.get("available"):
            signals["binoculars"] = bino_result["ai_probability"]

        # Enrich with ensemble signals (tree-sitter + stylometry signals).
        if ensemble_result.get("signals"):
            for name in ("ast", "perplexity", "burstiness", "stylometry"):
                if name in ensemble_result["signals"]:
                    signals[name] = ensemble_result["signals"][name]

        # Re-fuse using the orchestrator's weights (which favor Binoculars).
        # Without Binoculars the full grid is too noisy for code (perplexity is
        # ~0 for code, whitespace/vocabulary barely separate), so use the
        # heuristic-only path tuned for the signal ensemble.
        if bino_result.get("available"):
            fused_probability = self._weighted_fuse(signals)
        elif ensemble_result.get("mode") == "ml" and ensemble_result.get(
            "ai_probability"
        ):
            # A trained classifier is present — trust the ML ensemble score.
            fused_probability = ensemble_result["ai_probability"]
        else:
            fused_probability = self._heuristic_fuse(signals)

        # Combine confidence
        legacy_conf = legacy_result.get("confidence", 0.5)
        bino_conf = (
            bino_result.get("confidence", 0.5) if bino_result.get("available") else 0.5
        )
        combined_confidence = max(0.4, (0.6 * bino_conf + 0.4 * legacy_conf))

        # Merge indicators (prefer Binoculars evidence when strong)
        indicators = legacy_result.get("indicators", [])
        if bino_result.get("available") and bino_result.get("ai_probability", 0) > 0.65:
            indicators = [
                f"Binoculars: {bino_result.get('label', 'AI-like')}"
            ] + indicators

        layers = {
            "binoculars": {
                "ai_probability": bino_result.get("ai_probability"),
                "confidence": bino_result.get("confidence"),
                "available": bino_result.get("available", False),
            },
            "legacy": {
                "ai_probability": legacy_result.get("ai_probability"),
                "confidence": legacy_result.get("confidence"),
            },
        }
        if ensemble_result:
            layers["ensemble"] = {
                "ai_probability": ensemble_result.get("ai_probability"),
                "mode": ensemble_result.get("mode"),
                "signals": ensemble_result.get("signals", {}),
                "classifier": ensemble_result.get("classifier"),
            }

        # Flagged regions from the perplexity/uniformity scanner (line ranges).
        flagged_regions = ensemble_result.get("flagged_regions", [])

        return {
            "ai_probability": round(max(0.0, min(1.0, fused_probability)), 3),
            "confidence": round(max(0.0, min(1.0, combined_confidence)), 3),
            "method": "binoculars" if bino_result.get("available") else "heuristic",
            "model": (
                "Binoculars zero-shot detector (ICML 2024) fused with heuristics"
                if bino_result.get("available")
                else "Heuristic statistical fingerprint analysis (no trained model)"
            ),
            "signals": {k: round(v, 3) for k, v in signals.items()},
            "signal_labels": self.legacy_engine._signal_labels(signals),
            "indicators": indicators[:8],
            "flagged_lines": legacy_result.get("flagged_lines", [])[:30],
            "flagged_regions": flagged_regions[:10],
            "language": language,
            "layers": layers,
        }

    def _weighted_fuse(self, signals: Dict[str, float]) -> float:
        """Apply orchestrator weights (Binoculars gets the highest weight)."""
        total = 0.0
        weight_sum = 0.0

        for name, w in self._LAYER_WEIGHTS.items():
            if name in signals:
                total += signals[name] * w
                weight_sum += w

        if weight_sum == 0:
            return 0.5

        raw = total / weight_sum

        # Mild calibration (same style as legacy)
        k = 5.5
        calibrated = 1.0 / (1.0 + math.exp(-k * (raw - 0.5)))
        return calibrated

    def _heuristic_fuse(self, signals: Dict[str, float]) -> float:
        """Fuse the heuristic signals when Binoculars is unavailable.

        Uses only the signals that meaningfully separate AI from human code:
        fingerprint patterns, docstring over-documentation, stylometry, and
        burstiness. The Binoculars-heavy weight grid dilutes these into noise
        when the 0.40 binoculars weight is missing, so it is bypassed here.

        A sharp boost is applied whenever high-precision fingerprint patterns
        fire (>=0.30), which pushes genuine AI samples decisively above the
        ``0.70`` "high risk" threshold while leaving humans below ``0.30``.
        """
        pattern = signals.get("pattern_library", 0.0)
        docstring = signals.get("docstring_density", 0.0)
        stylometry = signals.get("stylometry", 0.0)
        burstiness = signals.get("burstiness", 0.0)

        raw = 0.45 * pattern + 0.20 * docstring + 0.20 * stylometry + 0.15 * burstiness
        # High-precision fingerprint evidence gets an additional boost.
        boost = 0.18 * pattern if pattern >= 0.30 else 0.0
        k = 6.0
        return 1.0 / (1.0 + math.exp(-k * ((raw + boost) - 0.5)))
