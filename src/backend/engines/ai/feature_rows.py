"""Shared feature-row construction for training and benchmarking.

``train_classifier`` and ``benchmark_classifier`` each had their own copy that
built a ``PerplexityScorer()`` with DEFAULT settings. Production scoring builds
its scorer from ``ai_ensemble_config.yaml`` (a code LM by default), so the
classifier was trained on statistical-model perplexity (values of a few units)
but fed code-LM perplexity (hundreds or thousands) at inference. Both scripts now
use the same configuration as production, and the model records which
perplexity model produced its training features so the ensemble can refuse a
mismatch.

Features are cached on disk (``cache_path``), keyed by the code and language and
invalidated automatically when any extractor's source changes: a 7,000-sample
run with a code LM takes hours, and a stale cache would silently reuse features
computed by older extractor code.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FeatureBuild:
    """Result of :func:`build_feature_rows`."""

    rows: list[dict[str, float]]
    #: how many samples were scored by each perplexity model ("statistical", "huggingface")
    perplexity_models: Counter = field(default_factory=Counter)
    cache_hits: int = 0

    @property
    def perplexity_model(self) -> str | None:
        """The perplexity model used for the training features (None if mixed)."""
        if len(self.perplexity_models) == 1:
            return next(iter(self.perplexity_models))
        return None


def _module_bytes(module_name: str) -> bytes:
    try:
        import importlib

        module = importlib.import_module(module_name)
        return Path(module.__file__).read_bytes()
    except Exception:  # pragma: no cover - a module that cannot be located
        return module_name.encode()


def pipeline_fingerprint(perplexity_config: dict[str, Any] | None = None) -> str:
    """Hash of everything that determines the computed features.

    Covers the source of the extractors and ``assemble_features``, the feature
    schema version, and the perplexity configuration.
    """
    from src.backend.engines.ai.classifier import FEATURE_SCHEMA_VERSION

    digest = hashlib.sha256()
    for name in (
        "src.backend.engines.ai.ast_features",
        "src.backend.engines.ai.perplexity",
        "src.backend.engines.ai.classifier",
        "src.backend.engines.features.code_stylometry",
    ):
        digest.update(_module_bytes(name))
    digest.update(f"schema={FEATURE_SCHEMA_VERSION}".encode())
    digest.update(json.dumps(perplexity_config or {}, sort_keys=True, default=str).encode())
    digest.update(os.environ.get("AICODE_TRANSFORMER_MODEL", "").encode())
    return digest.hexdigest()[:16]


def _sample_key(code: str, language: str) -> str:
    return hashlib.sha256(f"{language}\0{code}".encode("utf-8", "surrogatepass")).hexdigest()


def _load_cache(path: Path | None, fingerprint: str) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable feature cache %s: %s", path, exc)
        return {}
    if payload.get("fingerprint") != fingerprint:
        logger.info("Feature cache %s was built by different extractor code; rebuilding", path)
        return {}
    return payload.get("rows", {})


def _save_cache(path: Path | None, fingerprint: str, rows: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": fingerprint, "rows": rows}, fh)
        Path(tmp).replace(path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def build_feature_rows(
    codes: list[str],
    languages: list[str] | None = None,
    *,
    cache_path: Path | None = None,
    progress_every: int = 100,
) -> FeatureBuild:
    """Compute the classifier feature dict for every sample.

    Args:
        codes: Source text of each sample.
        languages: Language of each sample (default: Python for all).
        cache_path: Optional JSON file caching computed features.
        progress_every: Log progress every N newly computed samples.
    """
    from src.backend.engines.ai.ast_features import TreeSitterASTExtractor
    from src.backend.engines.ai.classifier import assemble_features
    from src.backend.engines.ai.ensemble import AIEnsembleConfig
    from src.backend.engines.ai.perplexity import PerplexityScorer
    from src.backend.engines.features.code_stylometry import StylometryExtractor

    languages = languages or ["python"] * len(codes)
    if len(languages) != len(codes):
        raise ValueError("languages must have one entry per sample")

    perplexity_config = AIEnsembleConfig.get_instance().perplexity_config()
    fingerprint = pipeline_fingerprint(perplexity_config)
    cache = _load_cache(cache_path, fingerprint)

    ast_extractor = TreeSitterASTExtractor()
    stylometry_extractor = StylometryExtractor()
    # Same construction as AIEnsembleScorer, so training sees what production sees.
    scorer = PerplexityScorer(
        model_path=perplexity_config.get("huggingface_model") or None,
        window=int(perplexity_config.get("window_lines", 25)),
        overlap=int(perplexity_config.get("overlap_lines", 5)),
    )

    build = FeatureBuild(rows=[])
    computed = 0
    for index, (code, language) in enumerate(zip(codes, languages)):
        key = _sample_key(code, language)
        entry = cache.get(key)
        if entry is None:
            perp = scorer.score(code)
            entry = {
                "features": assemble_features(
                    ast_extractor.extract(code, language),
                    stylometry_extractor.extract(code, doc_id=""),
                    perp,
                ),
                "perplexity_model": perp.get("model", "statistical"),
            }
            cache[key] = entry
            computed += 1
            if computed % progress_every == 0:
                logger.info("Computed features for %d new samples (%d/%d)", computed, index + 1, len(codes))
                _save_cache(cache_path, fingerprint, cache)
        else:
            build.cache_hits += 1
        build.rows.append(entry["features"])
        build.perplexity_models[entry["perplexity_model"]] += 1

    if computed:
        _save_cache(cache_path, fingerprint, cache)
    if len(build.perplexity_models) > 1:
        logger.warning(
            "Perplexity came from more than one model (%s): the code LM was unavailable for "
            "some samples. Training on this mix gives features on two scales; make the model "
            "available (or disable it in the config) and rebuild.",
            dict(build.perplexity_models),
        )
    return build
