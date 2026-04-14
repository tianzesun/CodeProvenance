"""CodeBERT/UniXcoder embedding similarity for GPU server deployment.

Replace OpenAI embeddings with local CodeBERT model.
Usage:
    from src.backend.engines.similarity.codebert_similarity import CodeBERTSimilarity
    similarity = CodeBERTSimilarity(device='cuda')
    score = similarity.compare({'raw': code_a}, {'raw': code_b})
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CodeBERTSimilarity:
    """Compute code similarity using a CodeBERT or similar transformer model.

    Embeddings are cached by content hash so the same code snippet is
    only encoded once regardless of how many pairs it participates in.
    """

    def __init__(self, model_name: str = "microsoft/codebert-base", device: str = "auto") -> None:
        self.model_name = model_name
        if device == "auto":
            device = "cuda" if self._has_gpu() else "cpu"
        self.device = device
        self._model: Any = None
        self._tokenizer: Any = None

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
        """Lazy-load the transformer model and tokenizer."""
        if self._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModel
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self._model.eval()
        except ImportError as exc:
            logger.error("transformers library not installed: %s", exc)
            raise
        except Exception as exc:
            logger.error("Failed to load model %s on %s: %s", self.model_name, self.device, exc)
            raise

    def _encode(self, code: str) -> list[float]:
        """Encode a single source snippet to a dense vector (cached)."""
        return self._embedding_cache.get_or_compute(code, self._do_encode)

    def _do_encode(self, code: str) -> list[float]:
        """Actual encoding — called by the cache on misses."""
        self._load_model()
        import torch
        inputs = self._tokenizer(code, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            outputs = self._model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).squeeze().tolist()

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
            ea, eb = self._encode(ca), self._encode(cb)
        except Exception as exc:
            logger.error("Embedding encoding failed for code pair: %s", exc)
            return 0.0

        dot = sum(x * y for x, y in zip(ea, eb))
        na = sum(x * x for x in ea) ** 0.5
        nb = sum(x * x for x in eb) ** 0.5

        if na == 0 or nb == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (na * nb)))


class UniXcoderSimilarity(CodeBERTSimilarity):
    """UniXcoder variant using microsoft/unixcoder-base."""

    def __init__(self, device: str = "auto") -> None:
        super().__init__("microsoft/unixcoder-base", device)