"""Unit tests for individual similarity engines.

Tests:
- TokenSimilarity (token/keyword/jaccard/ngram metrics)
- NgramSimilarity (n-gram overlap)
- Embedding/UniXcoder fallback behavior
- EngineCache (EmbeddingCache and TokenCache)
"""
from __future__ import annotations

import pytest
from typing import Any, Dict

from src.backend.engines.similarity.ast_similarity import ASTSimilarity
from src.backend.engines.similarity.token_similarity import TokenSimilarity
from src.backend.engines.similarity.ngram_similarity import NgramSimilarity
from src.backend.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
from src.backend.engines.cache import EmbeddingCache, TokenCache, _sha256, get_embedding_cache, get_token_cache, invalidate_all_caches


def _make_parsed(tokens: list[str] | None = None, raw: str | None = None) -> Dict[str, Any]:
    """Helper to create a minimal parsed representation."""
    result: Dict[str, Any] = {}
    if tokens is not None:
        result["tokens"] = tokens
    if raw is not None:
        result["raw"] = raw
    return result


# ─── TokenSimilarity ─────────────────────────────────────────────────────

class TestTokenSimilarity:
    """Tests for the TokenSimilarity engine."""

    def setup_method(self) -> None:
        self.engine = TokenSimilarity()

    def test_identical_code(self) -> None:
        """Identical token sequences should score 1.0."""
        parsed = _make_parsed(tokens=["def", "foo", "(", ")", ":"])
        assert self.engine.compare(parsed, parsed) == 1.0

    def test_disjoint_tokens(self) -> None:
        """Completely disjoint token sets should score low."""
        parsed_a = _make_parsed(tokens=["def", "foo", "(", ")", ":"])
        parsed_b = _make_parsed(tokens=["class", "Bar", "{", "}"])
        score = self.engine.compare(parsed_a, parsed_b)
        # distribution + keyword similarity may raise score slightly; keep < 0.3
        assert score < 0.3

    def test_partial_overlap(self) -> None:
        """Partial overlap should score between 0 and 1."""
        parsed_a = _make_parsed(tokens=["def", "foo", "(", ")", ":"])
        parsed_b = _make_parsed(tokens=["def", "bar", "(", ")", ":"])
        score = self.engine.compare(parsed_a, parsed_b)
        assert 0.0 < float(score) <= 1.0

    def test_empty_tokens(self) -> None:
        """Both empty → 1.0; one empty → 0.0."""
        empty = _make_parsed(tokens=[])
        non_empty = _make_parsed(tokens=["pass"])
        assert self.engine.compare(empty, empty) == 1.0
        assert self.engine.compare(empty, non_empty) == 0.0

    def test_raw_code_tokenization(self) -> None:
        """Raw code string should be tokenized."""
        parsed_a = _make_parsed(raw="def add(a, b): return a + b")
        parsed_b = _make_parsed(raw="def add(x, y): return x + y")
        score = self.engine.compare(parsed_a, parsed_b)
        assert score > 0.5  # Very similar structure

    def test_caching_reduces_re_tokenize(self) -> None:
        """Same raw code should hit cache on second call."""
        raw = "def test(): return 42"
        parsed = _make_parsed(raw=raw)
        # First call misses, second hits
        initial_misses = self.engine._token_cache.misses
        self.engine.compare(parsed, parsed)
        assert self.engine._token_cache.hits > 0

    def test_keyword_similarity(self) -> None:
        """Code with same control-flow keywords should score higher."""
        parsed_a = _make_parsed(tokens=["if", "x", ":", "return", "1"])
        parsed_b = _make_parsed(tokens=["if", "y", ":", "return", "2"])
        # Shares 'if' and 'return' keywords
        score = self.engine.compare(parsed_a, parsed_b)
        assert score > 0.0

    def test_long_token_sequence_ngram(self) -> None:
        """Longer overlapping n-grams should increase score."""
        tokens_a = ["for", "i", "in", "range", "(", "n", ")", ":"]
        tokens_b = ["for", "i", "in", "range", "(", "m", ")", ":"]
        parsed_a = _make_parsed(tokens=tokens_a)
        parsed_b = _make_parsed(tokens=tokens_b)
        # 6/8 tokens differ only by 'n' vs 'm'
        score = self.engine.compare(parsed_a, parsed_b)
        assert score > 0.5


# ─── NgramSimilarity ───────────────────────────────────────────────────

class TestNgramSimilarity:
    """Tests for the NgramSimilarity engine."""

    def setup_method(self) -> None:
        self.engine = NgramSimilarity()

    def test_identical_tokens(self) -> None:
        """Identical token lists → score 1.0."""
        parsed = _make_parsed(tokens=["a", "b", "c", "d", "e"])
        assert self.engine.compare(parsed, parsed) == 1.0

    def test_disjoint_ngrams(self) -> None:
        """No common n-grams → 0.0."""
        parsed_a = _make_parsed(tokens=["x", "y", "z"])
        parsed_b = _make_parsed(tokens=["p", "q", "r"])
        score = self.engine.compare(parsed_a, parsed_b)
        assert score == 0.0

    def test_raw_code_ngrams(self) -> None:
        """Raw code should produce overlapping n-grams."""
        parsed_a = _make_parsed(raw="for i in range(10):")
        parsed_b = _make_parsed(raw="for i in range(20):")
        score = self.engine.compare(parsed_a, parsed_b)
        assert score > 0.5

    def test_empty_tokens(self) -> None:
        """Empty token lists → 1.0 for both empty."""
        empty = _make_parsed(tokens=[])
        assert self.engine.compare(empty, empty) == 1.0


