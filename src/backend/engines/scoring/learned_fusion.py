"""Learned fusion scorer for the production scoring path.

Trains a calibrated logistic model over the production similarity features
(ast, fingerprint, embedding, ngram, winnowing, logic_flow) on labeled
datasets. The trained coefficients are stored as plain JSON so the runtime
scoring path has no scikit-learn or pickle dependency and degrades gracefully
to the rule-based ``FusionEngine`` score when the artifact is missing.
"""

from __future__ import annotations

import json
import math
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent / "similarity" / "models"
ARTIFACT_NAME = "learned_fusion_model.json"
ARTIFACT_VERSION = "1"

DEFAULT_FEATURE_NAMES: Tuple[str, ...] = (
    "ast",
    "fingerprint",
    "embedding",
    "ngram",
    "winnowing",
    "logic_flow",
    "coverage",
)


def _sigmoid(value: float) -> float:
    """Logistic sigmoid clipped for numeric stability."""
    if value != value:  # NaN
        return 0.5
    clipped = max(-30.0, min(30.0, value))
    return 1.0 / (1.0 + math.exp(-clipped))


class LearnedFusionScorer:
    """Score a code pair with the trained logistic fusion model.

    The model estimates ``P(plagiarism | features)``. When the artifact is not
    present, ``available`` is False and callers fall back to the rule-based
    fusion score.
    """

    def __init__(self, artifact_path: Optional[Path] = None) -> None:
        self._artifact_path = (
            Path(artifact_path) if artifact_path else MODELS_DIR / ARTIFACT_NAME
        )
        self._feature_names: List[str] = []
        self._coefficients: List[float] = []
        self._intercept: float = 0.0
        self._metadata: Dict[str, Any] = {}
        self._available = False
        self._load()

    @property
    def available(self) -> bool:
        """True when a valid trained artifact was loaded."""
        return self._available

    @property
    def feature_names(self) -> List[str]:
        """Order of coefficients used by the loaded model."""
        return list(self._feature_names)

    def version_info(self) -> Dict[str, Any]:
        """Return training metadata embedded in the artifact."""
        return dict(self._metadata)

    def _load(self) -> None:
        """Load and validate the JSON artifact."""
        if not self._artifact_path.exists():
            logger.info(
                "No learned fusion artifact at %s; using rule-based scoring",
                self._artifact_path,
            )
            return
        try:
            payload = json.loads(self._artifact_path.read_text(encoding="utf-8"))
            features = payload.get("feature_names", [])
            coefficients = payload.get("coefficients", [])
            intercept = payload.get("intercept", 0.0)
            if not features or len(features) != len(coefficients):
                raise ValueError(
                    "artifact feature_names/coefficients length mismatch: "
                    f"{len(features)} vs {len(coefficients)}"
                )
            if payload.get("version") != ARTIFACT_VERSION:
                raise ValueError(
                    "unsupported artifact version "
                    f"{payload.get('version')} != {ARTIFACT_VERSION}"
                )
            names = [str(name) for name in features]
            if len(set(names)) != len(names):
                raise ValueError("artifact feature_names contains duplicates")
            values = [float(value) for value in coefficients]
            bias = float(intercept)
            # JSON written by Python may contain NaN/Infinity. ``_sigmoid`` clamps its input with
            # ``min(30, nan)``, which is 30, so one NaN coefficient made EVERY pair score 1.0.
            if not all(math.isfinite(v) and abs(v) <= 1e4 for v in [*values, bias]):
                raise ValueError("artifact contains non-finite or implausibly large coefficients")
            self._feature_names = names
            self._coefficients = values
            self._intercept = bias
            self._metadata = payload.get("metadata", {})
            self._available = True
            logger.info(
                "Loaded learned fusion artifact from %s (%s features, AUC=%.4f)",
                self._artifact_path,
                len(self._feature_names),
                self._metadata.get("auc_roc", 0.0),
            )
        except Exception as exc:
            logger.warning(
                "Learned fusion artifact at %s is invalid (%s); "
                "falling back to rule-based scoring",
                self._artifact_path,
                exc,
            )
            self._available = False

    def score(self, features: Dict[str, float]) -> float:
        """Return calibrated plagiarism probability in [0, 1].

        Missing features are treated as 0.0 to match extraction defaults.
        """
        if not self._available:
            return 0.0
        linear = self._intercept
        for name, coefficient in zip(self._feature_names, self._coefficients):
            value = features.get(name)
            try:
                number = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                number = 0.0
            if not math.isfinite(number):
                number = 0.0  # a NaN feature must not become a NaN (then 1.0) probability
            linear += coefficient * max(0.0, min(1.0, number))  # features are unit-scale scores
        return _sigmoid(linear)

    def try_score(self, features: Dict[str, float]) -> Optional[float]:
        """Like :meth:`score`, but ``None`` when no model is loaded.

        ``score`` returns 0.0 when unavailable, which a caller that forgets to check
        ``available`` reads as "no plagiarism"."""
        return self.score(features) if self._available else None
