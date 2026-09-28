"""Tests for BinocularsDetector (zero-shot AI code detector).

The mocked ``compute_score`` values below are drawn from Binoculars' real
score space: a positive ``perplexity / cross_entropy`` ratio (roughly
0.3-2.0) where anything below ~0.854 is AI-generated. Earlier fixtures used
values like ``-0.65`` that the real implementation never produces, which hid a
broken probability mapping.
"""

import os
from unittest.mock import patch, MagicMock

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
        mock_bino.predict.return_value = "MOST_LIKELY_AI"
        detector._bino = mock_bino
        detector._available = True

        long_code = (
            "def hello_world():\n    print('This is a longer example for testing')\n    return 42\n"
            * 3
        )
        result = detector.analyze(long_code, language="python")

        assert result["available"] is True
        assert result["label"] == "MOST_LIKELY_AI"
        assert 0.8 < result["ai_probability"] <= 1.0
        assert result["confidence"] >= 0.6

    def test_human_like_score(self):
        detector = BinocularsDetector()

        mock_bino = MagicMock()
        # A genuinely human-like score sits ABOVE the accuracy threshold
        # (0.9015). The previous fixture used 0.72, which Binoculars actually
        # classifies as AI-generated, so it asserted the wrong outcome.
        mock_bino.compute_score.return_value = 0.95
        mock_bino.predict.return_value = "MOST_LIKELY_HUMAN"
        detector._bino = mock_bino
        detector._available = True

        long_code = (
            "def process_data(items):\n    result = []\n    for item in items:\n        result.append(item * 2)\n    return result\n"
            * 3
        )
        result = detector.analyze(long_code, language="python")

        assert result["available"] is True
        assert result["ai_probability"] < 0.2

    def test_ai_score_reaches_the_medium_risk_band(self):
        """A confident-AI score must be able to cross the 0.40 medium band.

        Regression: the previous ``(1.0 - raw) / 2.0`` mapping produced 0.125
        for a confidently-AI 0.75, so Binoculars could never flag anything.
        """
        detector = BinocularsDetector()
        mock_bino = MagicMock()
        mock_bino.compute_score.return_value = 0.75
        mock_bino.predict.return_value = "MOST_LIKELY_AI"
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
