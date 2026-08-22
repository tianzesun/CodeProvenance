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
from typing import Any, ClassVar

from src.backend.engines.ai.binoculars_detector import BinocularsDetector
from src.backend.engines.similarity.ai_detection import AIDetectionEngine

logger = logging.getLogger(__name__)

# Safe-blend defaults; runtime values come from ai_ensemble_config.yaml.
DEFAULT_ML_BLEND: dict[str, float] = {
    "ml_base_weight": 0.50,
    "ml_min_lines": 25,
    "ml_full_lines": 60,
    "disagreement_gap": 0.35,
    "disagreement_cap": 0.65,
}


def blend_ml_heuristic(
    ml_score: float,
    heuristic_score: float,
    line_count: int,
    config: dict[str, Any] | None = None,
) -> tuple[float, bool]:
    """Blend a trained-classifier score with the explainable heuristic score.

    The classifier's weight grows with code length because its features
    misfire on short files. When the classifier calls AI while the explainable
    signals call human (the false-positive direction), the blend is capped
    below the high-risk threshold instead of convicting on the classifier
    alone. Disagreement in the other direction is never capped — the heuristic
    fingerprints carry their own precision guards.

    Returns (blended_score, disagreement_capped).
    """
    conf = {**DEFAULT_ML_BLEND, **(config or {})}
    min_lines = float(conf["ml_min_lines"])
    full_lines = float(conf["ml_full_lines"])
    if line_count <= min_lines:
        length_factor = 0.2
    elif line_count >= full_lines:
        length_factor = 1.0
    else:
        length_factor = 0.2 + 0.8 * (line_count - min_lines) / (full_lines - min_lines)
    weight = float(conf["ml_base_weight"]) * length_factor
    blended = weight * ml_score + (1.0 - weight) * heuristic_score

    capped = False
    if (ml_score - heuristic_score) > float(conf["disagreement_gap"]):
        cap = float(conf["disagreement_cap"])
        if blended > cap:
            blended = cap
            capped = True
    return blended, capped


def apply_fp_safeguards(
    ai_probability: float, confidence: float, signals: dict[str, float]
) -> tuple[float, float, list[str]]:
    """False-positive safeguards for the live fusion path.

    Ported from ``false_positive_reduction.py`` (the framework path) so the
    live orchestrator gets the same protections: single-signal dominance,
    signal contradiction, and extreme signal variance reduce confidence, and a
    very low safeguarded confidence damps the score toward neutral. The
    framework's variance check could never fire (variance of [0,1] signals is
    capped at 0.25 but the threshold was 0.3); here 0.10 is used so extreme
    spread actually triggers.

    Returns (probability, confidence, notes).
    """
    notes: list[str] = []
    penalty = 0.0
    values = [value for value in signals.values() if isinstance(value, (int, float))]
    if len(values) >= 4:
        ai_like = sum(1 for value in values if value > 0.6)
        human_like = sum(1 for value in values if value < 0.4)
        if (ai_like == 1 and human_like >= 6) or (human_like == 1 and ai_like >= 6):
            penalty += 0.3
            notes.append("Single-signal dominance — confidence reduced")
        if any(value > 0.7 for value in values) and any(
            value < 0.3 for value in values
        ):
            penalty += 0.2
            notes.append("Signal contradiction — confidence reduced")
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        if variance > 0.10:
            penalty += 0.15
            notes.append("Extreme signal variance — confidence reduced")

    adjusted = max(0.0, min(1.0, confidence - penalty))
    if 0.4 <= ai_probability <= 0.6:
        adjusted = max(adjusted, 0.3)
    if adjusted < 0.2:
        ai_probability = ai_probability * 0.8 + 0.1
        notes.append("Low confidence — score damped toward neutral")
    return round(ai_probability, 3), round(adjusted, 3), notes


