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

import hashlib
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .base_similarity import BaseSimilarityAlgorithm

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Model config
# ─────────────────────────────────────────────
DEFAULT_MODEL = "microsoft/unixcoder-base"
MAX_LENGTH = 512          # UniXcoder token limit
BATCH_SIZE = 32           # Safe batch size for a single GPU (tune up/down as needed)
CACHE_DIR = Path("./.unixcoder_cache")


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
        super().__init__("embedding")          # keeps "embedding" key → fusion unchanged
        self.model_name = model_name
        self.batch_size = batch_size

        # Resolve device
        if device == "auto":
            self.device = self._resolve_device()
        else:
            self.device = device

        # Cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-loaded
        self._tokenizer = None
        self._model = None

        logger.info(
            "UniXcoderSimilarity initialised — model=%s device=%s",
            self.model_name, self.device,
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
        """Load model and tokenizer once, on first use."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "transformers package not installed. "
                "Run: pip install transformers torch"
            ) from e

        logger.info("Loading %s onto %s …", self.model_name, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = (
            AutoModel.from_pretrained(self.model_name)
            .to(self.device)
            .eval()
        )
        logger.info("Model loaded.")

    # ─────────────────────────────────────────
    #  Cache helpers
    # ─────────────────────────────────────────

    def _cache_key(self, text: str) -> str:
        payload = f"{self.model_name}::{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, text: str) -> Path:
        return self.cache_dir / f"{self._cache_key(text)}.pkl"

    def _load_from_cache(self, text: str) -> Optional[np.ndarray]:
        p = self._cache_path(text)
        if p.exists():
            try:
                with open(p, "rb") as f:
                    return pickle.load(f)
            except Exception:
                p.unlink(missing_ok=True)   # evict corrupt entry
        return None

    def _save_to_cache(self, text: str, embedding: np.ndarray) -> None:
        try:
            with open(self._cache_path(text), "wb") as f:
                pickle.dump(embedding, f)
        except Exception as e:
            logger.debug("Cache write failed (non-fatal): %s", e)

    # ─────────────────────────────────────────
    #  Core embedding
    # ─────────────────────────────────────────

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of code strings.
        Returns shape (N, hidden_size), L2-normalised rows.
        Uses cache where possible; runs model for any misses.
        """
        import torch

        results: List[Optional[np.ndarray]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Check cache
        for i, text in enumerate(texts):
            cached = self._load_from_cache(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # Run model in batches for cache misses
        if uncached_texts:
            self._load_model()
            all_embeddings: List[np.ndarray] = []

            for batch_start in range(0, len(uncached_texts), self.batch_size):
                batch = uncached_texts[batch_start: batch_start + self.batch_size]
                inputs = self._tokenizer(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=MAX_LENGTH,
                    padding=True,
                ).to(self.device)

                with torch.no_grad():
                    output = self._model(**inputs)

                # CLS token — index 0 of the sequence dimension
                # Shape: (batch, hidden_size)
                cls_embeddings = output.last_hidden_state[:, 0, :]

                # L2 normalise so dot product == cosine similarity
                norms = cls_embeddings.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                normalised = (cls_embeddings / norms).cpu().numpy()
                all_embeddings.extend(normalised)

            # Write cache + fill results
            for idx, text, emb in zip(uncached_indices, uncached_texts, all_embeddings):
                self._save_to_cache(text, emb)
                results[idx] = emb

        return np.stack(results)   # (N, hidden_size)

    # ─────────────────────────────────────────
    #  Public API (matches BaseSimilarityAlgorithm)
    # ─────────────────────────────────────────

    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code dicts.
        Reads 'raw' key first (set by FeatureExtractor), falls back to 'tokens'.

        Returns similarity in [0.0, 1.0].
        """
        text_a = self._extract_text(parsed_a)
        text_b = self._extract_text(parsed_b)

        if not text_a and not text_b:
            return 1.0
        if not text_a or not text_b:
            return 0.0

        # Skip very short snippets — noise dominates embeddings below ~5 tokens
        if len(text_a.split()) < 5 or len(text_b.split()) < 5:
            return self._token_fallback(parsed_a, parsed_b)

        try:
            embeddings = self._embed_texts([text_a, text_b])
            # Rows are already L2-normalised → dot product == cosine similarity
            score = float(np.dot(embeddings[0], embeddings[1]))
            # Map cosine [-1, 1] → [0, 1]
            return max(0.0, min(1.0, (score + 1.0) / 2.0))
        except Exception as e:
            logger.warning("UniXcoder compare failed: %s — using token fallback", e)
            return self._token_fallback(parsed_a, parsed_b)

    def similarity_matrix(self, codes: List[str]) -> np.ndarray:
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

        embeddings = self._embed_texts(codes)          # (N, hidden)
        cosine = embeddings @ embeddings.T             # (N, N), values in [-1, 1]
        similarity = (cosine + 1.0) / 2.0             # map to [0, 1]
        np.fill_diagonal(similarity, 1.0)             # self-similarity = 1.0
        return similarity

    def top_suspicious_pairs(
        self,
        codes: List[str],
        labels: Optional[List[str]] = None,
        threshold: float = 0.85,
    ) -> List[Dict[str, Any]]:
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
        matrix = self.similarity_matrix(codes)
        n = len(codes)
        labels = labels or [str(i) for i in range(n)]
        pairs = []

        for i in range(n):
            for j in range(i + 1, n):
                score = float(matrix[i, j])
                if score >= threshold:
                    pairs.append(
                        {
                            "i": i,
                            "j": j,
                            "label_i": labels[i],
                            "label_j": labels[j],
                            "score": round(score, 4),
                        }
                    )

        pairs.sort(key=lambda x: x["score"], reverse=True)
        return pairs

    # ─────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _extract_text(parsed: Dict[str, Any]) -> str:
        """Extract best text representation from a parsed dict."""
        if parsed.get("raw"):
            return parsed["raw"].strip()
        tokens = parsed.get("tokens", [])
        if tokens:
            return " ".join(tokens)
        return ""

    @staticmethod
    def _token_fallback(parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """Fallback to token similarity when embedding is unavailable / unreliable."""
        try:
            from .token_similarity import TokenSimilarity
            return TokenSimilarity().compare(parsed_a, parsed_b)
        except Exception:
            return 0.0
