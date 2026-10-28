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
