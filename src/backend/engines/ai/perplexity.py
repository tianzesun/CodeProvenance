"""Perplexity and burstiness scoring for AI-generated code detection.

Computes a statistical character/token-level perplexity estimate over windowed
chunks of source code (mirroring how Turnitin overlaps sentence windows) and
derives a burstiness signal from the variance of per-chunk perplexity.

The scorer ships with a self-contained, offline statistical model so it works
with no downloads. Optionally, if a causal HuggingFace code LM is available and
cached locally, it is used instead to compute next-token log-likelihoods for a
more accurate signal.
"""

from __future__ import annotations

import itertools
import logging
import math
import os
import re
import threading
import time
from collections import Counter, defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|\d+\.\d+|\d+|<=|>=|==|!=|[()\[\]{},.;:+\-*\/%=<>!]"
)

_MODEL_BITS_REF = {
    "statistical": 2.2,
    "huggingface": 8.0,
}

#: Burstiness reported when there is not enough data to measure variation.
NEUTRAL_BURSTINESS = 0.5

# Process-wide cache of loaded code LMs: name -> (tokenizer, model). Loading a
# causal LM costs ~17s on CPU, and scorers are constructed per analysis job, so
# without this cache every job would reload the model from disk.
_TRANSFORMER_CACHE: dict[str, tuple[Any, Any]] = {}
# model name -> time of the last failed attempt. A missing checkpoint is the
# normal case on most deployments; without this every job re-probed the disk
# (and re-imported ``transformers``) for it.
_TRANSFORMER_FAILED: dict[str, float] = {}
_TRANSFORMER_RETRY_SECONDS = 300.0
_TRANSFORMER_CACHE_LOCK = threading.Lock()


class TransformerScoringError(RuntimeError):
    """The causal LM could not score a chunk."""


def _load_cached_transformer(model_name: str) -> tuple[Any, Any] | None:
    """Load a HuggingFace causal LM once per process (no network access).

    Returns (tokenizer, model) or None when the checkpoint is not available
    locally, so callers fall back to the statistical model. The lock is held for
    the whole load (single flight): concurrent first callers used to each start
    their own multi-second load.
    """
    with _TRANSFORMER_CACHE_LOCK:
        cached = _TRANSFORMER_CACHE.get(model_name)
        if cached is not None:
            return cached
        failed_at = _TRANSFORMER_FAILED.get(model_name)
        if failed_at is not None and time.monotonic() - failed_at < _TRANSFORMER_RETRY_SECONDS:
            return None

        try:
            # Intentionally imported here so missing deps don't break launches.
            from transformers import AutoModelForCausalLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            # A causal (autoregressive) code LM: next-token log-likelihoods are
            # cheap to compute and well-calibrated. Encoder-only checkpoints
            # (e.g. microsoft/codebert-base) carry no LM head, so loading them as
            # MaskedLM yields a random head and meaningless perplexity; the
            # CausalLM load fails fast on those instead.
            model = AutoModelForCausalLM.from_pretrained(model_name, local_files_only=True)
            model.eval()
        except Exception as exc:
            _TRANSFORMER_FAILED[model_name] = time.monotonic()
            logger.info(
                "HF code LM %s unavailable locally, using statistical model: %s",
                model_name,
                exc,
            )
            return None

        _TRANSFORMER_FAILED.pop(model_name, None)
        entry = (tokenizer, model)
        _TRANSFORMER_CACHE[model_name] = entry
        return entry  # the cached object itself, so every caller shares one pair


def _bits_per_token(model: str, perplexity: float) -> float:
    """Convert a perplexity value to per-token surprise bits."""
    if perplexity <= 1.0:
        return 0.0
    return math.log2(perplexity)


def _perplexity_to_score(perplexity: float, model: str) -> float:
    """Map a perplexity value to an AI-likelihood score in [0,1].

    Uses a logistic curve on per-token surprise bits, centered on a reference
    calibrated per model. Low perplexity => low bits => high AI-likelihood.
    The linear ``(10 - x) / 10`` map used previously is only valid for the
    statistical model (perplexity ~2-3); a causal code LM (e.g. CodeGPT) has a
    different scale (perplexity ~10-2000 for realistic code), so bits and a
    per-model reference keep the signal meaningful for both.
    """
    if perplexity <= 0.0:
        return 0.5
    bits = _bits_per_token(model, perplexity)
    ref = _MODEL_BITS_REF.get(model, 2.2)
    score = 1.0 / (1.0 + math.exp(3.0 * (bits - ref)))
    return max(0.0, min(1.0, score))