class TestOptionalDependencyFallbacks:
    """Smoke tests for engines that should not hard-fail on optional deps."""

    def test_ast_similarity_smoke(self) -> None:
        engine = ASTSimilarity()
        score = float(
            engine.compare(
                _make_parsed(raw="def add(a, b): return a + b"),
                _make_parsed(raw="def add(x, y): return x + y"),
            )
        )
        assert 0.0 <= score <= 1.0

    def test_winnowing_similarity_smoke(self) -> None:
        engine = EnhancedWinnowingSimilarity()
        score = engine.compare(
            _make_parsed(raw="def add(a, b): return a + b"),
            _make_parsed(raw="def add(x, y): return x + y"),
        )
        assert 0.0 <= score <= 1.0


# ─── Cache Module ──────────────────────────────────────────────────────

class TestSha256:
    """Tests for the _sha256 helper."""

    def test_deterministic(self) -> None:
        """Same input always produces same hash."""
        h1 = _sha256("hello")
        h2 = _sha256("hello")
        assert h1 == h2

    def test_different_inputs(self) -> None:
        """Different inputs produce different hashes."""
        assert _sha256("hello") != _sha256("world")

    def test_length_16(self) -> None:
        """Hash is first 16 hex chars."""
        assert len(_sha256("any content")) == 16


class TestEmbeddingCache:
    """Tests for the EmbeddingCache class."""

    def setup_method(self) -> None:
        self.cache = EmbeddingCache(maxsize=3)

    def test_cache_miss_on_first_call(self) -> None:
        """First call computes and caches."""
        compute_calls = [0]

        def compute(code: str) -> list[float]:
            compute_calls[0] += 1
            return [float(ord(c)) for c in code]

        v1 = self.cache.get_or_compute("abc", compute)
        assert compute_calls[0] == 1
        assert v1 == [97.0, 98.0, 99.0]

    def test_cache_hit_on_second_call(self) -> None:
        """Second call with same content hits cache."""
        compute_calls = [0]

        def compute(code: str) -> list[float]:
            compute_calls[0] += 1
            return [1.0]

        self.cache.get_or_compute("x", compute)
        self.cache.get_or_compute("x", compute)
        assert compute_calls[0] == 1

    def test_eviction(self) -> None:
        """Overflow evicts oldest entry."""
        def compute(code: str) -> list[float]:
            return [float(ord(code[0]))]

        self.cache.get_or_compute("a", compute)
        self.cache.get_or_compute("b", compute)
        self.cache.get_or_compute("c", compute)
        self.cache.get_or_compute("d", compute)  # triggers eviction of 'a'
        assert self.cache.get_or_compute("a", compute) == compute("a")
        # Now 'a' was recomputed
        assert self.cache.misses >= 2

    def test_hit_rate(self) -> None:
        """hit_rate = hits / (hits + misses)."""
        def compute(code: str) -> list[float]:
            return [0.0]

        self.cache.get_or_compute("x", compute)  # miss
        self.cache.get_or_compute("x", compute)  # hit
        assert self.cache.hit_rate == 0.5

    def test_clear(self) -> None:
        """clear() resets all counters and cache."""
        def compute(code: str) -> list[float]:
            return [0.0]

        self.cache.get_or_compute("x", compute)
        self.cache.clear()
        assert self.cache.hits == 0
        assert self.cache.misses == 0


class TestTokenCache:
    """Tests for the TokenCache class."""

    def setup_method(self) -> None:
        self.cache = TokenCache(maxsize=5)

    def test_compute_and_reuse(self) -> None:
        """Same code reuses cached tokens."""
        calls = [0]
        result = self.cache.get_or_compute("code here", lambda c: (calls.__setitem__(0, calls[0] + 1), ["tok1", "tok2"]))
        assert len(result) == 2
        assert calls[0] == 1

        result2 = self.cache.get_or_compute("code here", lambda c: (calls.__setitem__(0, calls[0] + 1), []))
        assert result2 == result
        assert calls[0] == 1


class TestGlobalCacheAccess:
    """Tests for global cache singleton accessors."""

    def teardown_method(self) -> None:
        invalidate_all_caches()

    def test_get_embedding_cache(self) -> None:
        """get_embedding_cache returns singleton."""
        c1 = get_embedding_cache()
        c2 = get_embedding_cache()
        assert c1 is c2

    def test_get_token_cache(self) -> None:
        """get_token_cache returns singleton."""
        c1 = get_token_cache()
        c2 = get_token_cache()
        assert c1 is c2

    def test_invalidate_all(self) -> None:
        """invalidate_all_caches clears both global caches."""
        ec = get_embedding_cache()
        tc = get_token_cache()
        ec.get_or_compute("test", lambda c: [1.0])
        tc.get_or_compute("test", lambda c: ["tok"])
        assert ec.hits + ec.misses > 0
        invalidate_all_caches()
        # After clear, counters reset
        assert ec.hits == 0
        assert ec.misses == 0
