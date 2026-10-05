"""
Embedding-based similarity algorithm using LLM embeddings.

Compares code based on semantic similarity using vector embeddings.

PRIVACY: this engine sends submission source code to an OpenAI-compatible embedding
endpoint. Use it only with a server you are permitted to send student work to.
"""

import logging
import os
import threading
from typing import Any

import numpy as np

from src.backend.domain.models import EvidenceBlock, Finding

from .base_similarity import BaseSimilarityAlgorithm
from .embedding_store import DiskEmbeddingStore

logger = logging.getLogger(__name__)

#: Longest text sent for embedding (characters); longer files are truncated.
MAX_EMBED_CHARS = 24_000


class EmbeddingSimilarity(BaseSimilarityAlgorithm):
    """
    Embedding similarity algorithm that uses LLM embeddings for semantic comparison.

    Effective for detecting semantically similar code despite syntactic differences,
    including LLM-obfuscated code.
    """

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize the embedding similarity algorithm.

        Args:
            model_name: Name of the embedding model to use
            base_url: OpenAI-compatible endpoint (default: ``OPENAI_BASE_URL``)
            api_key: API key (default: ``OPENAI_API_KEY``)
        """
        super().__init__("embedding")
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        # The cache key now includes the model name (it was the text hash alone, so
        # switching models served vectors from the previous one), and the store is
        # created lazily and never unpickles.
        self._store = DiskEmbeddingStore(f"openai::{model_name}", default_dir=".embedding_cache")
        self._client = None
        self._client_lock = threading.Lock()
        self._warned = False

    @property
    def cache_dir(self):
        return self._store.directory

    def _get_openai_client(self):
        """
        Get or create OpenAI client.

        Returns:
            OpenAI client instance
        """
        with self._client_lock:
            if self._client is None:
                try:
                    from openai import OpenAI
                except ImportError as exc:
                    raise ImportError(
                        "OpenAI package not installed. Install with: pip install openai"
                    ) from exc

                api_key = self.api_key or os.getenv("OPENAI_API_KEY")
                base_url = self.base_url or os.getenv("OPENAI_BASE_URL")

                if not api_key and not base_url:
                    raise ValueError(
                        "OPENAI_API_KEY or an embedding server URL must be configured"
                    )

                # OpenAI-compatible local servers often accept a dummy token.
                resolved_api_key = api_key or "EMPTY"
                if base_url:
                    self._client = OpenAI(api_key=resolved_api_key, base_url=base_url)
                else:
                    self._client = OpenAI(api_key=resolved_api_key)
        return self._client

    def _get_cache_path(self, text: str):
        """Path of the cache file for ``text``."""
        return self._store.path(text)

    def _get_embedding(self, text: str) -> np.ndarray | None:
        """
        Get embedding for text, using cache if available.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        if not text.strip():
            return None

        text = text[:MAX_EMBED_CHARS]
        cached = self._store.get(text)
        if cached is not None:
            return cached

        try:
            client = self._get_openai_client()
            response = client.embeddings.create(input=text, model=self.model_name)
            embedding = np.asarray(response.data[0].embedding, dtype=np.float64)
            if embedding.ndim != 1 or embedding.size == 0 or not np.all(np.isfinite(embedding)):
                raise ValueError("embedding service returned an invalid vector")
        except Exception as exc:
            # Failures used to vanish silently (``return None``).
            log = logger.debug if self._warned else logger.warning
            self._warned = True
            log("Embedding request failed: %s", exc)
            return None

        self._store.put(text, embedding)
        return embedding

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations based on embedding similarity.

        Returns:
            A Finding object containing scores and evidence.
        """
        raw_a = parsed_a.get("raw", "")
        raw_b = parsed_b.get("raw", "")

        if not raw_a and not raw_b:
            return Finding(engine=self.name, score=1.0, confidence=1.0)
        if not raw_a or not raw_b:
            return Finding(engine=self.name, score=0.0, confidence=1.0)

        embedding_a = self._get_embedding(raw_a)
        embedding_b = self._get_embedding(raw_b)

        if embedding_a is None or embedding_b is None or embedding_a.shape != embedding_b.shape:
            # "No result" is reported as such: score 0.0 with confidence 0.0. It used
            # to be a fabricated MIDDLE score (0.5), which downstream fusion treated
            # as 50% similarity whenever the embedding service was down.
            return Finding(
                engine=self.name,
                score=0.0,
                confidence=0.0,
                methodology=f"Embedding unavailable ({self.model_name}); no similarity computed.",
            )

        norm_a = np.linalg.norm(embedding_a)
        norm_b = np.linalg.norm(embedding_b)

        if norm_a == 0 or norm_b == 0:
            score = 0.0
        else:
            cosine = float(np.dot(embedding_a, embedding_b) / (norm_a * norm_b))
            # Map [-1, 1] to [0, 1]. NOTE: real code embeddings rarely go below ~0.3
            # cosine, so unrelated files land around 0.65-0.75 here; thresholds on
            # this score must be calibrated accordingly.
            score = (cosine + 1) / 2

        score = max(0.0, min(1.0, float(score)))

        evidence = []
        if score > 0.85:
            evidence.append(
                EvidenceBlock(
                    engine=self.name,
                    score=score,
                    confidence=0.8,
                    a_snippet="Semantic vector similarity detected",
                    b_snippet="Semantic vector similarity detected",
                    transformation_notes=["LLM-based semantic embedding match"],
                )
            )

        return Finding(
            engine=self.name,
            score=score,
            confidence=0.85,
            evidence_blocks=evidence,
            methodology=f"Semantic comparison using {self.model_name} embeddings.",
        )
