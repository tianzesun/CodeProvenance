"""Tests for BinocularsDetector (zero-shot AI code detector).

The mocked ``compute_score`` values below are drawn from Binoculars' real
score space: a positive ``perplexity / cross_entropy`` ratio (roughly
0.3-2.0) where anything below ~0.854 is AI-generated. Earlier fixtures used
values like ``-0.65`` that the real implementation never produces, which hid a
broken probability mapping.
"""

import os
from unittest.mock import MagicMock, patch

from src.backend.engines.ai.binoculars_detector import BinocularsDetector


class TestBinocularsDetector:
    def test_short_code_returns_uncertain(self):
        detector = BinocularsDetector()
        result = detector.analyze("x=1")
        assert result["ai_probability"] == 0.5
        assert result["label"] == "UNCERTAIN"
        assert result["available"] is False

    def test_successful_analysis(self):
        detector = BinocularsDetector()

        # Manually inject a fake binoculars instance (simulates successful load)
        mock_bino = MagicMock()
        # 0.60 is below the low-FPR threshold (0.8536), i.e. clearly AI.
        mock_bino.compute_score.return_value = 0.60
        detector._bino = mock_bino
        detector._available = True

        long_code = (
            "def hello_world():\n    print('This is a longer example for testing')\n    return 42\n"
            * 3
        )
        result = detector.analyze(long_code, language="python")

        assert result["available"] is True
        assert result["label"] == "Most likely AI-generated"
        assert 0.8 < result["ai_probability"] <= 1.0
        assert result["confidence"] >= 0.6
        # The label must be derived from the score: predict() re-runs the full
        # double-model inference and must never be called.
        mock_bino.predict.assert_not_called()
        mock_bino.compute_score.assert_called_once()

    def test_label_follows_the_loaded_instance_threshold(self):
        """Label banding mirrors ``np.where(score < threshold, AI, human)``."""
        detector = BinocularsDetector()
        mock_bino = MagicMock()
        mock_bino.threshold = 0.9
        mock_bino.compute_score.return_value = 0.87
        detector._bino = mock_bino
        detector._available = True

        code = "def f(x):\n    return x * 2\n" * 8
        assert detector.analyze(code)["label"] == "Most likely AI-generated"

        mock_bino.compute_score.return_value = 0.92
        assert detector.analyze(code)["label"] == "Most likely human-generated"
        mock_bino.predict.assert_not_called()

    def test_human_like_score(self):
        detector = BinocularsDetector()

        mock_bino = MagicMock()
        # A genuinely human-like score sits ABOVE the accuracy threshold
        # (0.9015). The previous fixture used 0.72, which Binoculars actually
        # classifies as AI-generated, so it asserted the wrong outcome.
        mock_bino.compute_score.return_value = 0.95
        detector._bino = mock_bino
        detector._available = True

        long_code = (
            "def process_data(items):\n    result = []\n    for item in items:\n        result.append(item * 2)\n    return result\n"
            * 3
        )
        result = detector.analyze(long_code, language="python")

        assert result["available"] is True
        assert result["ai_probability"] < 0.2
        assert result["label"] == "Most likely human-generated"

    def test_ai_score_reaches_the_medium_risk_band(self):
        """A confident-AI score must be able to cross the 0.40 medium band.

        Regression: the previous ``(1.0 - raw) / 2.0`` mapping produced 0.125
        for a confidently-AI 0.75, so Binoculars could never flag anything.
        """
        detector = BinocularsDetector()
        mock_bino = MagicMock()
        mock_bino.compute_score.return_value = 0.75
        detector._bino = mock_bino
        detector._available = True

        code = "def f(x):\n    return x * 2\n" * 8
        result = detector.analyze(code, language="python")

        assert result["ai_probability"] >= 0.40

    @patch("sys.modules", new={"binoculars": None})
    def test_graceful_degradation_when_package_missing(self):
        detector = BinocularsDetector()
        result = detector.analyze(
            "def foo():\n    print('This is a longer example for testing')\n    return 42\n"
            * 3,
            language="python",
        )

        assert result["available"] is False
        assert result["ai_probability"] == 0.5

    def test_is_available_returns_false_when_not_loaded(self):
        detector = BinocularsDetector()
        # Force failure path
        with patch("sys.modules", {"binoculars": None}):
            assert detector.is_available() is False


def test_disabled_by_env_does_not_load_models() -> None:
    """``BINOCULARS_ENABLED=0`` forces the fallback without importing the package.

    The test suite relies on this: without it every AI-detection test would
    load two ~500MB checkpoints and the run would take hours.
    """
    from src.backend.engines.ai import binoculars_detector as module

    previous = os.environ.get("BINOCULARS_ENABLED")
    os.environ["BINOCULARS_ENABLED"] = "0"
    try:
        detector = module.BinocularsDetector()
        assert detector._load() is False
        assert detector._bino is None
        assert detector.is_available() is False
    finally:
        if previous is None:
            os.environ.pop("BINOCULARS_ENABLED", None)
        else:
            os.environ["BINOCULARS_ENABLED"] = previous


