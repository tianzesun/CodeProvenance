"""Pairs with no code on one side must not score as a match."""

from typing import Any

import pytest

from src.backend.application.services.batch_detection_service import (
    MIN_EVIDENCE_TOKENS,
    BatchDetectionService,
    _logic_flow_similarity,
)


class _ConfidentLearnedScorer:
    """Stands in for the learned model, which scores empty pairs ~0.97."""

    available = True

    def score(self, features: dict[str, Any]) -> float:
        return 0.97


@pytest.fixture(scope="module")
def service() -> BatchDetectionService:
    svc = BatchDetectionService(min_evidence_tokens=MIN_EVIDENCE_TOKENS)
    svc.learned_scorer = _ConfidentLearnedScorer()
    return svc


def _score(service: BatchDetectionService, code_a: str, code_b: str) -> float:
    features = service.extractor.extract(
        code_a, code_b, filename_a="a.py", filename_b="b.py"
    )
    logic_flow = _logic_flow_similarity(code_a, code_b)
    fused = service.fusion.fuse(features, logic_flow=logic_flow)
    return service._primary_score(features, logic_flow, fused, code_a, code_b)


@pytest.mark.parametrize(
    ("code_a", "code_b"),
    [
        ("", ""),
        ("   \n\n", "\t\n"),
        ("# hello\n", "// other\n"),
        ('"""Assignment 1."""\n', '"""Lab 2."""\n'),
        ("", "def double(n):\n    return n * 2\n"),
    ],
)
def test_pair_without_code_scores_zero(
    service: BatchDetectionService, code_a: str, code_b: str
) -> None:
    assert _score(service, code_a, code_b) == 0.0


LONG_ENOUGH = (
    "def mean(values):\n"
    "    if not values:\n"
    "        return 0.0\n"
    "    total = 0.0\n"
    "    for value in values:\n"
    "        total += value\n"
    "    return total / len(values)\n"
)


def test_pair_with_code_still_uses_learned_score(
    service: BatchDetectionService,
) -> None:
    assert _score(service, LONG_ENOUGH, LONG_ENOUGH) > 0.9


@pytest.mark.parametrize(
    ("code_a", "code_b"),
    [
        ("x = 1\n", "y = 2\n"),
        ("print('hi')\n", "print('bye')\n"),
        ("def solve():\n    pass\n", "def main():\n    pass\n"),
        ("x = 1\n", LONG_ENOUGH),
    ],
)
def test_too_little_code_is_held_at_review(
    service: BatchDetectionService, code_a: str, code_b: str
) -> None:
    """A few tokens normalise to the same shape; that is not a critical match."""
    assert 0.0 < _score(service, code_a, code_b) <= 0.5


def test_upload_order_does_not_change_scores() -> None:
    """Pair features depend on argument order, so pairs use sorted names."""
    small = "def total(xs):\n    return sum(xs)\n"
    large = (
        small
        + "\n\ndef mean(xs):\n    if not xs:\n        return 0\n"
        + "    return total(xs) / len(xs)\n"
    )
    other = "class Stack:\n    def __init__(self):\n        self.items = []\n"
    service = BatchDetectionService()

    def scores(submissions: dict[str, str]) -> dict[frozenset[str], float]:
        results = service.compare_all_pairs(submissions, use_parallel=False)
        return {frozenset((r.file_a, r.file_b)): r.score for r in results}

    forward = scores({"a.py": small, "b.py": large, "c.py": other})
    backward = scores({"c.py": other, "b.py": large, "a.py": small})
    assert forward.keys() == backward.keys()
    for pair, score in forward.items():
        assert backward[pair] == pytest.approx(score, abs=1e-6)


def test_starter_code_overlap_is_not_escalated(
    service: BatchDetectionService,
) -> None:
    """Identical untouched starter files stay at REVIEW, not a critical match."""
    starter = (
        "def load(path):\n    with open(path) as handle:\n"
        "        return handle.read().splitlines()\n\n\n"
        "def main():\n    rows = load('data.txt')\n    print(len(rows))\n"
    )
    features = service.extractor.extract(
        starter, starter, filename_a="a.py", filename_b="b.py"
    )
    features.starter_code_overlap = 1.0
    logic_flow = _logic_flow_similarity(starter, starter)
    fused = service.fusion.fuse(features, logic_flow=logic_flow)

    score = service._primary_score(features, logic_flow, fused, starter, starter)

    assert score <= 0.5
