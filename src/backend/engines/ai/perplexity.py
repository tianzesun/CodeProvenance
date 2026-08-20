"""Perplexity and burstiness scoring for AI-generated code detection.

Computes a statistical character/token-level perplexity estimate over windowed
chunks of source code (mirroring how Turnitin overlaps sentence windows) and
derives a burstiness signal from the variance of per-chunk perplexity.

The scorer ships with a self-contained, offline statistical model so it works
with no downloads. Optionally, if a HuggingFace code LM (CodeBERT, CodeT5, ...)
is available and cached, it is used instead to compute masked-token
log-likelihoods for a more accurate signal.
"""

from __future__ import annotations

import itertools
import logging
import math
import os
import re
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

    def train_texts(self, texts: list[str]) -> None:
        """Train on a list of source code strings."""
        for text in texts:
            self.train(text)

    def train_corpus(self, directory: str) -> int:
        """Train on all source files in a directory. Returns file count."""
        from pathlib import Path

        count = 0
        for path in Path(directory).rglob("*"):
            if path.suffix.lower() in {
                ".py",
                ".java",
                ".c",
                ".cpp",
                ".h",
                ".cc",
                ".cs",
                ".js",
                ".ts",
                ".go",
                ".rs",
                ".rb",
                ".php",
            }:
                try:
                    self.train(path.read_text(encoding="utf-8", errors="replace"))
                    count += 1
                except OSError:
                    continue
        return count

    def _log_prob(self, token: str, context: tuple[str, ...]) -> float:
        """Backoff-log-probability of a token given its context."""
        denom = sum(self._ngrams[context].values())
        if denom > 0:
            prob = self._ngrams[context][token] / denom
            if prob > 0:
                return math.log2(prob)
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
    """
    lines = code.splitlines()
    if not lines:
        return []
    chunks: list[dict[str, Any]] = []
    step = max(1, window - overlap)
    for start in range(0, len(lines), step):
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
    HuggingFace code LM is available (``AICODE_TRANSFORMER_MODEL`` env var and
    a cached download), it is used for token log-likelihoods instead.
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
        self._transformer_available = False
        self._transformer_probed = False
        # Only probe a transformer model when one is explicitly configured.
        # Without a name, importing `transformers` is an expensive (+10s) load
        # that would slow every scoring call in a fresh deployment.
        if transformer and (model_path or os.getenv("AICODE_TRANSFORMER_MODEL", "")):
            self._try_load_transformer(model_path)

    def _try_load_transformer(self, model_path: str | None) -> None:
        """Lazily attempt to load a cached HuggingFace code LM (no download).

        Only runs when a model name is explicitly configured (env var or arg),
        because importing ``transformers`` is expensive.
        """
        if self._transformer_probed:
            return
        self._transformer_probed = True

        env_model = os.getenv("AICODE_TRANSFORMER_MODEL", "")
        model_name = model_path or env_model
        if not model_name:
            self._load_from_local_cache()
            return

        try:
            # Intentionally import inside the method so missing deps don't break
            # launches. Never triggers a network download.
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            # A causal (autoregressive) code LM: next-token log-likelihoods are
            # cheap to compute and well-calibrated. Encoder-only checkpoints
            # (e.g. microsoft/codebert-base) advertise `RobertaModel` and carry
            # no LM head, so loading them as MaskedLM yields a random head and
            # meaningless perplexity; CausalLM load fails fast on those instead.
            self._huggingface = AutoModelForCausalLM.from_pretrained(
                model_name, local_files_only=True
            )
            self._huggingface.eval()
            self._transformer_available = True
            logger.info("Loaded HF code LM %s for perplexity", model_name)
        except Exception as exc:  # pragma: no cover
            logger.info(
                "HF code LM %s unavailable locally, using statistical model: %s",
                model_name,
                exc,
            )

    def _load_from_local_cache(self) -> None:
        """Try common local cache names for a code LM (no network)."""
        candidates = ["microsoft/CodeGPT-small-py", "microsoft/codegen-350M-mono"]
        for candidate in candidates:
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    candidate, local_files_only=True
                )
                self._huggingface = AutoModelForCausalLM.from_pretrained(
                    candidate, local_files_only=True
                )
                self._huggingface.eval()
                self._transformer_available = True
                logger.info("Loaded HF code LM %s from local cache", candidate)
                return
            except Exception:
                logger.debug("Failed to load HF model %s", candidate, exc_info=True)
                continue

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
            return {
                "perplexity": 0.0,
                "burstiness": 0.0,
                "avg_log_prob": 0.0,
                "ai_likelihood": 0.5,
                "per_chunk": [],
                "model": "statistical",
            }

        per_chunk: list[dict[str, Any]] = []
        chunk_scores: list[float] = []
        for chunk in chunks:
            if self._transformer_available:
                perplexity, avg_log_prob = self._transformer_perplexity(chunk["lines"])
            else:
                perplexity, avg_log_prob = self._statistical_perplexity(chunk["lines"])
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
            chunk_scores.append(perplexity)

        if not chunk_scores:
            return {
                "perplexity": 0.0,
                "burstiness": 0.0,
                "avg_log_prob": 0.0,
                "ai_likelihood": 0.5,
                "per_chunk": [],
                "model": "statistical",
            }

        avg_perplexity = sum(chunk_scores) / len(chunk_scores)
        # Burstiness = coefficient of variation of chunk perplexity
        mean = avg_perplexity
        variance = sum((x - mean) ** 2 for x in chunk_scores) / len(chunk_scores)
        std = math.sqrt(variance)
        cv = std / mean if mean > 0 else 0.0
        burstiness = min(1.0, max(0.0, 1.0 - cv / 1.2))

        avg_log_prob = sum(chunk.get("avg_log_prob", 0.0) for chunk in per_chunk) / len(
            per_chunk
        )

        model_used = "huggingface" if self._transformer_available else "statistical"

        # Map perplexity to [0,1] AI-likelihood (low perplexity => high likeness).
        # Human code remains sparse/random => higher perplexity. The mapping is
        # log-scaled and model-aware (see _perplexity_to_score).
        perplexity_score = _perplexity_to_score(avg_perplexity, model_used)

        return {
            "perplexity": round(avg_perplexity, 3),
            "burstiness": round(burstiness, 3),
            "avg_log_prob": round(avg_log_prob, 4),
            "ai_likelihood": round(0.6 * perplexity_score + 0.4 * burstiness, 3),
            "per_chunk": per_chunk,
            "model": model_used,
        }

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
        answer = 2.0 ** (-avg_log_prob)
        return answer, avg_log_prob

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

        unigrams: Counter = Counter(tokens)
        successors: defaultdict = defaultdict(Counter)
        for word, following in itertools.pairwise(tokens):
            successors[word][following] += 1
        vocab = len(unigrams)

        total_log = 0.0
        count = 0
        for word, following in itertools.pairwise(tokens):
            successor_total = sum(successors[word].values())
            emp_prob = successors[word][following] / successor_total
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
        """
        import torch

        try:
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
            logger.info("Transformer perplexity failed, falling back: %s", exc)
            return self._statistical_perplexity(code)


def score_code(code: str, scorer: PerplexityScorer | None = None) -> dict[str, Any]:
    """Module-level convenience: score a snippet with the default scorer."""
    if scorer is None:
        scorer = PerplexityScorer()
    return scorer.score(code)


if __name__ == "__main__":
    # Quick smoke test: train on a few snippets then score
    import sys

    demo = [
        "if x < 0: return -x else: return x",
        "for i in range(n):\n    total += i",
        "def f(a, b):\n    return a * b",
    ]
    s = PerplexityScorer()
    s.train(demo)
    print(s.score("for i in range(n):\n    total += i"))
    print(sys.getsizeof(s.model._unigrams))
