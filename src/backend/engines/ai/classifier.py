"""Lightweight gradient-boosting classifier for AI-generated code.

Trains a HistGradientBoostingClassifier on the combined feature vector
(stylometric + tree-sitter AST + perplexity/burstiness) to classify code as
human- or AI-authored. Includes model versioning and save/load helpers.

The classifier is optional — when no trained model is present, the ensemble
scorer relies on the heuristic signals only.

Safety properties of the persisted model
----------------------------------------
* ``FEATURE_SCHEMA_VERSION`` identifies the definition of the input features.
  A model trained under a different schema is REFUSED at load time (the
  ensemble then falls back to its explainable heuristics), because applying a
  classifier to features computed differently from its training data yields
  confident but meaningless probabilities. Set ``AICODE_ALLOW_STALE_MODEL=1``
  to override deliberately.
* Models are pickles. ``save`` writes a SHA-256 sidecar and ``load`` verifies it
  when present, so a modified model file is rejected instead of executed.
"""

from __future__ import annotations

import hashlib
import logging
import os
import statistics
import tempfile
import threading
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, ClassVar

import joblib

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).parent / "models"

#: Bump whenever the meaning of any FEATURE_KEYS value changes (extractor
#: fixes, new definitions). v2: stylometry/AST/perplexity feature definitions
#: were corrected (type-hint and nesting features were previously constant,
#: indentation consistency was effectively always 0, cyclomatic complexity now
#: counts ``while``, burstiness is neutral for single-chunk files).
FEATURE_SCHEMA_VERSION = 2

