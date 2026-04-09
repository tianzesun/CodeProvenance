"""Feature Extractor - Extracts features from code pairs for similarity engines."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dataclasses import dataclass
from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Similarity scores from each detection engine.

    The extraction layer normalizes missing or failed engines to ``0.0`` so
    the downstream pipeline always receives a stable numeric feature set.
    """

    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0
    ngram: float = 0.0
    winnowing: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        """Convert FeatureVector to a dictionary."""
        return {
            "ast": self.ast,
            "fingerprint": self.fingerprint,
            "embedding": self.embedding,
            "ngram": self.ngram,
            "winnowing": self.winnowing,
        }


class FeatureExtractor:
    """Extracts a FeatureVector from a pair of source code strings.

    The extractor lazily loads each similarity engine so that importing the
    module is cheap and missing optional dependencies (e.g. ML models) only
    affect the engines that need them.
    """

    FEATURE_ORDER: List[str] = ["ast", "fingerprint", "embedding", "ngram", "winnowing"]

    def __init__(self) -> None:
        # Cached engine instances (lazy-loaded on first use)
        self._ast_engine = None
        self._token_engine = None
        self._unixcoder_engine = None
        self._fallback_embedding = None
        self._ngram_engine = None
        self._winnowing_engine = None

    def _resolve_embedding_base_url(self) -> Optional[str]:
        if settings.EMBEDDING_SERVER_URL:
            return settings.EMBEDDING_SERVER_URL

        host = settings.EMBEDDING_SERVER_HOST
        if host:
            return f"http://{host}:{settings.EMBEDDING_SERVER_PORT}/v1"

        return settings.OPENAI_BASE_URL or None

    # ── Public API ──────────────────────────────────────────────

    def extract(self, code_a: str, code_b: str) -> FeatureVector:
        """Run all enabled engines and collect scores.

        Args:
            code_a: Source code of the first file.
            code_b: Source code of the second file.

        Returns:
            A FeatureVector with a score from each engine.
        """
        ast = self._run_ast(code_a, code_b)
        fingerprint = self._run_fingerprint(code_a, code_b)
        embedding = self._run_embedding(code_a, code_b)
        ngram = self._run_ngram(code_a, code_b)
        winnowing = self._run_winnowing(code_a, code_b)

        return FeatureVector(
            ast=ast if ast is not None else 0.0,
            fingerprint=fingerprint if fingerprint is not None else 0.0,
            embedding=embedding if embedding is not None else 0.0,
            ngram=ngram if ngram is not None else 0.0,
            winnowing=winnowing if winnowing is not None else 0.0,
        )

    def to_features(self, fv: FeatureVector) -> List[float]:
        """Flatten a FeatureVector into a list of floats.

        Returns:
            List of floats in FEATURE_ORDER.
        """
        return [fv.ast, fv.fingerprint, fv.embedding, fv.ngram, fv.winnowing]

    def _coerce_score(self, result: Any, engine_name: str) -> Optional[float]:
        """Normalize engine outputs to a plain numeric score.

        Similarity engines are not perfectly consistent today:
        some return a raw float while others return a Finding-like object
        with a ``score`` attribute. The downstream fusion layer expects
        floats only, so we normalize here at the integration boundary.
        """
        if result is None:
            return None

        if isinstance(result, (int, float)):
            return float(result)

        score = getattr(result, "score", None)
        if isinstance(score, (int, float)):
            return float(score)

        logger.debug("Engine %s returned non-numeric result of type %s", engine_name, type(result).__name__)
        return None

    # ── Private engine helpers ──────────────────────────────────

    def _run_ast(self, a: str, b: str) -> Optional[float]:
        try:
            if self._ast_engine is None:
                from src.engines.similarity.ast_similarity import ASTSimilarity
                self._ast_engine = ASTSimilarity()
            result = self._ast_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
            return self._coerce_score(result, "ast")
        except Exception as exc:
            logger.debug("AST engine unavailable: %s", exc)
            return None

    def _run_fingerprint(self, a: str, b: str) -> Optional[float]:
        try:
            if self._token_engine is None:
                from src.engines.similarity.token_similarity import TokenSimilarity
                self._token_engine = TokenSimilarity()
            result = self._token_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
            return self._coerce_score(result, "fingerprint")
        except Exception as exc:
            logger.debug("Token/Fingerprint engine unavailable: %s", exc)
            return None

    def _run_embedding(self, a: str, b: str) -> Optional[float]:
        runtime = (settings.EMBEDDING_RUNTIME or "local_unixcoder").lower()

        if runtime in {"local", "local_unixcoder", "unixcoder"}:
            try:
                if self._unixcoder_engine is None:
                    from src.engines.similarity.unixcoder_similarity import UniXcoderSimilarity
                    self._unixcoder_engine = UniXcoderSimilarity(
                        model_name=settings.EMBEDDING_MODEL,
                        device=settings.EMBEDDING_DEVICE,
                        batch_size=settings.EMBEDDING_BATCH_SIZE,
                    )
                result = self._unixcoder_engine.compare({"raw": a}, {"raw": b})
                coerced = self._coerce_score(result, "embedding")
                if coerced is not None:
                    return coerced
            except Exception as exc:
                logger.debug("UniXcoder engine unavailable, falling back to API embeddings: %s", exc)

        try:
            if self._fallback_embedding is None:
                from src.engines.similarity.embedding_similarity import EmbeddingSimilarity
                self._fallback_embedding = EmbeddingSimilarity(
                    model_name=settings.EMBEDDING_MODEL,
                    base_url=self._resolve_embedding_base_url(),
                    api_key=settings.OPENAI_API_KEY,
                )
            result = self._fallback_embedding.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "embedding")
        except Exception as exc:
            logger.debug("Embedding API fallback also failed: %s", exc)
            return None

    def _run_ngram(self, a: str, b: str) -> Optional[float]:
        try:
            if self._ngram_engine is None:
                from src.engines.similarity.ngram_similarity import NgramSimilarity
                self._ngram_engine = NgramSimilarity()
            result = self._ngram_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
            return self._coerce_score(result, "ngram")
        except Exception as exc:
            logger.debug("N-gram engine unavailable: %s", exc)
            return None

    def _run_winnowing(self, a: str, b: str) -> Optional[float]:
        try:
            if self._winnowing_engine is None:
                from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
                self._winnowing_engine = EnhancedWinnowingSimilarity()
            result = self._winnowing_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
            return self._coerce_score(result, "winnowing")
        except Exception as exc:
            logger.debug("Winnowing engine unavailable: %s", exc)
            return None
