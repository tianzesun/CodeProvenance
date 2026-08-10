"""Ensemble scorer for AI-generated code detection.

Combines the tree-sitter AST features, stylometry, perplexity/burstiness, and
(optionally) the trained ML classifier into a single weighted AI-likelihood
score. Weights and thresholds are loaded from ``ai_ensemble_config.yaml`` so
calibration can be tuned without code changes.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

import yaml

from src.backend.engines.ai.ast_features import TreeSitterASTExtractor
from src.backend.engines.ai.classifier import AICodeClassifier, assemble_features
from src.backend.engines.ai.perplexity import PerplexityScorer

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "ai_ensemble_config.yaml"


class AIEnsembleConfig:
    """Loads and validates the AI ensemble configuration.

    Follows the ``EngineWeightConfig`` pattern: singleton, lazy load, graceful
    fallback to defaults when the file is missing.
    """

    _instance: Optional[AIEnsembleConfig] = None
    _lock = Lock()

    DEFAULTS: Dict[str, Any] = {
        "ensemble": {
            "heuristic": {
                "ast": 0.20,
                "stylometry": 0.25,
                "perplexity": 0.25,
                "burstiness": 0.15,
                "pattern_library": 0.15,
            },
            "ml": {
                "classifier": 0.45,
                "ast": 0.15,
                "stylometry": 0.15,
                "perplexity": 0.15,
                "burstiness": 0.10,
            },
        },
        "thresholds": {
            "medium_risk": 0.40,
            "high_risk": 0.70,
            "refactor_selection": 0.35,
        },
        "classification": {"enabled": False, "model_dir": None},
        "perplexity": {
            "window_lines": 25,
            "overlap_lines": 5,
            "huggingface_model": "",
        },
    }

    @classmethod
    def get_instance(cls) -> AIEnsembleConfig:
        """Return the shared singleton."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = AIEnsembleConfig()
            return cls._instance

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = self._deep_copy(self.DEFAULTS)
        self._reload()

    def _reload(self) -> None:
        """(Re)load configuration from the YAML file with validation."""
        config: Dict[str, Any] = self._deep_copy(self.DEFAULTS)
        if self.config_path.exists():
            try:
                loaded = (
                    yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
                )
                if isinstance(loaded, dict):
                    config = self._deep_merge(config, loaded)
            except yaml.YAMLError as exc:
                logger.warning(
                    "Invalid AI ensemble config %s: %s", self.config_path, exc
                )
        self._config = config

    @staticmethod
    def _deep_copy(value: Any) -> Any:
        import copy

        return copy.deepcopy(value)

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = AIEnsembleConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def weights(self, mode: str = "heuristic") -> Dict[str, float]:
        """Return weighting factors for the given scoring mode."""
        return self._config["ensemble"].get(mode, self.DEFAULTS["ensemble"][mode])

    def threshold(self, name: str, default: float) -> float:
        """Look up a threshold by name with fallback."""
        return float(self._config["thresholds"].get(name, default))

    @property
    def classification_enabled(self) -> bool:
        """Whether the trained classifier should be used."""
        return bool(self._config["classification"].get("enabled", False))

    @property
    def model_dir(self) -> Optional[Path]:
        """Configured model directory override."""
        raw = self._config["classification"].get("model_dir")
        return Path(raw) if raw else None

    def perplexity_config(self) -> Dict[str, Any]:
        """Return the perplexity scorer settings."""
        return self._config.get("perplexity", self.DEFAULTS["perplexity"])

    def reload(self) -> None:
        """Force a reload from disk."""
        self._reload()