_BLANK_RE = re.compile(r"^\s*$")
_COMMENT_RE = re.compile(r"^\s*(#|//|/\*|\*|--)")

_CODE_SUFFIXES = frozenset(
    {".py", ".java", ".c", ".cpp", ".h", ".cc", ".cs", ".js", ".ts", ".go", ".rs", ".rb", ".php"}
)


class TokenPerplexityModel:
    """Offline statistical n-gram (bigram/unigram) language model for code.

    Estimates token log-probabilities from training code. This is a deliberately
    simple model used to detect textual uniformity: AI-generated code tends to be
    more predictable (lower perplexity, higher log-probability) than idiosyncratic
    human code.
    """

    def __init__(self, n: int = 2) -> None:
        self.n = n
        self._unigrams: Counter = Counter()
        self._ngrams: defaultdict = defaultdict(Counter)
        # context -> total count. Kept incrementally so scoring is O(1) per token
        # instead of summing every successor of the context.
        self._context_totals: Counter = Counter()
        self._total: int = 0

    def train(self, code: str) -> None:
        """Incrementally train the model on source code."""
        tokens = ["<s>"] + _tokenize(code) + ["</s>"]
        for i, token in enumerate(tokens):
            self._unigrams[token] += 1
            self._total += 1
            if i >= self.n - 1:
                context = tuple(tokens[i - self.n + 1 : i])
                self._ngrams[context][token] += 1
                self._context_totals[context] += 1

    def train_texts(self, texts: list[str]) -> None:
        """Train on a list of source code strings."""
        for text in texts:
            self.train(text)

    def train_corpus(self, directory: str) -> int:
        """Train on all source files in a directory. Returns file count."""
        from pathlib import Path

        count = 0
        for path in Path(directory).rglob("*"):
            if path.suffix.lower() in _CODE_SUFFIXES:
                try:
                    self.train(path.read_text(encoding="utf-8", errors="replace"))
                    count += 1
                except OSError:
                    continue
        return count

    def _log_prob(self, token: str, context: tuple[str, ...]) -> float:
        """Backoff-log-probability of a token given its context."""
        denom = self._context_totals.get(context, 0)
        if denom > 0:
            # ``.get``: indexing the defaultdict inserted an empty Counter for
            # every unseen context, so merely SCORING code grew the model.
            count = self._ngrams.get(context, {}).get(token, 0)
            if count > 0:
                return math.log2(count / denom)
        if self._total > 0:
            unigram = self._unigrams.get(token, 0)
            prob = (unigram + 0.5) / (self._total + 0.5 * len(self._unigrams))
            return math.log2(prob)
        return math.log2(1.0 / 50000.0)

    def average_log_prob(self, code: str) -> float | None:
        """Mean per-token log-probability of code under this model."""
        tokens = _tokenize(code)
        if not tokens:
            return None
        sequence = ["<s>"] + tokens
        total = 0.0
        count = 0
        for i, token in enumerate(sequence[1:], start=1):
            context = tuple(sequence[max(0, i - self.n + 1) : i])
            total += self._log_prob(token, context)
            count += 1
        if count == 0:
            return None
        return total / count

    def perplexity(self, code: str) -> float | None:
        """Perplexity of code under the model (lower = more predictable)."""
        avg_log_prob = self.average_log_prob(code)
        if avg_log_prob is None:
            return None
        return 2.0 ** (-avg_log_prob)


def _tokenize(code: str) -> list[str]:
    """Tokenize source code into tokens for the language model."""
    return _TOKEN_RE.findall(code)


def _windowed_chunks(
    code: str, window: int = 25, overlap: int = 5
) -> list[dict[str, Any]]:
    """Split code into windowed line chunks with overlap.

    Mirrors Turnitin's overlapping sentence windows so burstiness can be
    measured across the span of the file. Returns a list of chunk dicts with
    ``lines`` (the chunk text), ``start_line`` and ``end_line`` (1-based line
    numbers within the original source) so downstream consumers can map a
    chunk back to the exact lines it covers.

    A window whose lines were ALL already covered by the previous window (what
    remains is no more than the overlap) is not emitted. A 25-line file used to
    yield a second 5-line chunk repeating its last lines, which fed a noisy
    small sample into the burstiness calculation.
    """
    lines = code.splitlines()
    if not lines:
        return []
    # Sanitise the configuration (it comes from a YAML file): a window below 1
    # produced no chunks at all, and an overlap >= window never advanced.
    window = max(1, int(window))
    overlap = max(0, min(int(overlap), window - 1))
    chunks: list[dict[str, Any]] = []
    step = window - overlap
    for start in range(0, len(lines), step):
        if start > 0 and start + overlap >= len(lines):
            break  # nothing here that the previous window did not already cover
        chunk_lines = lines[start : start + window]
        if not chunk_lines:
            continue
        chunk_text = "\n".join(chunk_lines)
        if chunk_text.strip():
            chunks.append(
                {
                    "lines": chunk_text,
                    "start_line": start + 1,
                    "end_line": start + len(chunk_lines),
                }
            )
    return chunks


