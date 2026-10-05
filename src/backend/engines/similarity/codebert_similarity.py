"""CodeBERT/UniXcoder embedding similarity for GPU server deployment.

Replace OpenAI embeddings with local CodeBERT model.
Usage:
    from src.backend.engines.similarity.codebert_similarity import CodeBERTSimilarity
    similarity = CodeBERTSimilarity(device='cuda')
    score = similarity.compare({'raw': code_a}, {'raw': code_b})

NOTE: ``unixcoder_similarity.UniXcoderSimilarity`` is the maintained UniXcoder engine
(CLS pooling, disk/Redis caches, batching). The ``UniXcoderSimilarity`` defined
at the bottom of THIS module is a thin mean-pooling variant kept for compatibility;
it shares a name but not a constructor or pooling with that one.
"""

import logging
import threading
from typing import Any

import numpy as np

from .base_similarity import BaseSimilarityAlgorithm

logger = logging.getLogger(__name__)


class CodeBERTSimilarity(BaseSimilarityAlgorithm):
    """Compute code similarity using a CodeBERT or similar transformer model.

    Embeddings are cached by content hash so the same code snippet is
    only encoded once regardless of how many pairs it participates in.

    It now subclasses :class:`BaseSimilarityAlgorithm`: it had no ``name`` or
    ``get_name()``, so ``SimilarityEngine.add_algorithm`` raised AttributeError.
    ``compare`` still returns a plain float, which the engine accepts.
    """

    def __init__(
        self, model_name: str = "microsoft/codebert-base", device: str = "auto"
    ) -> None:
        super().__init__("codebert")
        self.model_name = model_name
        if device == "auto":
            device = "cuda" if self._has_gpu() else "cpu"
        self.device = device
        self._model: Any = None
        self._tokenizer: Any = None
        self._load_lock = threading.Lock()

        # Per-instance embedding cache
        from src.backend.engines.cache import EmbeddingCache

        self._embedding_cache = EmbeddingCache(maxsize=4096)

    @staticmethod
    def _has_gpu() -> bool:
        """Check whether a CUDA-capable GPU is available."""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError as exc:
            logger.debug("PyTorch not installed; GPU check failed: %s", exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error during GPU check: %s", exc)
            return False

    def _load_model(self) -> None:
        """Lazy-load the transformer model and tokenizer (thread-safe)."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                from transformers import AutoModel, AutoTokenizer

                tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                model = AutoModel.from_pretrained(self.model_name).to(self.device)
                model.eval()
                self._tokenizer, self._model = tokenizer, model
            except ImportError as exc:
                logger.error("transformers library not installed: %s", exc)
                raise
            except Exception as exc:
                logger.error(
                    "Failed to load model %s on %s: %s", self.model_name, self.device, exc
                )
                raise

    def _encode(self, code: str) -> list[float]:
        """Encode a single source snippet to a dense vector (cached)."""
        return self._embedding_cache.get_or_compute(code, self._do_encode)

    def _do_encode(self, code: str) -> list[float]:
        """Actual encoding — called by the cache on misses."""
        self._load_model()
        import torch

        inputs = self._tokenizer(
            code, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)
        with torch.no_grad():
            outputs = self._model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).reshape(-1).tolist()

    def compare(self, a: Any, b: Any) -> float:
        """Return cosine similarity in [0, 1] for two code inputs.

        Args:
            a: First code element (dict with 'raw' key, or raw string).
            b: Second code element (dict with 'raw' key, or raw string).

        Returns:
            A float between 0.0 and 1.0.
        """
        ca: str = a.get("raw", "") if isinstance(a, dict) else str(a)
        cb: str = b.get("raw", "") if isinstance(b, dict) else str(b)

        if not ca or not cb:
            return 0.0

        try:
            ea = np.asarray(self._encode(ca), dtype=np.float64)
            eb = np.asarray(self._encode(cb), dtype=np.float64)
        except Exception as exc:
            logger.error("Embedding encoding failed for code pair: %s", exc)
            return 0.0

        if ea.shape != eb.shape:
            return 0.0
        na, nb = float(np.linalg.norm(ea)), float(np.linalg.norm(eb))
        if na == 0 or nb == 0:
            return 0.0
        # (a pure-Python ``sum(x * y ...)`` over 768 floats per comparison before)
        return max(0.0, min(1.0, float(np.dot(ea, eb) / (na * nb))))


class UniXcoderSimilarity(CodeBERTSimilarity):
    """UniXcoder variant using microsoft/unixcoder-base (mean pooling; see module note)."""

    def __init__(self, device: str = "auto") -> None:
        super().__init__("microsoft/unixcoder-base", device)
        self.name = "unixcoder_meanpool"
