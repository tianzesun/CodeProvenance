"""
UniXcoder-based embedding similarity for local GPU deployment.

Drop-in replacement for EmbeddingSimilarity (OpenAI).
Uses microsoft/unixcoder-base — purpose-built for code similarity tasks.

Usage:
    # Automatic — via feature_extractor.py (recommended)
    # Manual:
    from src.backend.engines.similarity.unixcoder_similarity import UniXcoderSimilarity
    engine = UniXcoderSimilarity()
    score = engine.compare({'raw': code_a}, {'raw': code_b})
"""

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from src.backend.domain.models import Finding

from .base_similarity import BaseSimilarityAlgorithm
from .embedding_store import DiskEmbeddingStore

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Model config
# ─────────────────────────────────────────────
DEFAULT_MODEL = "microsoft/unixcoder-base"
MAX_LENGTH = 512  # UniXcoder token limit
BATCH_SIZE = 32  # Safe batch size for a single GPU (tune up/down as needed)
CACHE_DIR = Path("./.unixcoder_cache")

_TOKEN_FALLBACK: Any = None
_TOKEN_FALLBACK_LOCK = threading.Lock()


def _token_fallback_engine():
    """One shared TokenSimilarity for the fallback path (a new one, with its own
    8k-entry cache, was built for every short snippet)."""
    global _TOKEN_FALLBACK
    with _TOKEN_FALLBACK_LOCK:
        if _TOKEN_FALLBACK is None:
            from .token_similarity import TokenSimilarity

            _TOKEN_FALLBACK = TokenSimilarity()
        return _TOKEN_FALLBACK


