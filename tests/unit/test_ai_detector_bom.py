"""A UTF-8 byte-order mark must not change the AI-detection result."""

from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

STUDENT_CODE = (
    "def average(marks):\n"
    "    total = 0\n"
    "    for m in marks:\n"
    "        total = total + m\n"
    "    return total / len(marks)\n"
    "\n"
    "marks = [int(x) for x in input().split()]\n"
    "print('average', average(marks))\n"
)


def test_leading_bom_does_not_change_the_score() -> None:
    """Files saved by Windows editors often start with a BOM; the score must match."""
    detector = AIDetectionOrchestrator()
    plain = detector.analyze(STUDENT_CODE)
    with_bom = detector.analyze("﻿" + STUDENT_CODE)
    assert with_bom["ai_probability"] == plain["ai_probability"]
    assert with_bom["flagged_lines"] == plain["flagged_lines"]
