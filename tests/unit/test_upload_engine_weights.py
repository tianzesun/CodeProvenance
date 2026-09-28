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


# ---------------------------------------------------------------------------
# Fusion weight mapping
#
# Regression: mode weight dicts name signals ``cfg``/``execution_cfg``, but the
# fusion engine reads ``graph``/``static_rules``. The mismatch meant the
# code-graph engine received 0.0 for *every* assignment mode, so the "CFG /
# execution focus" the UI advertises never influenced a score.
# ---------------------------------------------------------------------------


def test_cfg_alias_feeds_the_graph_engine() -> None:
    """``cfg`` is the mode-catalog name for the code-graph signal."""
    weights = server._build_fusion_weights({"cfg": 0.25})
    assert weights["graph"] == pytest.approx(0.25)


def test_execution_cfg_feeds_static_rules() -> None:
    """``execution_cfg`` is the behavioural signal grouped with static rules."""
    weights = server._build_fusion_weights({"execution_cfg": 0.30})
    assert weights["static_rules"] == pytest.approx(0.30)


def test_graph_and_cfg_aliases_are_summed() -> None:
    """Both spellings of the graph engine add together rather than overwrite."""
    weights = server._build_fusion_weights({"graph": 0.10, "cfg": 0.15})
    assert weights["graph"] == pytest.approx(0.25)


def test_mode_only_signals_reach_the_fusion_scorer() -> None:
    """Signals with no upload toggle are passed through, not dropped."""
    weights = server._build_fusion_weights(
        {"tree_kernel": 0.12, "web": 0.06, "ai_detection": 0.01}
    )
    assert weights["tree_kernel"] == pytest.approx(0.12)
    assert weights["web"] == pytest.approx(0.06)
    assert weights["ai_detection"] == pytest.approx(0.01)


def test_no_weighted_mode_starves_an_engine() -> None:
    """Every weighted mode must give every declared signal a non-zero weight.

    This is the invariant the old mapping broke: ``graph`` and ``static_rules``
    were 0.0 across all six modes.
    """
    from src.backend.engines.scoring.assignment_modes import get_assignment_modes

    # Mode-catalog key -> fusion key.
    aliases = {
        "token": "fingerprint",
        "fingerprint": "fingerprint",
        "winnowing": "winnowing",
        "gst": "string_tiling",
        "ast": "ast",
        "ngram": "ngram",
        "graph": "graph",
        "cfg": "graph",
        "semantic": "embedding",
        "embedding": "embedding",
        "static_rules": "static_rules",
        "execution_cfg": "static_rules",
        "tree_kernel": "tree_kernel",
        "web": "web",
        "ai_detection": "ai_detection",
    }

    checked = 0
    for mode_id, mode in get_assignment_modes().items():
        if not mode.weights:
            continue
        fusion = server._build_fusion_weights(dict(mode.weights))
        assert fusion, f"{mode_id} produced no fusion weights"
        for source_key, weight in mode.weights.items():
            if weight <= 0:
                continue
            target = aliases.get(source_key)
            assert target is not None, f"{mode_id}.{source_key} has no fusion mapping"
            assert fusion.get(target, 0.0) > 0, (
                f"{mode_id}: {source_key} -> {target} is zero, "
                f"so the signal cannot influence a score"
            )
        checked += 1
    assert checked >= 6, f"expected the six weighted modes, saw {checked}"


def test_empty_weights_still_return_empty_mapping() -> None:
    """All-zero input must keep returning {} (the scorer's 'nothing enabled')."""
    assert server._build_fusion_weights({}) == {}
    assert server._build_fusion_weights({"ast": 0.0, "cfg": 0.0}) == {}
