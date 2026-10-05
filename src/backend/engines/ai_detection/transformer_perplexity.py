"""Transformer-based perplexity calculation for AI detection.

Uses a causal language model (GPT-2 by default) for token-level perplexity instead of
bigram approximations. Low perplexity means highly predictable code, which is *one* weak
indicator of machine generation.

IMPORTANT - calibration: perplexity depends heavily on length, language, comments and how
"textbook" the task is. Short, canonical student solutions (the first loop, a fibonacci
function) are low-perplexity for entirely human reasons. The thresholds in
:func:`perplexity_to_ai_score` are heuristic defaults, not validated cut-offs: calibrate them on
your own labelled human/AI data before relying on the score, and never use it alone.

Failures are reported as *unavailable* (``None`` / ``available=False``), never as a made-up
"human-typical" perplexity of 100: an unavailable model used to look like evidence of human
authorship.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
import time
import warnings
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

#: Longest source text (characters) that is tokenized; the rest is ignored.
MAX_CHARS = 200_000
#: Fewer tokens than this give a meaningless perplexity.
MIN_TOKENS = 32
DEFAULT_MAX_LENGTH = 1024
DEFAULT_STRIDE = 512
#: Loss is clamped before ``exp`` (``exp(90)`` overflows float32; 20 is already "random text").
_MAX_LOSS = 20.0
_FAILURE_BACKOFF_SECONDS = 300.0

# (upper bound of perplexity, AI score at the upper bound) - piecewise linear, continuous.
_SCORE_POINTS: tuple[tuple[float, float], ...] = (
    (20.0, 1.0),
    (35.0, 0.8),
    (60.0, 0.4),
    (100.0, 0.1),
)


class PerplexityUnavailable(RuntimeError):
    """The model cannot be loaded or the input is unusable."""


def perplexity_to_ai_score(perplexity: float) -> tuple[float, str]:
    """Map a perplexity to an AI-likelihood score in [0, 1] and a short description.

    Heuristic mapping (see the module note on calibration): below 20 -> 1.0, 35 -> 0.8,
    60 -> 0.4, 100 -> 0.1, then decaying to 0.0 by 120+.
    """
    if not math.isfinite(perplexity) or perplexity < 0:
        raise ValueError(f"invalid perplexity: {perplexity!r}")
    if perplexity < _SCORE_POINTS[0][0]:
        return 1.0, "Very high AI likelihood (extremely predictable)"
    for (x0, y0), (x1, y1) in zip(_SCORE_POINTS, _SCORE_POINTS[1:]):
        if perplexity < x1:
            score = y0 + (perplexity - x0) / (x1 - x0) * (y1 - y0)
            label = (
                "High AI likelihood (low perplexity)"
                if x1 <= 35.0
                else "Moderate likelihood (borderline)"
                if x1 <= 60.0
                else "Low AI likelihood (human-typical)"
            )
            return max(0.0, min(1.0, score)), label
    score = max(0.0, 0.1 - (perplexity - 100.0) / 200.0)
    return score, "Very low AI likelihood (high variance)"


def windowed_nll(
    token_ids: Sequence[int],
    score_window: Callable[[Sequence[int], int], tuple[float, int]],
    max_length: int = DEFAULT_MAX_LENGTH,
    stride: int = DEFAULT_STRIDE,
) -> tuple[float, int]:
    """Total negative log-likelihood of ``token_ids[1:]`` using strided windows.

    Every token after the first is scored exactly once, with up to ``max_length - 1`` tokens
    of left context (the standard sliding-window recipe). The old code truncated the input to
    ``max_length`` tokens, which silently made its sliding-window branch dead code, and its
    windows also re-scored the overlapping tokens.

    ``score_window(window, n_targets)`` must return ``(sum_nll, n_scored)`` for the LAST
    ``n_targets`` tokens of ``window``; when ``n_targets == len(window)`` the first token has no
    context and is not scored (``n_scored == n_targets - 1``).
    """
    length = len(token_ids)
    if max_length < 2:
        raise ValueError("max_length must be at least 2")
    # stride <= max_length - 1 keeps at least one token of left context in every window; with
    # no overlap the first token of each window would have no context and be dropped.
    stride = max(1, min(stride, max_length - 1))
    total_nll, total_tokens, prev_end = 0.0, 0, 0
    for begin in range(0, length, stride):
        end = min(begin + max_length, length)
        n_targets = end - prev_end
        if n_targets <= 0:
            break
        nll, scored = score_window(token_ids[begin:end], n_targets)
        total_nll += nll
        total_tokens += scored
        prev_end = end
        if end == length:
            break
    return total_nll, total_tokens


class TransformerPerplexityAnalyzer:
    """Compute code perplexity with a causal language model.

    The model is loaded lazily, once per analyzer, under a lock (the old ``lru_cache`` on a
    method kept a single entry shared by ALL instances, so two analyzers evicted each other's
    model, and concurrent first calls loaded the model twice). A failed load is remembered:
    a missing dependency permanently, anything else for five minutes.
    """

    def __init__(self, model_name: str = "gpt2", device: str | None = None):
        """
        Args:
            model_name: Hugging Face causal-LM name (default ``gpt2``, the smallest/fastest).
            device: ``'cpu'``, ``'cuda'`` or None to auto-detect (CUDA when available).
        """
        self.model_name = model_name
        self._requested_device = device
        self.device: str = device or "cpu"
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.Lock()
        self._failed_until = 0.0
        self._failure: str = ""
        self._permanent_failure = False

    # ------------------------------------------------------------------ loading

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            if self._permanent_failure or time.monotonic() < self._failed_until:
                raise PerplexityUnavailable(self._failure)
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                device = self._requested_device or ("cuda" if torch.cuda.is_available() else "cpu")
                local_only = os.getenv("AI_DETECT_LOCAL_FILES_ONLY", "").lower() in {"1", "true", "yes"}
                logger.info("Loading %s on %s (first load can take 10-20s)", self.model_name, device)
                with warnings.catch_warnings():  # (this used to filter warnings process-wide at import)
                    warnings.filterwarnings("ignore", message=".*were not initialized.*")
                    warnings.filterwarnings("ignore", message=".*is better suited.*")
                    tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=local_only)
                    model = AutoModelForCausalLM.from_pretrained(self.model_name, local_files_only=local_only)
                model.to(device)
                model.eval()
                self.device, self._tokenizer, self._model = device, tokenizer, model
            except ImportError as exc:
                self._permanent_failure = True
                self._failure = f"transformers/torch not installed: {exc}"
                raise PerplexityUnavailable(self._failure) from exc
            except Exception as exc:
                self._failed_until = time.monotonic() + _FAILURE_BACKOFF_SECONDS
                self._failure = f"could not load {self.model_name}: {exc}"
                logger.error(self._failure)
                raise PerplexityUnavailable(self._failure) from exc

    @property
    def model(self):
        """The language model (loaded on first access)."""
        self._ensure_loaded()
        return self._model

    @property
    def tokenizer(self):
        """The tokenizer (loaded on first access)."""
        self._ensure_loaded()
        return self._tokenizer

    def _context_limit(self) -> int:
        config = getattr(self.model, "config", None)
        for attr in ("n_positions", "max_position_embeddings"):
            value = getattr(config, attr, None)
            if isinstance(value, int) and value > 1:
                return value
        return DEFAULT_MAX_LENGTH

    # ------------------------------------------------------------------ tokenizing / scoring

    def _encode(self, code: str) -> list[int]:
        """Token ids with the BOS token prepended so the FIRST real token is scored too."""
        tokenizer = self.tokenizer
        try:  # literal "<|endoftext|>" in a submission must stay plain text, not a special token
            ids = tokenizer.encode(code, add_special_tokens=False, split_special_tokens=True)
        except TypeError:
            ids = tokenizer.encode(code, add_special_tokens=False)
        bos = getattr(tokenizer, "bos_token_id", None)
        return ([bos] if bos is not None else []) + list(ids)

    def _score_window(self, window: Sequence[int], n_targets: int) -> tuple[float, int]:
        """NLL of the last ``n_targets`` tokens of ``window`` (torch)."""
        import torch

        input_ids = torch.tensor([list(window)], device=self.device)
        labels = input_ids.clone()
        if n_targets < input_ids.size(1):
            labels[:, :-n_targets] = -100  # context only, not scored
        n_scored = n_targets - 1 if n_targets == input_ids.size(1) else n_targets
        if n_scored <= 0:
            return 0.0, 0
        with torch.inference_mode():
            loss = self.model(input_ids, labels=labels).loss.item()
        return float(loss) * n_scored, n_scored

    # ------------------------------------------------------------------ cache (optional)

    def _cache_key(self, code: str, max_length: int, stride: int) -> str:
        # Exact text, not a "semantic" hash: perplexity depends on the identifiers, so two
        # programs that differ only in names must NOT share an entry (they used to).
        digest = hashlib.sha256(code.encode("utf-8", "surrogatepass")).hexdigest()
        return f"perplexity:{self.model_name}:{max_length}:{stride}:{digest}"

    @staticmethod
    def _get_cache():
        try:
            from src.backend.infrastructure.cache import get_cache

            return get_cache()
        except Exception:  # no cache configured: just compute (this import used to be fatal)
            return None

    # ------------------------------------------------------------------ public API

    def compute_perplexity(
        self,
        code: str,
        max_length: int = DEFAULT_MAX_LENGTH,
        stride: int = DEFAULT_STRIDE,
        use_cache: bool = True,
    ) -> float | None:
        """Perplexity of ``code`` (lower = more predictable), or None when unavailable.

        None means the code is too short for a meaningful value (< ``MIN_TOKENS`` tokens) or the
        model cannot be used. Long code is scored in full with a sliding window (the old code
        looked only at the first ``max_length`` tokens).

        Typical values for GPT-2 on code are ~15-35 for very predictable text and 40-120 for
        typical human code, but see the module note: these ranges are not validated.
        """
        if not isinstance(code, str) or len(code.strip()) < 10:
            return None
        code = code[:MAX_CHARS]
        try:
            self._ensure_loaded()
        except PerplexityUnavailable as exc:
            logger.debug("Perplexity unavailable: %s", exc)
            return None
        max_length = max(2, min(int(max_length), self._context_limit()))
        stride = max(1, min(int(stride), max_length - 1))

        cache = self._get_cache() if use_cache else None
        key = self._cache_key(code, max_length, stride)
        if cache is not None:
            try:
                cached = cache.get(key)
                if isinstance(cached, (int, float)) and math.isfinite(cached) and cached > 0:
                    return float(cached)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Perplexity cache read failed: %s", exc)

        try:
            ids = self._encode(code)
            if len(ids) - 1 < MIN_TOKENS:
                return None
            nll, tokens = windowed_nll(ids, self._score_window, max_length, stride)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Perplexity computation failed: %s", exc)
            return None
        if tokens <= 0 or not math.isfinite(nll):
            return None
        result = math.exp(min(_MAX_LOSS, nll / tokens))

        if cache is not None:
            try:
                cache.set(key, result, ttl=86400)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Perplexity cache write failed: %s", exc)
        return result

    def compute_normalized_score(self, code: str, max_length: int = DEFAULT_MAX_LENGTH) -> dict[str, Any]:
        """Perplexity normalised to an AI-likelihood score.

        Returns:
            ``{"available": bool, "raw_perplexity": float | None, "ai_score": float | None,
            "interpretation": str, "token_count": int | None}``. ``ai_score`` is None when the
            perplexity could not be computed; callers must fall back, not assume "human".
        """
        perplexity = self.compute_perplexity(code, max_length=max_length)
        if perplexity is None:
            return {
                "available": False,
                "raw_perplexity": None,
                "ai_score": None,
                "interpretation": "Perplexity unavailable (input too short or model not loaded)",
                "token_count": None,
            }
        ai_score, interpretation = perplexity_to_ai_score(perplexity)
        try:
            token_count = len(self._encode(code[:MAX_CHARS])) - 1
        except Exception:  # noqa: BLE001
            token_count = None
        return {
            "available": True,
            "raw_perplexity": round(perplexity, 2),
            "ai_score": round(ai_score, 3),
            "interpretation": interpretation,
            "token_count": token_count,
        }

    def batch_analyze(self, code_samples: list[str], max_length: int = DEFAULT_MAX_LENGTH) -> list[dict]:
        """Analyse several samples (one result per sample; a failing sample is 'unavailable')."""
        return [self.compute_normalized_score(code, max_length=max_length) for code in code_samples]


# One analyzer (and one model) per model name, created under a lock.
_analyzers: dict[str, TransformerPerplexityAnalyzer] = {}
_analyzers_lock = threading.Lock()


def get_analyzer(model_name: str = "gpt2") -> TransformerPerplexityAnalyzer:
    """Get or create the shared analyzer for ``model_name``.

    (Asking for a different model used to REPLACE the global analyzer, discarding the loaded
    one and thrashing between models.)
    """
    with _analyzers_lock:
        analyzer = _analyzers.get(model_name)
        if analyzer is None:
            analyzer = _analyzers[model_name] = TransformerPerplexityAnalyzer(model_name=model_name)
        return analyzer


def compute_perplexity(code: str, max_length: int = DEFAULT_MAX_LENGTH) -> float | None:
    """Convenience: perplexity for ``code`` (None when unavailable)."""
    return get_analyzer().compute_perplexity(code, max_length=max_length)


def compute_ai_score(code: str, max_length: int = DEFAULT_MAX_LENGTH) -> dict[str, Any]:
    """Convenience: normalised AI score dict (see :meth:`compute_normalized_score`)."""
    return get_analyzer().compute_normalized_score(code, max_length=max_length)