class UniXcoderSimilarity(BaseSimilarityAlgorithm):
    """
    Semantic code similarity using UniXcoder (local GPU).

    Replaces EmbeddingSimilarity (OpenAI API) with a fully local model.
    Preserves the same interface: compare(parsed_a, parsed_b) → float.

    Key improvements over the old CodeBERT stub:
    • CLS token pooling  (better than mean pooling for similarity tasks)
    • Pre-normalised embeddings  (dot product == cosine similarity, no division needed)
    • Batch inference for all-pairs matrix computation
    • Pickle cache keyed by (model_name + code_hash)
    • Graceful CPU fallback when no GPU is available
    • Thread-safe lazy model loading
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "auto",
        cache_dir: Path = CACHE_DIR,
        batch_size: int = BATCH_SIZE,
    ):
        super().__init__("embedding")  # keeps "embedding" key → fusion unchanged
        self.model_name = model_name
        self.batch_size = batch_size

        # Resolve device
        if device == "auto":
            self.device = self._resolve_device()
        else:
            self.device = device

        # Cache: ``.npy`` files (never pickles), created on first write
        self.cache_dir = Path(cache_dir)
        self._store = DiskEmbeddingStore(self.model_name, directory=self.cache_dir)

        # Lazy-loaded
        self._tokenizer = None
        self._model = None
        self._load_lock = threading.Lock()

        logger.info(
            "UniXcoderSimilarity initialised — model=%s device=%s",
            self.model_name,
            self.device,
        )

    # ─────────────────────────────────────────
    #  Device helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _resolve_device() -> str:
        try:
            import torch

            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                logger.info("GPU detected: %s", name)
                return "cuda"
        except ImportError:
            pass
        logger.warning("No GPU detected — UniXcoder will run on CPU (slower)")
        return "cpu"

    # ─────────────────────────────────────────
    #  Lazy model loading
    # ─────────────────────────────────────────

    def _load_model(self) -> None:
        """Load model and tokenizer once, on first use (thread-safe)."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is None:
                self._load_model_locked()

    def _load_model_locked(self) -> None:
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "transformers package not installed. "
                "Run: pip install transformers torch"
            ) from e

        logger.info("Loading %s onto %s …", self.model_name, self.device)

        # Suppress warnings during model loading (known issue with unixcoder-base)
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*embeddings\\.position_ids.*")
            warnings.filterwarnings(
                "ignore", category=UserWarning, module="transformers"
            )

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            # ``trust_remote_code=True`` was removed: it executes Python from the model
            # repository. UniXcoder is a standard RoBERTa-style checkpoint and does not
            # need it.
            self._model = (
                AutoModel.from_pretrained(self.model_name, ignore_mismatched_sizes=True)
                .to(self.device)
                .eval()
            )
        logger.info("Model loaded.")

    # ─────────────────────────────────────────
    #  Cache helpers
    # ─────────────────────────────────────────

    def _cache_key(self, text: str) -> str:
        return self._store.key(text)

    def _cache_path(self, text: str) -> Path:
        return self._store.path(text)

    def _load_from_cache(self, text: str) -> np.ndarray | None:
        return self._store.get(text)

    def _save_to_cache(self, text: str, embedding: np.ndarray) -> None:
        self._store.put(text, embedding)

    # ─────────────────────────────────────────
    #  Core embedding
    # ─────────────────────────────────────────

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of code strings.
        Returns shape (N, hidden_size), L2-normalised rows.
        Uses Redis cache (fast) → disk cache (slower) → model (slowest).

        ``torch`` is imported only when the model actually has to run: it used to be
        imported first thing, so a machine without torch could not even serve vectors
        that were already cached, and every such comparison fell back to tokens.
        Identical texts in one call are embedded once.
        """
        if not texts:
            return np.zeros((0, 0))

        unique: dict[str, int] = {}
        for text in texts:
            unique.setdefault(text, len(unique))
        unique_texts = list(unique)
        vectors: list[np.ndarray | None] = [None] * len(unique_texts)
        missing: list[int] = []

        from src.backend.infrastructure.cache import get_cache

        redis_cache = get_cache()

        for i, text in enumerate(unique_texts):
            cache_key = f"unixcoder:{self._cache_key(text)}"
            if redis_cache.available:
                cached_redis = redis_cache.get(cache_key)
                if cached_redis is not None:
                    try:
                        vectors[i] = np.asarray(cached_redis, dtype=np.float64)
                        continue
                    except Exception:  # noqa: S110
                        pass  # fall through to the disk cache
            cached_disk = self._load_from_cache(text)
            if cached_disk is not None:
                vectors[i] = cached_disk
                if redis_cache.available:  # backfill Redis for future lookups
                    try:
                        redis_cache.set(cache_key, cached_disk.tolist(), ttl=86400)
                    except Exception:  # noqa: S110
                        pass
            else:
                missing.append(i)

        if missing:
            import torch

            self._load_model()
            for batch_start in range(0, len(missing), self.batch_size):
                batch_idx = missing[batch_start : batch_start + self.batch_size]
                batch = [unique_texts[i] for i in batch_idx]
                inputs = self._tokenizer(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=MAX_LENGTH,
                    padding=True,
                ).to(self.device)

                with torch.no_grad():
                    output = self._model(**inputs)

                # CLS token, L2-normalised so dot product == cosine similarity
                cls_embeddings = output.last_hidden_state[:, 0, :]
                norms = cls_embeddings.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                normalised = (cls_embeddings / norms).cpu().numpy()

                for idx, emb in zip(batch_idx, normalised):
                    text = unique_texts[idx]
                    vectors[idx] = emb
                    self._save_to_cache(text, emb)
                    if redis_cache.available:
                        try:
                            redis_cache.set(f"unixcoder:{self._cache_key(text)}", emb.tolist(), ttl=86400)
                        except Exception:  # noqa: S110
                            pass

        return np.stack([vectors[unique[text]] for text in texts])  # (N, hidden_size)

    # ─────────────────────────────────────────
    #  Public API (matches BaseSimilarityAlgorithm)
    # ─────────────────────────────────────────

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """
        Compare two parsed code dicts.
        Reads 'raw' key first (set by FeatureExtractor), falls back to 'tokens'.

        Returns a Finding with similarity score in [0.0, 1.0].
        """
        text_a = self._extract_text(parsed_a)
        text_b = self._extract_text(parsed_b)

        if not text_a and not text_b:
            return Finding(
                engine=self.name,
                score=1.0,
                confidence=1.0,
                methodology="UniXcoder semantic similarity",
            )
        if not text_a or not text_b:
            return Finding(
                engine=self.name,
                score=0.0,
                confidence=1.0,
                methodology="UniXcoder semantic similarity",
            )

        # Skip very short snippets — noise dominates embeddings below ~5 tokens
        if len(text_a.split()) < 5 or len(text_b.split()) < 5:
            fallback_result = self._token_fallback(parsed_a, parsed_b)
            return Finding(
                engine=self.name,
                score=fallback_result.score,
                confidence=fallback_result.confidence,
                methodology="UniXcoder semantic similarity (token fallback)",
            )

        try:
            embeddings = self._embed_texts([text_a, text_b])
            # Rows are already L2-normalised → dot product == cosine similarity
            score = float(np.dot(embeddings[0], embeddings[1]))
            # Map cosine [-1, 1] → [0, 1]
            normalized_score = max(0.0, min(1.0, (score + 1.0) / 2.0))
            return Finding(
                engine=self.name,
                score=normalized_score,
                confidence=0.9,
                methodology="UniXcoder semantic similarity using CLS token embeddings",
            )
        except Exception as e:
            logger.warning("UniXcoder compare failed: %s — using token fallback", e)
            fallback_result = self._token_fallback(parsed_a, parsed_b)
            return Finding(
                engine=self.name,
                score=fallback_result.score,
                confidence=fallback_result.confidence,
                methodology="UniXcoder semantic similarity (fallback due to error)",
            )

    def similarity_matrix(self, codes: list[str]) -> np.ndarray:
        """
        Compute full pairwise similarity matrix for a list of code strings.
        Single GPU pass — use this for all-pairs batch comparison.

        Returns: np.ndarray shape (N, N), values in [0, 1].

        Example:
            engine = UniXcoderSimilarity()
            matrix = engine.similarity_matrix(all_student_codes)
            # matrix[i][j] == similarity between student i and student j
        """
        if not codes:
            return np.zeros((0, 0))

        embeddings = self._embed_texts(codes)  # (N, hidden)
        cosine = embeddings @ embeddings.T  # (N, N), values in [-1, 1]
        similarity = (cosine + 1.0) / 2.0  # map to [0, 1]
        np.fill_diagonal(similarity, 1.0)  # self-similarity = 1.0
        return similarity

    def top_suspicious_pairs(
        self,
        codes: list[str],
        labels: list[str] | None = None,
        threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        """
        Return all pairs above a similarity threshold, sorted descending.

        Args:
            codes:     List of code strings (one per student).
            labels:    Optional list of student names / file names (same length).
            threshold: Minimum similarity score to include in results.

        Returns:
            List of dicts: {i, j, label_i, label_j, score}

        Example:
            results = engine.top_suspicious_pairs(
                codes=student_codes,
                labels=student_names,
                threshold=0.85,
            )
            for r in results:
                print(f"{r['label_i']} ↔ {r['label_j']}: {r['score']:.3f}")
        """
        n = len(codes)
        labels = labels or [str(i) for i in range(n)]
        if len(labels) != n:  # validate before paying for any embedding
            raise ValueError("labels must have one entry per code string")
        matrix = self.similarity_matrix(codes)

        # vectorised: the O(N^2) double Python loop is one numpy selection
        rows, cols = np.triu_indices(n, k=1)
        scores = matrix[rows, cols]
        keep = scores >= threshold
        pairs = [
            {
                "i": int(i),
                "j": int(j),
                "label_i": labels[i],
                "label_j": labels[j],
                "score": round(float(score), 4),
            }
            for i, j, score in zip(rows[keep], cols[keep], scores[keep])
        ]
        pairs.sort(key=lambda x: x["score"], reverse=True)
        return pairs

    # ─────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _extract_text(parsed: dict[str, Any]) -> str:
        """Extract best text representation from a parsed dict."""
        if parsed.get("raw"):
            return parsed["raw"].strip()
        tokens = parsed.get("tokens", [])
        if tokens:
            return " ".join(tokens)
        return ""

    @staticmethod
    def _token_fallback(parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """Fallback to token similarity when embedding is unavailable / unreliable."""
        try:
            return _token_fallback_engine().compare(parsed_a, parsed_b)
        except Exception:
            return Finding(
                engine="token",
                score=0.0,
                confidence=0.1,
                methodology="Token similarity fallback",
            )