class AIEnsembleScorer:
    """Fuse AST, stylometry, perplexity and classifier signals into one score.

    Usage::

        scorer = AIEnsembleScorer()
        result = scorer.score(code, language="python")
    """

    def __init__(
        self,
        config: Optional[AIEnsembleConfig] = None,
        model_dir: Optional[Path] = None,
    ) -> None:
        self.config = config or AIEnsembleConfig.get_instance()
        self._ast_extractor = TreeSitterASTExtractor()
        self._perplexity_scorer: Optional[PerplexityScorer] = None
        self._classifier: Optional[AICodeClassifier] = None
        self._model_dir = model_dir
        self._init_optional_components()

    def _init_optional_components(self) -> None:
        """Lazily initialise perplexity scorer and classifier."""
        pconf = self.config.perplexity_config()
        self._perplexity_scorer = PerplexityScorer(
            model_path=pconf.get("huggingface_model") or None,
            window=int(pconf.get("window_lines", 25)),
            overlap=int(pconf.get("overlap_lines", 5)),
        )

        if self.config.classification_enabled:
            classifier = AICodeClassifier(
                model_dir=self._model_dir or self.config.model_dir
            )
            if classifier.load():
                self._classifier = classifier
            else:
                logger.info(
                    "Classification enabled but no model found; using heuristic"
                )

    @property
    def classifier_available(self) -> bool:
        """Whether a trained classifier is loaded."""
        return self._classifier is not None and self._classifier.is_trained

    def score(
        self,
        code: str,
        language: str = "python",
        pattern_library: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compute the fused AI-likelihood score and per-signal breakdown.

        Args:
            code: Source code text.
            language: Detected language (python, java, cpp, ...).
            pattern_library: Optional pre-computed LLM-fingerprint signal from
                the legacy heuristic engine (0-1), used as an extra input.

        Returns:
            Dict with keys ``ai_probability``, ``method``, ``signals``,
            ``probability_sources``, ``flagged_regions``, ``classifier``,
            ``perplexity_sources`` and ``config``.
        """
        if not code or len(code.strip()) < 20:
            return {
                "ai_probability": 0.0,
                "method": "ensemble",
                "signals": {},
                "flagged_regions": [],
                "language": language,
                "model": "sklearn HistGradientBoosting",
                "confidence": 0.0,
                "mode": "heuristic",
                "phrased": "Code too short for analysis",
            }

        # 1. AST features
        ast_vector = self._ast_extractor.extract(code, language)
        ast_signals = self._ratio_signals(ast_vector)

        # 2. Stylometry
        stylometry = self._extract_stylometry(code, language)
        stylometry_signals = self._stylometry_signals(stylometry)

        # 3. Perplexity / burstiness
        perp_result = self._perplexity_scorer.score(code)
        # Map a perplexity value to an AI-likeness score in [0,1].
        perplexity_score = max(0.0, min(1.0, (10.0 - perp_result["perplexity"]) / 10.0))
        signals = {
            "ast": _mean_signals(ast_signals),
            "stylometry": _mean_signals(stylometry_signals),
            "perplexity": round(perplexity_score, 3),
            "burstiness": round(perp_result["burstiness"], 3),
            "pattern_library": round(float(pattern_library or 0.0), 3),
        }

        # 4. ML classifier (optional)
        classifier_result = None
        classifier_probability: Optional[float] = None
        if self.classifier_available:
            features = assemble_features(ast_vector, stylometry, perp_result)
            classifier_result = self._classifier.predict(features)
            classifier_probability = classifier_result.ai_probability

        # 5. Fuse
        mode = "ml" if classifier_probability is not None else "heuristic"
        weights = self.config.weights(mode)
        fused = self._fuse(signals, weights, classifier_probability, mode)

        flagged_regions = self._flag_regions(code, perp_result, ast_vector)

        return {
            "ai_probability": round(fused, 3),
            "method": "ensemble",
            "mode": mode,
            "signals": signals,
            "probability_sources": _prob_sources(fused),
            "flagged_regions": flagged_regions,
            "language": language,
            "classifier": (
                {
                    "ai_probability": classifier_probability,
                    "version": classifier_result.model_version,
                }
                if classifier_result
                else None
            ),
            "perplexity_sources": perp_result,
            "model": "sklearn HistGradientBoosting",
            "confidence": _confidence_from_signals(signals, fused),
            "config": {"mode": mode, "weights": weights},
        }

    def _fuse(
        self,
        signals: Dict[str, float],
        weights: Dict[str, float],
        classifier_probability: Optional[float],
        mode: str,
    ) -> float:
        """Weighted combination of signals plus sigmoid calibration."""
        total = 0.0
        weight_sum = 0.0
        for name, weight in weights.items():
            if name == "classifier" and classifier_probability is not None:
                total += classifier_probability * weight
                weight_sum += weight
            elif name in signals:
                total += signals[name] * weight
                weight_sum += weight
        if weight_sum == 0:
            return 0.5
        raw = total / weight_sum
        k = 6.0
        return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-k * (raw - 0.5)))))

    def _extract_stylometry(self, code: str, language: str) -> Any:
        """Extract stylometric features using the existing StylometryExtractor."""
        try:
            from src.backend.engines.features.code_stylometry import StylometryExtractor

            return StylometryExtractor().extract(code, doc_id="")
        except Exception as exc:  # pragma: no cover
            logger.info("Stylometry extraction failed: %s", exc)
            return None

    def _ratio_signals(self, vector: Any) -> Dict[str, float]:
        """Turn an ASTFeatureVector into [0,1] AI-likeness signals.

        Higher values indicate AI-like structure: uniform node distribution,
        consistent indent, very regular identifiers.
        """
        if vector is None:
            return {}
        return {
            "node_entropy": round(1.0 - _ratio(vector.node_type_entropy, 9.0), 3),
            "indentation": round(float(vector.indentation_consistency), 3),
            "whitespace": round(1.0 - _ratio(vector.whitespace_entropy, 1.0), 3),
            "complexity_uniformity": round(
                1.0 - _ratio(vector.cyclomatic_complexity, 1.0), 3
            ),
            "identifier_regularity": round(
                max(
                    vector.identifier_naming_entropy,
                    1.0 - _ratio(vector.identifier_length_std, 5.0),
                ),
                3,
            ),
        }

    def _stylometry_signals(self, stylometry: Any) -> Dict[str, float]:
        """Convert stylometry features to AI-likeness signals."""
        if stylometry is None:
            return {}
        from dataclasses import asdict

        data = asdict(stylometry)
        return {
            "descriptive_names": round(_ratio(data.get("descriptive_var_ratio")), 3),
            "docstring_density": round(_ratio(data.get("docstring_ratio")), 3),
            "type_hint_density": round(_ratio(data.get("type_hint_ratio")), 3),
            "simple_names": round(_ratio(data.get("single_char_var_ratio")), 3),
            "naming_uniformity": round(_ratio(data.get("var_naming_entropy")), 3),
            "nesting_shallowness": round(
                1.0 - _ratio(data.get("max_nesting_depth"), 5.0), 3
            ),
            "comprehension_density": round(
                _ratio(data.get("list_comprehension_ratio")), 3
            ),
        }

    def _flag_regions(
        self, code: str, perp_result: Dict[str, Any], ast_vector: Any
    ) -> list:
        """Identify regions worth flagging (low perplexity / high uniformity).

        Returns a list of ``{start_line, end_line, reason, severity}`` dicts.
        """
        flagged = []
        for i, chunk in enumerate(perp_result.get("per_chunk", [])):
            perplexity = chunk.get("perplexity", 0.0)
            if perplexity < 2.0:
                flagged.append(
                    {
                        "start_line": i * (25 - 5) + 1,
                        "end_line": i * (25 - 5) + chunk.get("chunk_lines", 25),
                        "reason": "low_perplexity",
                        "severity": "high",
                        "detail": f"Perplexity {perplexity:.2f} suggests very predictable code",
                    }
                )
        return flagged[:10]

    def detect_ai(self, code: str, language: str = "python") -> bool:
        """Convenience binary verdict for callers that need one."""
        return self.score(code, language)["ai_probability"] >= self.config.threshold(
            "medium_risk", 0.40
        )


def _ratio(value: Any, scale: float = 1.0) -> float:
    """Clamp a value to [0, scale] and normalise to [0,1]."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if scale <= 0:
        return 0.0
    return max(0.0, min(scale, numeric)) / scale


def _mean_signals(signals: Dict[str, float]) -> float:
    """Mean of signal values, 0.0 for empty."""
    if not signals:
        return 0.0
    return round(sum(signals.values()) / len(signals), 3)


def _prob_sources(fused: float) -> Dict[str, float]:
    """Return a simple source breakdown for UI display."""
    return {"fusion": round(fused, 3)}


def _confidence_from_signals(signals: Dict[str, float], ai_prob: float) -> float:
    """Derive a confidence value from signal agreement and extremity."""
    values = [value for value in signals.values() if 0.0 <= value <= 1.0]
    if not values:
        return 0.0
    spread = max(values) - min(values) if len(values) > 1 else 0.0
    # Agreement (low spread) + extremeness push confidence up
    agreement = 1.0 - spread
    extremity = 2.0 * abs(ai_prob - 0.5)
    return round(max(0.0, min(1.0, 0.5 * agreement + 0.5 * extremity)), 3)