_MODEL_GLOB = "ai_code_classifier_*.joblib"


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

    FEATURE_KEYS: ClassVar[list] = [
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
        # The directory is NOT created here. Constructing a classifier only to
        # predict used to create ``models/`` as a side effect, which raises on a
        # read-only filesystem and took the whole ensemble down with it.
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self._model = None
        self._version: str | None = None
        self._feature_names: list[str] = list(self.FEATURE_KEYS)
        self._defaults: dict[str, float] = {}
        #: How the training features were produced, e.g. ``{"perplexity_model":
        #: "statistical"}``. The ensemble refuses to use a classifier whose
        #: training perplexity model differs from the one scoring the code.
        self.metadata: dict[str, Any] = {}
        self.stale_reason: str | None = None

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
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Train the gradient-boosting classifier.

        Args:
            feature_rows: List of dicts mapping feature names to values.
            labels: Binary labels (1 = AI-generated, 0 = human).
            feature_names: Optional explicit feature ordering.
            metadata: How the features were produced (see ``self.metadata``).

        Returns:
            The generated model version string.
        """
        if len(feature_rows) != len(labels):
            raise ValueError("feature_rows and labels must be the same length")
        if len(feature_rows) < 10:
            raise ValueError("Need at least 10 labelled samples to train")
        if set(labels) != {0, 1}:
            # One class made predict_proba return one column, and the first
            # prediction failed with an IndexError long after training "worked".
            raise ValueError("labels must contain both classes, encoded as 0 and 1")

        from sklearn.ensemble import HistGradientBoostingClassifier

        names = list(feature_names or self._feature_names)
        # Fallback values for features missing at prediction time are the
        # TRAINING MEDIANS. The old hard-coded "neutral" values sat on a
        # different scale from the real features (e.g. 0.2 for a function length
        # measured in lines).
        self._defaults = _training_medians(feature_rows, names)
        matrix = _feature_matrix(feature_rows, names, self._defaults)
        self._feature_names = names
        self.metadata = dict(metadata or {})

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
        self.stale_reason = None
        self._version = self._compute_version(feature_rows, labels)
        return self._version

    def _compute_version(
        self, feature_rows: list[dict[str, float]], labels: list[int]
    ) -> str:
        """Compute a short version fingerprint (training-content hash + timestamp)."""
        digest = hashlib.sha256()
        for row, label in sorted(zip(feature_rows, labels), key=lambda pair: str(pair)):
            digest.update(str(row).encode("utf-8", errors="replace"))
            digest.update(f":{label}".encode())
        import datetime

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M")
        return f"{timestamp}-{digest.hexdigest()[:8]}"

    def _row_defaults(self) -> dict[str, float]:
        return {**_default_feature_values(), **self._defaults}

    def predict(self, features: dict[str, float]) -> ClassifierResult:
        """Predict AI-probability from a feature dict.

        Missing features are filled with the training medians so partial vectors
        (e.g. a language without AST support) still work.
        """
        if self._model is None:
            return ClassifierResult(
                ai_probability=0.5,
                evidence={"model": "none", "message": "No trained model loaded"},
                model_version="none",
            )
        return self.predict_many([features])[0]

    def predict_many(self, rows: list[dict[str, float]]) -> list[ClassifierResult]:
        """Vectorised prediction: one model call for the whole batch."""
        if self._model is None:
            return [self.predict({}) for _ in rows]
        if not rows:
            return []
        matrix = _feature_matrix(rows, self._feature_names, self._row_defaults())
        probabilities = self._model.predict_proba(matrix)[:, 1]
        evidence = {
            "n_features": len(self._feature_names),
            "model": type(self._model).__name__,
        }
        return [
            ClassifierResult(
                ai_probability=round(max(0.0, min(1.0, float(p))), 3),
                evidence=dict(evidence),
                model_version=self._version or "unknown",
            )
            for p in probabilities
        ]

    # -- persistence -----------------------------------------------------

    def save(self, name: str | None = None) -> Path:
        """Persist the trained model to disk with its version and checksum."""
        if self._model is None:
            raise RuntimeError("Cannot save an untrained model")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        filename = name or f"ai_code_classifier_{self._version or 'latest'}.joblib"
        path = self.model_dir / filename
        payload = {
            "model": self._model,
            "version": self._version,
            "features": self._feature_names,
            "defaults": self._defaults,
            "schema_version": FEATURE_SCHEMA_VERSION,
            "metadata": self.metadata,
        }
        # Write to a temp file and rename, so a crash never leaves a truncated
        # model that the next start would try to load.
        fd, tmp_name = tempfile.mkstemp(dir=self.model_dir, suffix=".tmp")
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            joblib.dump(payload, tmp_path)
            checksum = _sha256_file(tmp_path)
            tmp_path.replace(path)
        finally:
            tmp_path.unlink(missing_ok=True)
        _checksum_path(path).write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
        logger.info("Saved AI code classifier to %s", path)
        return path

    def _candidates(self) -> list[Path]:
        if not self.model_dir.is_dir():
            return []
        return sorted(self.model_dir.glob(_MODEL_GLOB), reverse=True)

    def load(self, path: Path | None = None) -> bool:
        """Load a trained model. Returns True on success.

        Never raises for a bad model file: a corrupt, tampered, incompatible or
        stale model is logged and refused so the caller falls back to the
        heuristic path instead of failing every analysis.
        """
        candidates = [Path(path)] if path is not None else self._candidates()
        if not candidates:
            logger.info("No saved AI code classifier found in %s", self.model_dir)
            return False
        for candidate in candidates:
            if self._load_one(candidate):
                return True
        return False

    def _load_one(self, candidate: Path) -> bool:
        if not candidate.exists():
            logger.info("No saved AI code classifier found (%s)", candidate)
            return False

        sidecar = _checksum_path(candidate)
        if sidecar.exists():
            expected = sidecar.read_text(encoding="utf-8").split()[0:1]
            if not expected or expected[0] != _sha256_file(candidate):
                logger.error("Refusing %s: checksum does not match %s", candidate, sidecar.name)
                return False
        else:
            logger.warning("No checksum recorded for %s; loading unverified", candidate.name)

        try:
            payload = joblib.load(candidate)
            model = payload["model"]
        except Exception as exc:
            logger.warning("Could not load classifier %s: %s", candidate, exc)
            return False

        schema = payload.get("schema_version")
        if schema != FEATURE_SCHEMA_VERSION and os.environ.get("AICODE_ALLOW_STALE_MODEL") != "1":
            self.stale_reason = (
                f"{candidate.name} was trained on feature schema {schema!r}; this code "
                f"computes schema {FEATURE_SCHEMA_VERSION}. Retrain with "
                f"train_classifier (or set AICODE_ALLOW_STALE_MODEL=1 to use it anyway)."
            )
            logger.warning("Classifier not used: %s", self.stale_reason)
            return False

        self._model = model
        self._version = payload.get("version")
        self._feature_names = list(payload.get("features") or self.FEATURE_KEYS)
        self._defaults = dict(payload.get("defaults") or {})
        self.metadata = dict(payload.get("metadata") or {})
        self.stale_reason = None
        logger.info("Loaded AI code classifier %s (%s)", candidate, self._version)
        return True

    def latest_model_path(self) -> Path | None:
        """Return the path of the most recently saved model, if any."""
        return next(iter(self._candidates()), None)


# ---------------------------------------------------------------------------
# Shared (per-process) classifier
# ---------------------------------------------------------------------------

_SHARED: dict[tuple[str, int], AICodeClassifier] = {}
_SHARED_LOCK = threading.Lock()


def load_shared_classifier(model_dir: Path | None = None) -> AICodeClassifier | None:
    """Return a process-wide classifier for ``model_dir`` (loaded once).

    Detectors are built per analysis job and each one used to unpickle the model
    from disk. The cache key includes the file's modification time, so a retrained
    model is picked up without a restart. Returns None when no usable model exists.
    """
    probe = AICodeClassifier(model_dir=model_dir)
    latest = probe.latest_model_path()
    if latest is None:
        return None
    try:
        key = (str(latest.resolve()), latest.stat().st_mtime_ns)
    except OSError:
        return None
    with _SHARED_LOCK:
        cached = _SHARED.get(key)
        if cached is not None:
            return cached
        if probe.load():
            _SHARED.clear()  # keep at most one model resident
            _SHARED[key] = probe
            return probe
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _checksum_path(model_path: Path) -> Path:
    return model_path.with_name(model_path.name + ".sha256")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _training_medians(rows: list[dict[str, float]], names: list[str]) -> dict[str, float]:
    """Median of each feature over the training rows (static default if never seen)."""
    static = _default_feature_values()
    medians: dict[str, float] = {}
    for name in names:
        values = [float(row[name]) for row in rows if _is_number(row.get(name))]
        medians[name] = statistics.median(values) if values else static.get(name, 0.0)
    return medians


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _feature_matrix(
    rows: list[dict[str, float]],
    names: list[str],
    defaults: dict[str, float] | None = None,
) -> list[list[float]]:
    """Convert rows of dicts to a numeric matrix aligned to names."""
    fallback = defaults if defaults is not None else _default_feature_values()
    matrix = []
    for row in rows:
        matrix.append(
            [
                float(row[name]) if _is_number(row.get(name)) else fallback.get(name, 0.0)
                for name in names
            ]
        )
    return matrix


def _default_feature_values() -> dict[str, float]:
    """Static last-resort defaults, used only for models saved without medians.

    Models trained by this code carry the training medians instead; these values
    are on mixed scales and are kept for backward compatibility.
    """
    return {
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


_STYLOMETRY_FEATURES = (
    "descriptive_var_ratio",
    "docstring_ratio",
    "type_hint_ratio",
    "single_char_var_ratio",
    "exception_handling_ratio",
    "list_comprehension_ratio",
    "var_naming_entropy",
    "avg_statements_per_func",
    "max_nesting_depth",
)


def assemble_features(
    ast_vector: Any,
    stylometry: Any | None = None,
    perplexity: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Assemble the classifier feature dict from the three signal sources.

    Accepts an ``ASTFeatureVector``, an optional stylometry result (a dataclass
    or a dict) and an optional perplexity result dict. A source that is missing,
    or whose parse failed, contributes NO keys, so the classifier substitutes the
    training median instead of a misleading zero (an unparseable Java file used
    to feed ``single_char_var_ratio = 0`` and ``max_nesting_depth = 0`` as facts).
    """
    features: dict[str, float] = {}

    if ast_vector is not None:
        for name in ast_vector.feature_names():
            features[name] = float(getattr(ast_vector, name))

    if stylometry is not None and getattr(stylometry, "parse_ok", True) is not False:
        if is_dataclass(stylometry) and not isinstance(stylometry, type):
            stylometry = asdict(stylometry)
        if isinstance(stylometry, dict) and stylometry.get("parse_ok", True) is not False:
            for name in _STYLOMETRY_FEATURES:
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
