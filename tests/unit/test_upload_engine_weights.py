"""Unit tests for upload engine-weight resolution.

These guard two behaviors that previously caused the Plagiarism Checker's
engine toggles to be silently ignored and scores to be overstated:

1. Assignment-mode preset weights must still honor the engine on/off toggles
   submitted from the upload form.
2. Alias keys that resolve to the same underlying fusion engine must be summed
   (``token``/``fingerprint``, ``semantic``/``embedding``) rather than having
   one silently dropped.
"""

import pytest

from src.backend.api import server


def test_build_fusion_weights_sums_token_and_fingerprint() -> None:
    """token and fingerprint both feed the token-level fusion engine."""
    weights = server._build_fusion_weights({"token": 0.18, "fingerprint": 0.08})
    assert weights["fingerprint"] == pytest.approx(0.26)


def test_build_fusion_weights_sums_semantic_and_embedding() -> None:
    """semantic and embedding both feed the semantic fusion engine."""
    weights = server._build_fusion_weights({"semantic": 0.05, "embedding": 0.01})
    assert weights["embedding"] == pytest.approx(0.06)


def test_build_fusion_weights_missing_aliases_default_to_zero() -> None:
    """Absent alias keys contribute zero instead of raising or emitting NaN."""
    weights = server._build_fusion_weights({"ast": 0.3})
    assert weights["fingerprint"] == 0.0
    assert weights["embedding"] == 0.0
    assert weights["ast"] == 0.3


def test_apply_selection_zeros_deselected_engines() -> None:
    """Engines the user did not select are disabled in the returned weights."""
    base = {key: 1.0 for key in server.UPLOAD_ENGINE_KEYS}
    out = server._apply_upload_engine_selection(dict(base), ["token", "ast"])
    assert out["token"] == 1.0
    assert out["ast"] == 1.0
    for key in server.UPLOAD_ENGINE_KEYS:
        if key in ("token", "ast"):
            continue
        assert out[key] == 0.0


def test_apply_selection_zeros_aliases_in_mode_weights() -> None:
    """Deselecting token/embedding also disables their mode dict aliases."""
    mode_weights = {
        **{key: 1.0 for key in server.UPLOAD_ENGINE_KEYS},
        "fingerprint": 1.0,
        "semantic": 1.0,
    }
    out = server._apply_upload_engine_selection(dict(mode_weights), ["ast", "gst"])
    assert out["token"] == 0.0
    assert out["fingerprint"] == 0.0
    assert out["embedding"] == 0.0
    assert out["semantic"] == 0.0
    assert out["ast"] == 1.0
    assert out["gst"] == 1.0


def test_apply_selection_keeps_mode_only_signals() -> None:
    """Mode-only signals (e.g. tree_kernel) are not zeroed by the filter."""
    base = {key: 1.0 for key in server.UPLOAD_ENGINE_KEYS}
    base["tree_kernel"] = 0.5
    out = server._apply_upload_engine_selection(dict(base), ["token"])
    assert out["tree_kernel"] == 0.5


def test_apply_selection_noop_when_no_upload_engine_selected() -> None:
    """A selection with no upload engine keys leaves weights unchanged."""
    base = {"tree_kernel": 0.5}
    out = server._apply_upload_engine_selection(dict(base), ["tree_kernel"])
    assert out == base
