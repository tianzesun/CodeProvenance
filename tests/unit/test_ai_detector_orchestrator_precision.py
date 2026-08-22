"""Regression tests for the AI detection orchestrator accuracy fixes.

These guard against the specific failures found while tuning the detector:
- generic-identifier fingerprints (result/data/value) must not cause false
  positives on human code with docstrings;
- LLM-style descriptive comments must be detected (previous regex was too
  fragile to match hyphenated words / single-letter sentence starts);
- heuristic-only fusion must separate human from AI samples;
- the AIDetectionLayer must not fabricate near-constant scores when the
  learned models are unavailable.
"""

from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator
from src.backend.engines.ai.transformer_detector import (
    AIDetectionLayer,
    ZeroShotAIDetector,
)


HUMAN_TERSE = (
    "def grade(s):\n"
    "    if s >= 90:\n"
    "        return 'A'\n"
    "    if s >= 80:\n"
    "        return 'B'\n"
    "    return 'C'\n"
    "\n"
    "def main():\n"
    "    marks = [91, 84, 62, 78]\n"
    "    for m in marks:\n"
    "        print(grade(m))\n"
    "\n"
    "main()\n"
)

HUMAN_WITH_DOCSTRINGS = (
    "def sort_array(values):\n"
    '    """Sort values in place and return the sorted list."""\n'
    "    values.sort()\n"
    "    return values\n"
    "\n"
    "def average(values):\n"
    '    """Return the mean of the provided values."""\n'
    "    return sum(values) / len(values) if values else 0\n"
    "\n"
    "result = average(sort_array([3, 1, 2]))\n"
    "print(result)\n"
)

AI_CANONICAL = (
    "from collections import defaultdict\n"
    "from typing import Dict, List\n"
    "\n"
    "def classify_scores(scores: List[float]) -> Dict[str, int]:\n"
    '    """Classify a list of scores into grade buckets.\n'
    "\n"
    "    Args:\n"
    "        scores: A list of numeric percentage scores.\n"
    "\n"
    "    Returns:\n"
    "        A dictionary mapping each grade to its count.\n"
    '    """\n'
    "    grades = defaultdict(int)\n"
    "    for score in scores:\n"
    "        if score >= 90:\n"
    '            grades["A"] += 1\n'
    "        elif score >= 80:\n"
    '            grades["B"] += 1\n'
    "        else:\n"
    '            grades["C"] += 1\n'
    "    return dict(grades)\n"
    "\n"
    "def main() -> None:\n"
    '    """Print the grade distribution for a sample dataset."""\n'
    "    data = [88.0, 92.0, 61.0, 77.0]\n"
    "    result = classify_scores(data)\n"
    "    print(result)\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    main()\n"
)

AI_WITH_COMMENTS = (
    "def is_palindrome(s):\n"
    "    # Convert string to lowercase and strip non-alphanumeric characters\n"
    "    cleaned = ''.join(ch for ch in s.lower() if ch.isalnum())\n"
    "    # A string is a palindrome if it equals its reverse\n"
    "    return cleaned == cleaned[::-1]\n"
    "\n"
    "def longest_substring(s):\n"
    '    """Return the length of the longest substring without repeating characters."""\n'
    "    char_map = {}\n"
    "    left = 0\n"
    "    longest = 0\n"
    "    for right, char in enumerate(s):\n"
    "        if char in char_map and char_map[char] >= left:\n"
    "            left = char_map[char] + 1\n"
    "        char_map[char] = right\n"
    "        longest = max(longest, right - left + 1)\n"
    "    return longest\n"
)


class TestOrchestratorSeparation:
    """Human and AI samples must separate around the decision thresholds.

    Medium risk starts at 0.4; high risk at 0.7.
    """

    def setup_method(self) -> None:
        self.detector = AIDetectionOrchestrator()

    def test_human_terse_scores_low(self) -> None:
        result = self.detector.analyze(HUMAN_TERSE)
        assert result["ai_probability"] < 0.3

    def test_human_with_docstrings_stays_below_medium_risk(self) -> None:
        # Regression: bare generic identifiers previously inflated the pattern
        # signal, pushing this human sample to ~0.45.
        result = self.detector.analyze(HUMAN_WITH_DOCSTRINGS)
        assert result["ai_probability"] < 0.4

    def test_ai_canonical_scores_high(self) -> None:
        result = self.detector.analyze(AI_CANONICAL)
        assert result["ai_probability"] >= 0.6

    def test_ai_with_comments_detected(self) -> None:
        # Regression: the descriptive English comment fingerprint regex was too
        # fragile to match hyphenated words or single-letter sentence starts.
        result = self.detector.analyze(AI_WITH_COMMENTS)
        assert result["ai_probability"] >= 0.6
        assert result["signals"].get("pattern_library", 0.0) > 0.3


class TestAIDetectionLayerHonesty:
    """The layer must delegate to the real engine, not fabricate scores."""

    def test_human_code_not_flagged_constant(self) -> None:
        layer = AIDetectionLayer()
        result = layer.analyze(HUMAN_TERSE)
        assert 0.0 < result["ai_probability"] < 0.5
        assert result["decision"] == "likely_human"

    def test_zero_shot_delegates_to_engine(self) -> None:
        detector = ZeroShotAIDetector()
        human_score = detector.predict_zero_shot(HUMAN_TERSE)
        ai_score = detector.predict_zero_shot(AI_CANONICAL)
        assert ai_score > human_score

    def test_orchestrator_reports_detection_method(self) -> None:
        result = AIDetectionOrchestrator().analyze(AI_CANONICAL, language="python")
        assert result["method"] in ("binoculars", "heuristic", "ml")
        if result["method"] == "heuristic":
            assert "trained model" in result["model"]
        elif result["method"] == "ml":
            assert "safe-blend" in result["model"]