def test_configured_pair_defaults_to_a_cpu_sized_model() -> None:
    """The default pair must not be the multi-GB Falcon checkpoints.

    Falcon-7B x2 is ~28GB and cannot run without a GPU, so it is only reachable
    by explicitly overriding the environment.
    """
    from src.backend.engines.ai import binoculars_detector as module

    detector = module.BinocularsDetector()
    assert "falcon" not in detector.model.lower()
    assert "falcon" not in detector.performer.lower()
    # Observer is the base model, performer the instruction-tuned sibling.
    assert detector.model != detector.performer


def test_model_pair_is_configurable_via_environment() -> None:
    """Operators can point the detector at a different pair without a code change."""
    from src.backend.engines.ai import binoculars_detector as module

    previous = (
        os.environ.get("BINOCULARS_OBSERVER_MODEL"),
        os.environ.get("BINOCULARS_PERFORMER_MODEL"),
    )
    os.environ["BINOCULARS_OBSERVER_MODEL"] = "org/observer"
    os.environ["BINOCULARS_PERFORMER_MODEL"] = "org/performer"
    try:
        detector = module.BinocularsDetector()
        assert detector.model == "org/observer"
        assert detector.performer == "org/performer"
    finally:
        for key, value in zip(
            ("BINOCULARS_OBSERVER_MODEL", "BINOCULARS_PERFORMER_MODEL"), previous
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_loaded_pair_is_cached_across_detectors() -> None:
    """One process loads the model pair once; later detectors reuse it.

    Regression: every job constructed a fresh detector, so each AI run
    reloaded two ~0.5B checkpoints — jobs sat at "processing" for minutes
    on tiny files. The pair must be shared, not reloaded per instance.
    """
    import sys
    import types

    from src.backend.engines.ai import binoculars_detector as module

    construct_calls = {"count": 0}

    class FakeBinoculars:
        """Stands in for the real package; records constructor calls."""

        def __init__(self, **kwargs):
            construct_calls["count"] += 1
            self.threshold = module.BINOCULARS_FPR_THRESHOLD

        def compute_score(self, code):
            return 0.60

    fake_package = types.ModuleType("binoculars")
    fake_package.Binoculars = FakeBinoculars

    previous_enabled = os.environ.get("BINOCULARS_ENABLED")
    saved_cache = dict(module._BINOCULARS_CACHE)
    os.environ["BINOCULARS_ENABLED"] = "1"
    module._BINOCULARS_CACHE.clear()
    try:
        with patch.dict(sys.modules, {"binoculars": fake_package}):
            first = module.BinocularsDetector()
            second = module.BinocularsDetector()
            assert first._load() is True
            assert second._load() is True
            assert first._bino is second._bino
            assert construct_calls["count"] == 1
    finally:
        module._BINOCULARS_CACHE.clear()
        module._BINOCULARS_CACHE.update(saved_cache)
        if previous_enabled is None:
            os.environ.pop("BINOCULARS_ENABLED", None)
        else:
            os.environ["BINOCULARS_ENABLED"] = previous_enabled


def test_bf16_env_override_beats_cpu_detection() -> None:
    """BINOCULARS_BF16 forces either path, capable CPU or not."""
    from src.backend.engines.ai import binoculars_detector as module

    forced_off = patch.dict(os.environ, {"BINOCULARS_BF16": "0"})
    capable = patch.object(module, "_cpu_has_native_bf16", return_value=True)
    with forced_off, capable:
        assert module._bfloat16_enabled() is False

    forced_on = patch.dict(os.environ, {"BINOCULARS_BF16": "1"})
    incapable = patch.object(module, "_cpu_has_native_bf16", return_value=False)
    with forced_on, incapable:
        assert module._bfloat16_enabled() is True


def test_bf16_defaults_to_cpu_capability() -> None:
    """Without env, bf16 follows native support — emulated bf16 is unusable.

    Regression: the old default was always-on, and torch's emulated bf16 ran
    GEMM ~159x slower on an AVX2-only host, stranding AI jobs for an hour.
    """
    from src.backend.engines.ai import binoculars_detector as module

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BINOCULARS_BF16", None)
        with patch.object(module, "_cpu_has_native_bf16", return_value=True):
            assert module._bfloat16_enabled() is True
        with patch.object(module, "_cpu_has_native_bf16", return_value=False):
            assert module._bfloat16_enabled() is False


def test_cpu_bf16_probe_is_a_bool() -> None:
    """The /proc probe answers with a plain bool (and caches itself)."""
    from src.backend.engines.ai import binoculars_detector as module

    previous = module._NATIVE_BF16
    module._NATIVE_BF16 = None
    try:
        assert isinstance(module._cpu_has_native_bf16(), bool)
        # Second call uses the cached value without touching /proc again.
        module._NATIVE_BF16 = True
        assert module._cpu_has_native_bf16() is True
    finally:
        module._NATIVE_BF16 = previous
