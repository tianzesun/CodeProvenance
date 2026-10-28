"""A full GPU must not switch the embedding signal to its token fallback."""

from __future__ import annotations

import pytest

transformers = pytest.importorskip("transformers")
torch = pytest.importorskip("torch")

from src.backend.engines.similarity.unixcoder_similarity import (
    UniXcoderSimilarity,
)


class _GpuFullModel:
    """Model stand-in whose move to CUDA fails like a GPU held by another service."""

    def __init__(self, error=None):
        self.moves: list[str] = []
        self.error = error

    def to(self, device):
        self.moves.append(device)
        if device == "cuda":
            raise self.error or torch.cuda.OutOfMemoryError("CUDA out of memory")
        return self

    def eval(self):
        return self


def _patch(monkeypatch, model):
    # Keep the fake vectors out of the shared Redis embedding cache.
    monkeypatch.setattr(
        "src.backend.infrastructure.cache.get_cache",
        lambda: type("NoCache", (), {"available": False})(),
    )
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda index: "Tesla T4")
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: object())
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", lambda *a, **k: model)


@pytest.mark.parametrize(
    "error",
    [
        torch.cuda.OutOfMemoryError("CUDA out of memory"),
        # What torch raises when even the CUDA context does not fit.
        RuntimeError("CUDA error: out of memory"),
    ],
)
def test_auto_device_falls_back_to_cpu(monkeypatch, tmp_path, error):
    model = _GpuFullModel(error)
    _patch(monkeypatch, model)

    engine = UniXcoderSimilarity(cache_dir=tmp_path)
    assert engine.device == "cuda"
    engine._load_model()

    assert engine._model is model
    assert engine.device == "cpu"
    assert model.moves == ["cuda", "cpu"]


def test_explicit_cuda_still_raises(monkeypatch, tmp_path):
    _patch(monkeypatch, _GpuFullModel())

    engine = UniXcoderSimilarity(device="cuda", cache_dir=tmp_path)
    with pytest.raises(torch.cuda.OutOfMemoryError):
        engine._load_model()
    assert engine._model is None


def test_other_cuda_errors_are_not_masked(monkeypatch, tmp_path):
    _patch(monkeypatch, _GpuFullModel(RuntimeError("CUDA error: illegal memory access")))

    engine = UniXcoderSimilarity(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="illegal memory access"):
        engine._load_model()


class _GpuFilledLaterModel:
    """Model that loaded on the GPU, then runs out of room when it is used."""

    def __init__(self):
        self.device = None

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        return self

    def __call__(self, **inputs):
        if self.device == "cuda":
            raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 20.00 MiB")
        hidden = torch.ones(len(inputs["input_ids"]), 3, 4)
        return type("Output", (), {"last_hidden_state": hidden})()


class _Tokens(dict):
    def to(self, device):
        return self


def test_gpu_filled_after_load_finishes_on_cpu(monkeypatch, tmp_path):
    model = _GpuFilledLaterModel()
    _patch(monkeypatch, model)
    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *a, **k: lambda batch, **kw: _Tokens(input_ids=[[0]] * len(batch)),
    )

    engine = UniXcoderSimilarity(cache_dir=tmp_path)
    vectors = engine._embed_texts(["def f(x): return x + 1", "def g(y): return y * 2"])

    assert vectors.shape == (2, 4)
    assert engine.device == "cpu"
    assert model.device == "cpu"
