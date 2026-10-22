"""Tests for the embedding prewarm used by the GPU benchmark runs."""

from __future__ import annotations

import numpy as np
import pytest

from src.backend.engines.similarity.unixcoder_similarity import UniXcoderSimilarity


class _RecordingStore:
    """Disk-cache stand-in that records what is already stored."""

    def __init__(self, cached: set[str]) -> None:
        self.cached = set(cached)

    def key(self, text: str) -> str:
        """Return a stable key for a text."""
        return f"key:{text}"

    def get(self, text: str):
        """Return a vector only for texts marked as cached."""
        if text in self.cached:
            return np.zeros(4, dtype=np.float32)
        return None

    def put(self, text: str, vector) -> None:
        """Record a written vector."""
        self.cached.add(text)


def _engine(cached: set[str]) -> UniXcoderSimilarity:
    """Build an engine without loading the transformer."""
    engine = UniXcoderSimilarity.__new__(UniXcoderSimilarity)
    engine._store = _RecordingStore(cached)
    engine._model = None
    engine._embed_calls = []  # type: ignore[attr-defined]

    def fake_embed(texts):
        engine._embed_calls.append(list(texts))  # type: ignore[attr-defined]
        return np.zeros((len(texts), 4), dtype=np.float32)

    engine._embed_texts = fake_embed  # type: ignore[method-assign]
    engine._load_model = lambda: None  # type: ignore[method-assign]
    return engine


def test_warm_embeddings_computes_only_uncached_texts() -> None:
    """A cached submission must not be sent through the model again."""
    engine = _engine({"a.py"})
    computed = engine.warm_embeddings(["a.py", "b.py", "b.py", "  c.py "])
    assert computed == 2
    assert engine._embed_calls == [["a.py", "b.py", "c.py"]]  # type: ignore[attr-defined]


def test_warm_embeddings_is_a_noop_when_everything_is_cached() -> None:
    """A resumed run must not touch the device at all."""
    engine = _engine({"a.py", "b.py"})
    assert engine.warm_embeddings(["a.py", "b.py"]) == 0
    assert engine._embed_calls == []  # type: ignore[attr-defined]


def test_warm_embeddings_skips_blank_texts() -> None:
    """Blank sources never reach the model."""
    engine = _engine(set())
    assert engine.warm_embeddings(["", "   ", "\n"]) == 0
    assert engine._embed_calls == []  # type: ignore[attr-defined]


def test_prewarm_skips_short_texts_that_use_the_token_fallback(monkeypatch) -> None:
    """Texts under five tokens are compared by tokens, never embedded."""
    from src.backend.engines.features import feature_extractor as module

    monkeypatch.setenv("EMBEDDING_RUNTIME", "local_unixcoder")
    summary = module.prewarm_local_embeddings(["a = 1", "def f():\n    return 1"])
    assert summary["requested"] == 0
    assert summary["computed"] == 0


def test_prewarm_reports_a_failure_without_raising(monkeypatch) -> None:
    """A missing model must degrade to the normal per-pair path, not crash."""
    from src.backend.engines.features import feature_extractor as module

    monkeypatch.setenv("EMBEDDING_RUNTIME", "local_unixcoder")

    class Broken:
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("transformers not installed")

    monkeypatch.setattr(
        "src.backend.engines.similarity.unixcoder_similarity.UniXcoderSimilarity",
        Broken,
    )
    summary = module.prewarm_local_embeddings(["def f():\n    x = 1\n    return x"])
    assert summary["enabled"] is True
    assert summary["computed"] == 0
    assert "ImportError" in (summary["error"] or "")


def test_prewarm_is_skipped_when_embeddings_are_disabled(monkeypatch) -> None:
    """``EMBEDDING_RUNTIME=none`` must not load a model to warm a cache."""
    from src.backend.engines.features import feature_extractor as module

    monkeypatch.setenv("EMBEDDING_RUNTIME", "none")
    summary = module.prewarm_local_embeddings(["def f():\n    x = 1\n    return x"])
    assert summary["enabled"] is False
    assert summary["computed"] == 0
    assert summary["error"] is None


@pytest.mark.parametrize("runtime", ["local", "local_unixcoder", "unixcoder"])
def test_prewarm_treats_every_local_runtime_alias_as_local(
    monkeypatch, runtime: str
) -> None:
    """All three aliases the extractor accepts must enable the warm-up."""
    from src.backend.engines.features import feature_extractor as module

    monkeypatch.setenv("EMBEDDING_RUNTIME", runtime)
    assert module._embedding_runtime_name() == runtime


@pytest.mark.parametrize("command", ["fusion-train-learned", "engine-eval"])
def test_cli_documents_the_prewarm_opt_out(command: str, capsys) -> None:
    """Every scoring command must expose the same escape hatch."""
    import sys

    from src.backend.benchmark import __main__ as cli

    previous = sys.argv
    sys.argv = ["benchmark", command, "--help"]
    try:
        with pytest.raises(SystemExit):
            cli.main()
    finally:
        sys.argv = previous
    assert "--no-prewarm-embeddings" in capsys.readouterr().out
