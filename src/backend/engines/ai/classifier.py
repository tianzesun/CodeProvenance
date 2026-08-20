"""Lightweight gradient-boosting classifier for AI-generated code.

Trains a HistGradientBoostingClassifier on the combined feature vector
(stylometric + tree-sitter AST + perplexity/burstiness) to classify code as
human- or AI-authored. Includes model versioning and save/load helpers.

The classifier is optional — when no trained model is present, the ensemble
scorer relies on the heuristic signals only.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).parent / "models"


@dataclass
class ClassifierResult:
    """Output of a classifier prediction."""

    ai_probability: float
    evidence: dict[str, Any]
    model_version: str


class AICodeClassifier:
    """Gradient-boosting classifier over AI-detection feature vectors.

    Builds a fixed, ordered feature vector from these sources:

    - ``ast``: 11 tree-sitter features (see ``ASTFeatureVector.feature_names``)
    - ``stylometry``: 9 compact stylometric features
    - ``perplexity``: perplexity, burstiness, avg log-prob

    Call ``train`` with labeled ``(features, is_ai)`` pairs, then ``save``/``load``
    to persist. Use ``predict`` with a new feature dict.
    """

    FEATURE_KEYS = [
        # AST features
        "node_type_entropy",
        "cyclomatic_complexity",
        "avg_identifier_length",
        "identifier_length_std",
        "identifier_naming_entropy",
        "comment_to_code_ratio",
        "blank_line_ratio",
        "avg_function_length",
        "avg_class_length",
        "indentation_consistency",
        "whitespace_entropy",
        # Stylometric features
        "descriptive_var_ratio",
        "docstring_ratio",
        "type_hint_ratio",
        "single_char_var_ratio",
        "exception_handling_ratio",
        "list_comprehension_ratio",
        "var_naming_entropy",
        "avg_statements_per_func",
        "max_nesting_depth",
        # Perplexity/burstiness
        "perplexity",
        "burstiness",
        "avg_log_prob",
    ]

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._version: str | None = None
        self._feature_names: list[str] = list(self.FEATURE_KEYS)

    @property
    def is_trained(self) -> bool:
        """Whether a trained model is loaded."""
        return self._model is not None

    @property
    def version(self) -> str | None:
        """Version of the loaded model."""
        return self._version

    def train(
        self,
        feature_rows: list[dict[str, float]],
        labels: list[int],
        feature_names: list[str] | None = None,
    ) -> str:
        """Train the gradient-boosting classifier.

        Args:
            feature_rows: List of dicts mapping feature names to values.
            labels: Binary labels (1 = AI-generated, 0 = human).
            feature_names: Optional explicit feature ordering.

        Returns:
            The generated model version string.
        """
        if len(feature_rows) != len(labels):
            raise ValueError("feature_rows and labels must be the same length")
        if len(feature_rows) < 10:
            raise ValueError("Need at least 10 labelled samples to train")

        from sklearn.ensemble import HistGradientBoostingClassifier

        names = feature_names or self._feature_names
        matrix = _feature_matrix(feature_rows, names)
        self._feature_names = names

        model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.06,
            max_leaf_nodes=15,
            min_samples_leaf=10,
            l2_regularization=1.0,
            early_stopping=True,
            random_state=42,
        )
        model.fit(matrix, labels)
        self._model = model
        self._version = self._compute_version(feature_rows, labels)
        return self._version

    def _compute_version(
        self, feature_rows: list[dict[str, float]], labels: list[int]
    ) -> str:
        """Compute a short content-derived version fingerprint."""
        digest = hashlib.sha256()
        for row, label in sorted(zip(feature_rows, labels), key=lambda pair: str(pair)):
            digest.update(str(row).encode("utf-8", errors="replace"))
            digest.update(f":{label}".encode())
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        return f"{timestamp}-{digest.hexdigest()[:8]}"

    def predict(self, features: dict[str, float]) -> ClassifierResult:
        """Predict AI-probability from a feature dict.

        Missing features are filled with sensible defaults so partial vectors
        (e.g. a language without AST support) still work.
        """
        if self._model is None:
            return ClassifierResult(
                ai_probability=0.5,
                evidence={"model": "none", "message": "No trained model loaded"},
                model_version="none",
            )

        default_features = _default_feature_values()
        row_values = [
            features.get(name, default_features.get(name, 0.0))
            for name in self._feature_names
        ]
        probability = float(self._model.predict_proba([row_values])[0][1])
        probability = round(max(0.0, min(1.0, probability)), 3)
        return ClassifierResult(
            ai_probability=probability,
            evidence={
                "n_features": len(self._feature_names),
                "model": type(self._model).__name__,
            },
            model_version=self._version or "unknown",
        )

    def save(self, name: str | None = None) -> Path:
        """Persist the trained model to disk with its version."""
        if self._model is None:
            raise RuntimeError("Cannot save an untrained model")
        filename = name or f"ai_code_classifier_{self._version or 'latest'}.joblib"
        path = self.model_dir / filename
        joblib.dump(
            {
                "model": self._model,
                "version": self._version,
                "features": self._feature_names,
            },
            path,
        )
        logger.info("Saved AI code classifier to %s", path)
        return path

    def load(self, path: Path | None = None) -> bool:
        """Load a trained model. Returns True on success."""
        candidate = path
        if candidate is None:
            candidates = sorted(
                self.model_dir.glob("ai_code_classifier_*.joblib"), reverse=True
            )
            candidate = next(iter(candidates), None)
        if candidate is None or not Path(candidate).exists():
            logger.info("No saved AI code classifier found (%s)", candidate)
            return False

        payload = joblib.load(candidate)
        self._model = payload["model"]
        self._version = payload.get("version")
        self._feature_names = payload.get("features", list(self.FEATURE_KEYS))
        logger.info("Loaded AI code classifier %s (%s)", candidate, self._version)
        return True

    def latest_model_path(self) -> Path | None:
        """Return the path of the most recently saved model, if any."""
        candidates = sorted(
            self.model_dir.glob("ai_code_classifier_*.joblib"), reverse=True
        )
        return next(iter(candidates), None)


def _feature_matrix(
    rows: list[dict[str, float]], names: list[str]
) -> list[list[float]]:
    """Convert rows of dicts to a numeric matrix aligned to names."""
    default_features = _default_feature_values()
    matrix = []
    for row in rows:
        matrix.append(
            [row.get(name, default_features.get(name, 0.0)) for name in names]
        )
    return matrix


def _default_feature_values() -> dict[str, float]:
    """Provide neutral defaults for missing feature values."""
    return {
        # AST entropy-ish neutral midpoint
        "node_type_entropy": 0.5,
        "cyclomatic_complexity": 0.2,
        "avg_identifier_length": 0.35,
        "identifier_length_std": 0.2,
        "identifier_naming_entropy": 0.5,
        "comment_to_code_ratio": 0.15,
        "blank_line_ratio": 0.1,
        "avg_function_length": 0.2,
        "avg_class_length": 0.1,
        "indentation_consistency": 0.8,
        "whitespace_entropy": 0.5,
        "descriptive_var_ratio": 0.3,
        "docstring_ratio": 0.2,
        "type_hint_ratio": 0.2,
        "single_char_var_ratio": 0.2,
        "exception_handling_ratio": 0.1,
        "list_comprehension_ratio": 0.1,
        "var_naming_entropy": 0.5,
        "avg_statements_per_func": 0.3,
        "max_nesting_depth": 0.2,
        "perplexity": 5.0,
        "burstiness": 0.5,
        "avg_log_prob": -5.0,
    }


def assemble_features(
    ast_vector: Any,
    stylometry: Any | None = None,
    perplexity: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Assemble the classifier feature dict from the three signal sources.

    Accepts an ``ASTFeatureVector``, an optional stylometry object/features and
    an optional perplexity result dict. Missing sources fall back to defaults
    so the classifier can still run without all modules.
    """
    features: dict[str, float] = {}

    if ast_vector is not None:
        for name in ast_vector.feature_names():
            features[name] = float(getattr(ast_vector, name))

    if stylometry is not None:
        from dataclasses import asdict

        stylometry = asdict(stylometry)
        for name in (
            "descriptive_var_ratio",
            "docstring_ratio",
            "type_hint_ratio",
            "single_char_var_ratio",
            "exception_handling_ratio",
            "list_comprehension_ratio",
            "var_naming_entropy",
            "avg_statements_per_func",
            "max_nesting_depth",
        ):
            features[name] = _coerce(stylometry.get(name))

    if perplexity is not None:
        features["perplexity"] = _coerce(perplexity.get("perplexity"))
        features["burstiness"] = _coerce(perplexity.get("burstiness"))
        features["avg_log_prob"] = _coerce(perplexity.get("avg_log_prob"))

    return features


def _coerce(value: Any | None) -> float:
    """Safely coerce a value to float, 0.0 when missing/uncoercible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