class PerplexityScorer:
    """Compute perplexity and burstiness signals for a submission.

    Uses the statistical :class:`TokenPerplexityModel` by default. If a
    HuggingFace code LM is available (an explicit ``model_path`` or the
    ``AICODE_TRANSFORMER_MODEL`` env var, and a cached download), it is used for
    token log-likelihoods instead.
    """

    def __init__(
        self,
        model_path: str | None = None,
        window: int = 25,
        overlap: int = 5,
        transformer: bool = True,
    ) -> None:
        self.window = window
        self.overlap = overlap
        self.model = TokenPerplexityModel(n=2)
        self._huggingface = None
        self._tokenizer = None
        self._transformer_available = False
        # Only probe a transformer model when one is explicitly configured.
        # Without a name, importing `transformers` is an expensive (+10s) load
        # that would slow every scoring call in a fresh deployment.
        model_name = model_path or os.getenv("AICODE_TRANSFORMER_MODEL", "")
        if transformer and model_name:
            loaded = _load_cached_transformer(model_name)
            if loaded is not None:
                self._tokenizer, self._huggingface = loaded
                self._transformer_available = True

    def train(self, texts: list[str]) -> None:
        """Train the statistical model on a set of code strings."""
        self.model.train_texts(texts)

    def score(self, code: str) -> dict[str, Any]:
        """Compute perplexity, burstiness and chunk-level signals.

        Returns a dict with the raw signal values. Higher ``ai_likelihood``
        means the text looks more AI-generated (low perplexity + high
        uniformity).
        """
        chunks = _windowed_chunks(code, self.window, self.overlap)
        if not chunks:
            return self._empty_result()

        per_chunk: list[dict[str, Any]] = []
        chunk_scores: list[float] = []
        model_used = "statistical"
        if self._transformer_available:
            try:
                per_chunk, chunk_scores = self._score_chunks(chunks, self._transformer_perplexity)
                model_used = "huggingface"
            except TransformerScoringError as exc:
                # One chunk failing used to fall back for THAT chunk only, giving
                # a result that mixed perplexities on two different scales
                # (~2 vs thousands) under a single "huggingface" label. Re-score
                # the whole file with the statistical model instead.
                logger.info("Transformer perplexity failed, using statistical model: %s", exc)
        if model_used == "statistical":
            per_chunk, chunk_scores = self._score_chunks(chunks, self._statistical_perplexity)

        if not chunk_scores:
            return self._empty_result()

        avg_perplexity = sum(chunk_scores) / len(chunk_scores)
        burstiness = self._burstiness(chunk_scores, avg_perplexity)
        avg_log_prob = sum(chunk["avg_log_prob"] for chunk in per_chunk) / len(per_chunk)

        # Map perplexity to [0,1] AI-likelihood (low perplexity => high likeness).
        perplexity_score = _perplexity_to_score(avg_perplexity, model_used)

        return {
            "perplexity": round(avg_perplexity, 3),
            "burstiness": round(burstiness, 3),
            "avg_log_prob": round(avg_log_prob, 4),
            "ai_likelihood": round(0.6 * perplexity_score + 0.4 * burstiness, 3),
            "per_chunk": per_chunk,
            "model": model_used,
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "perplexity": 0.0,
            "burstiness": NEUTRAL_BURSTINESS,
            "avg_log_prob": 0.0,
            "ai_likelihood": 0.5,
            "per_chunk": [],
            "model": "statistical",
        }

    @staticmethod
    def _burstiness(chunk_scores: list[float], mean: float) -> float:
        """Uniformity of chunk perplexity: 1.0 = perfectly uniform (AI-like).

        Needs at least two chunks. With one chunk the variance is trivially zero,
        so every file of up to ~20 lines used to score the maximum AI-like value
        for this signal. That case now reports a neutral value instead.
        """
        if len(chunk_scores) < 2:
            return NEUTRAL_BURSTINESS
        variance = sum((x - mean) ** 2 for x in chunk_scores) / len(chunk_scores)
        cv = math.sqrt(variance) / mean if mean > 0 else 0.0
        return min(1.0, max(0.0, 1.0 - cv / 1.2))

    @staticmethod
    def _score_chunks(chunks: list[dict[str, Any]], scorer) -> tuple[list[dict[str, Any]], list[float]]:
        per_chunk: list[dict[str, Any]] = []
        scores: list[float] = []
        for chunk in chunks:
            perplexity, avg_log_prob = scorer(chunk["lines"])
            if perplexity is None:
                continue
            per_chunk.append(
                {
                    "perplexity": round(perplexity, 3),
                    "avg_log_prob": round(avg_log_prob, 4),
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                }
            )
            scores.append(perplexity)
        return per_chunk, scores

    def _statistical_perplexity(self, code: str) -> tuple[float | None, float | None]:
        """Return (perplexity, avg_log_prob) using the local statistical model.

        Falls back to a per-document mini language model when the global model
        has not been trained on a corpus, so the signal stays non-degenerate in
        a fresh deployment. The per-document model measures internal
        predictability (repetitive, uniform code scores lower perplexity).
        """
        if self.model._total > 0:
            avg_log_prob = self.model.average_log_prob(code)
        else:
            avg_log_prob = self._document_average_log_prob(code)
        if avg_log_prob is None:
            return None, None
        return 2.0 ** (-avg_log_prob), avg_log_prob

    def _document_average_log_prob(self, code: str) -> float | None:
        """Mean per-token log-probability from a per-document recurrence model.

        Measures how predictable each token is given the previous token, using
        only the code itself. Repetitive, uniform code (typical of AI output)
        yields high recurrence probability (e.g. ``result`` almost always
        followed by ``=``), while eclectic human code spreads successors across
        many tokens. Results are bounded: recurrence probabilities are clamped
        to [1/vocab, 1] so perplexity stays in a sane range.
        """
        tokens = _tokenize(code)
        if len(tokens) < 4:
            return None

        vocab = len(set(tokens))
        successors: defaultdict = defaultdict(Counter)
        for word, following in itertools.pairwise(tokens):
            successors[word][following] += 1
        successor_totals = {word: sum(c.values()) for word, c in successors.items()}

        total_log = 0.0
        count = 0
        for word, following in itertools.pairwise(tokens):
            emp_prob = successors[word][following] / successor_totals[word]
            # Laplace-style floor keeps log probabilities finite
            prob = 0.3 * (1.0 / vocab) + 0.7 * max(emp_prob, 1.0 / vocab)
            total_log += math.log2(prob)
            count += 1
        if count == 0:
            return None
        return total_log / count

    def _transformer_perplexity(self, code: str) -> tuple[float | None, float | None]:
        """Return (perplexity, avg_log_prob) using a HuggingFace code LM.

        Uses a causal (autoregressive) code LM: one forward pass yields
        next-token log-likelihoods for every position, so the whole window is
        scored in a single call (no per-token masking loop). Requires a locally
        cached causal code LM (e.g. microsoft/CodeGPT-small-py); encoder-only
        checkpoints like microsoft/codebert-base are rejected at load time.
        Only the first 256 tokens of a window are scored.

        Raises:
            TransformerScoringError: if the model cannot score this chunk.
        """
        try:
            import torch

            inputs = self._tokenizer(
                code, return_tensors="pt", truncation=True, max_length=256
            )
            input_ids = inputs["input_ids"]
            if input_ids.numel() < 2:
                return None, None

            with torch.no_grad():
                logits = self._huggingface(
                    input_ids=input_ids, attention_mask=inputs["attention_mask"]
                ).logits
            # Shift so logits[t] predicts token t+1 (causal next-token LM).
            shift_logits = logits[0, :-1].contiguous()
            shift_labels = input_ids[0, 1:]
            log_probs = torch.log_softmax(shift_logits, dim=-1)
            per_token = log_probs.gather(1, shift_labels.unsqueeze(1)).squeeze(1)
            avg_log_prob = per_token.sum().item() / shift_labels.numel()
            return 2.0 ** (-avg_log_prob), avg_log_prob
        except Exception as exc:  # pragma: no cover
            raise TransformerScoringError(str(exc)) from exc


def score_code(code: str, scorer: PerplexityScorer | None = None) -> dict[str, Any]:
    """Module-level convenience: score a snippet with the default scorer."""
    if scorer is None:
        scorer = PerplexityScorer()
    return scorer.score(code)


if __name__ == "__main__":
    # Quick smoke test: train on a few snippets then score
    demo = [
        "if x < 0: return -x else: return x",
        "for i in range(n):\n    total += i",
        "def f(a, b):\n    return a * b",
    ]
    s = PerplexityScorer()
    s.train(demo)
    print(s.score("for i in range(n):\n    total += i"))