class AIDetectionOrchestrator:
    """
    Coordinates multiple AI detection layers and produces a fused result.

    Usage:
        orchestrator = AIDetectionOrchestrator()
        result = orchestrator.analyze(code, language="python")
    """

    # Calibrated weights favoring Binoculars (Layer 1) for its published performance
    # Total weight = 1.0
    _LAYER_WEIGHTS: ClassVar[dict[str, float]] = {
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

    def analyze(self, code: str, language: str = "python") -> dict[str, Any]:
        """
        Run the full multi-layer detection pipeline.

        Returns the same shape as the legacy AIDetectionEngine.analyze()
        plus an extra "layers" key for debugging / UI.
        """
        if not code or len(code.strip()) < 20:
            return {
                "ai_probability": 0.0,
                "confidence": 0.0,
                "method": "heuristic",
                "model": "Heuristic statistical fingerprint analysis (no trained model)",
                "signals": {},
                "signal_labels": {},
                "indicators": ["Code too short for reliable detection"],
                "flagged_lines": [],
                "flagged_regions": [],
                "language": language,
                "layers": {},
            }

        # Layer 1: Binoculars
        bino_result = self.binoculars.analyze(code, language=language)

        # Layer 3: Legacy multi-signal engine
        legacy_result = self.legacy_engine.analyze(code, language=language)

        # Layer 4: tree-sitter AST + perplexity + (optional) ML ensemble
        ensemble_result: dict[str, Any] = {}
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
        signals: dict[str, float] = legacy_result.get("signals", {}).copy()

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
        ml_mode = ensemble_result.get("mode") == "ml"
        ml_probability = ensemble_result.get("ai_probability")
        fusion_debug: dict[str, Any] = {}
        fusion_notes: list[str] = []
        if bino_result.get("available"):
            fused_probability = self._weighted_fuse(signals)
        elif ml_mode and ml_probability is not None:
            # A trained classifier is present — blend it with the explainable
            # heuristic score rather than trusting it outright (see
            # blend_ml_heuristic for the length gate and disagreement cap).
            heuristic_probability = self._heuristic_fuse(signals)
            line_count = len(code.splitlines())
            fused_probability, capped = blend_ml_heuristic(
                float(ml_probability),
                heuristic_probability,
                line_count,
                self._blend_config(),
            )
            fusion_debug = {
                "strategy": "ml_blend",
                "ml_score": round(float(ml_probability), 3),
                "heuristic_score": round(heuristic_probability, 3),
                "line_count": line_count,
                "disagreement_capped": capped,
            }
            if capped:
                fusion_notes.append(
                    "Classifier/heuristic disagreement — score capped, "
                    "manual review advised"
                )
        else:
            fused_probability = self._heuristic_fuse(signals)

        # Combine confidence, then apply the false-positive safeguards before
        # the display floor so penalties (and the low-confidence damping they
        # enable) can actually take effect.
        legacy_conf = legacy_result.get("confidence", 0.5)
        bino_conf = (
            bino_result.get("confidence", 0.5) if bino_result.get("available") else 0.5
        )
        raw_confidence = 0.6 * bino_conf + 0.4 * legacy_conf
        fused_probability, safeguarded_confidence, safeguard_notes = (
            apply_fp_safeguards(fused_probability, raw_confidence, signals)
        )
        combined_confidence = max(0.4, safeguarded_confidence)

        # Apply the learned calibrator (trained via /api/ai-detect/retrain) to
        # the fused score so shared calibration feedback affects the live path.
        calibrator = getattr(self.legacy_engine, "calibrator", None)
        if calibrator is not None and callable(getattr(calibrator, "predict", None)):
            try:
                fused_probability = float(calibrator.predict([fused_probability])[0])
            except Exception:  # pragma: no cover  # noqa: S110
                pass  # Keep the sigmoid-calibrated score on failure

        # Merge indicators (prefer Binoculars evidence when strong)
        indicators = list(legacy_result.get("indicators", []))
        if bino_result.get("available") and bino_result.get("ai_probability", 0) > 0.65:
            indicators = [
                f"Binoculars: {bino_result.get('label', 'AI-like')}"
            ] + indicators
        indicators = fusion_notes + safeguard_notes + indicators

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
        if calibrator is not None:
            layers["calibration"] = {
                "available": True,
                "samples": int(getattr(self.legacy_engine, "calibrator_samples", 0)),
            }
        if ensemble_result:
            layers["ensemble"] = {
                "ai_probability": ensemble_result.get("ai_probability"),
                "mode": ensemble_result.get("mode"),
                "signals": ensemble_result.get("signals", {}),
                "classifier": ensemble_result.get("classifier"),
            }
        if fusion_debug:
            layers["fusion"] = fusion_debug

        # Flagged regions from the perplexity/uniformity scanner (line ranges).
        flagged_regions = ensemble_result.get("flagged_regions", [])

        calibration = (
            {
                "available": True,
                "samples": int(getattr(self.legacy_engine, "calibrator_samples", 0)),
            }
            if calibrator is not None
            else {"available": False, "samples": 0}
        )

        using_binoculars = bool(bino_result.get("available"))
        using_ml = ml_mode and ml_probability is not None and not using_binoculars
        return {
            "ai_probability": round(max(0.0, min(1.0, fused_probability)), 3),
            "confidence": round(max(0.0, min(1.0, combined_confidence)), 3),
            "method": (
                "binoculars" if using_binoculars else "ml" if using_ml else "heuristic"
            ),
            "model": (
                "Binoculars zero-shot detector (ICML 2024) fused with heuristics"
                if using_binoculars
                else (
                    "Trained classifier blended with statistical signals "
                    "(safe-blend fusion)"
                    if using_ml
                    else "Heuristic statistical fingerprint analysis (no trained model)"
                )
            ),
            "signals": {k: round(v, 3) for k, v in signals.items()},
            "signal_labels": self.legacy_engine._signal_labels(signals),
            "indicators": indicators[:8],
            "flagged_lines": legacy_result.get("flagged_lines", [])[:30],
            "flagged_regions": flagged_regions[:10],
            "language": language,
            "calibration": calibration,
            "layers": layers,
        }

    def _blend_config(self) -> dict[str, Any]:
        """Load safe-blend settings from the shared ensemble config."""
        try:
            from src.backend.engines.ai.ensemble import AIEnsembleConfig

            return AIEnsembleConfig.get_instance().orchestrator_config()
        except Exception:  # pragma: no cover
            return dict(DEFAULT_ML_BLEND)

    def _weighted_fuse(self, signals: dict[str, float]) -> float:
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

    def _heuristic_fuse(self, signals: dict[str, float]) -> float:
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
