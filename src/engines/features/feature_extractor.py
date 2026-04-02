"""Feature Extractor - Extracts features from code pairs for similarity engines."""
from __future__ import annotations

import logging
from typing import Dict, List

from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Similarity scores from each detection engine."""

    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0
    ngram: float = 0.0
    winnowing: float = 0.0


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

    # ── Public API ──────────────────────────────────────────────

    def extract(self, code_a: str, code_b: str) -> FeatureVector:
        """Run all enabled engines and collect scores.

        Args:
            code_a: Source code of the first file.
            code_b: Source code of the second file.

        Returns:
            A FeatureVector with a score from each engine.
        """
        return FeatureVector(
            ast=self._run_ast(code_a, code_b),
            fingerprint=self._run_fingerprint(code_a, code_b),
            embedding=self._run_embedding(code_a, code_b),
            ngram=self._run_ngram(code_a, code_b),
            winnowing=self._run_winnowing(code_a, code_b),
        )

    def to_features(self, fv: FeatureVector) -> List[float]:
        """Flatten a FeatureVector into a list of floats.

        Returns:
            List of floats in FEATURE_ORDER.
        """
        return [fv.ast, fv.fingerprint, fv.embedding, fv.ngram, fv.winnowing]

    # ── Private engine helpers ──────────────────────────────────

    def _run_ast(self, a: str, b: str) -> float:
        try:
            if self._ast_engine is None:
                from src.engines.similarity.ast_similarity import ASTSimilarity
                self._ast_engine = ASTSimilarity()
            return self._ast_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
        except Exception as exc:
            logger.debug("AST engine unavailable: %s", exc)
            return 0.0

    def _run_fingerprint(self, a: str, b: str) -> float:
        try:
            if self._token_engine is None:
                from src.engines.similarity.token_similarity import TokenSimilarity
                self._token_engine = TokenSimilarity()
            return self._token_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
        except Exception as exc:
            logger.debug("Token/Fingerprint engine unavailable: %s", exc)
            return 0.0

    def _run_embedding(self, a: str, b: str) -> float:
        # Primary: UniXcoder (local, GPU-friendly)
        try:
            if self._unixcoder_engine is None:
                from src.engines.similarity.unixcoder_similarity import UniXcoderSimilarity
                self._unixcoder_engine = UniXcoderSimilarity()
            return self._unixcoder_engine.compare({"raw": a}, {"raw": b})
        except Exception as exc:
            logger.debug("UniXcoder engine unavailable, falling back to OpenAI: %s", exc)

        # Fallback: OpenAI embeddings
        try:
            if self._fallback_embedding is None:
                from src.engines.similarity.embedding_similarity import EmbeddingSimilarity
                self._fallback_embedding = EmbeddingSimilarity()
            return self._fallback_embedding.compare({"raw": a}, {"raw": b})
        except Exception as exc:
            logger.debug("OpenAI embedding fallback also failed: %s", exc)
            return 0.0

    def _run_ngram(self, a: str, b: str) -> float:
        try:
            if self._ngram_engine is None:
                from src.engines.similarity.ngram_similarity import NgramSimilarity
                self._ngram_engine = NgramSimilarity()
            return self._ngram_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
        except Exception as exc:
            logger.debug("N-gram engine unavailable: %s", exc)
            return 0.0

    def _run_winnowing(self, a: str, b: str) -> float:
        try:
            if self._winnowing_engine is None:
                from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
                self._winnowing_engine = EnhancedWinnowingSimilarity()
            return self._winnowing_engine.compare(
                {"raw": a, "tokens": []},
                {"raw": b, "tokens": []},
            )
        except Exception as exc:
            logger.debug("Winnowing engine unavailable: %s", exc)
            return 0.0