"""Tests for legacy backend import compatibility."""

import importlib


def test_legacy_backend_namespace_resolves_main_module() -> None:
    """Legacy ``src.backend.backend`` imports should resolve to active modules."""
    module = importlib.import_module("src.backend.backend.main")

    assert module.app.title == "IntegrityDesk"
