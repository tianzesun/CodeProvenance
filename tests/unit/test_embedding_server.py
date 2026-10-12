"""Unit tests for embedding-server device selection (no model downloads)."""

import importlib
import sys
import types


def _load_with_fake_st(monkeypatch, device_env):
    """Import the server with a stubbed sentence_transformers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        device_env: Value for EMBEDDING_DEVICE, or None to leave it unset.

    Returns:
        A dict capturing the model name and device the loader requested.
    """
    captured: dict = {}

    class FakeSentenceTransformer:
        """Stand-in that records constructor args instead of downloading."""

        def __init__(self, model, device="cpu"):
            captured["model"] = model
            captured["device"] = device

        def encode(self, *args, **kwargs):
            return [[0.0]]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    if device_env is None:
        monkeypatch.delenv("EMBEDDING_DEVICE", raising=False)
    else:
        monkeypatch.setenv("EMBEDDING_DEVICE", device_env)
    from src.backend.services import embedding_server

    importlib.reload(embedding_server)
    embedding_server.embedding_model = None
    embedding_server._load_model_sync()
    embedding_server.embedding_model = None
    return captured


class TestEmbeddingDevice:
    """EMBEDDING_DEVICE selects the torch device without code changes."""

    def test_defaults_to_cpu(self, monkeypatch):
        """Test that an unset variable preserves CPU behavior."""
        captured = _load_with_fake_st(monkeypatch, None)
        assert captured["device"] == "cpu"

    def test_cuda_is_honored(self, monkeypatch):
        """Test that the GPU holder's EMBEDDING_DEVICE=cuda reaches torch."""
        captured = _load_with_fake_st(monkeypatch, "cuda")
        assert captured["device"] == "cuda"

    def test_blank_falls_back_to_cpu(self, monkeypatch):
        """Test that an empty value does not produce an invalid device."""
        captured = _load_with_fake_st(monkeypatch, "   ")
        assert captured["device"] == "cpu"
