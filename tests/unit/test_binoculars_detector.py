"""Tests for BinocularsDetector (zero-shot AI code detector)."""

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
        mock_bino.compute_score.return_value = -0.65
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
        mock_bino.compute_score.return_value = 0.72
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
