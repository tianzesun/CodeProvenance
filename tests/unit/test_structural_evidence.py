"""Tests for professor-readable AST structural evidence."""

from src.backend.engines.similarity.structural_evidence import (
    compare_structural_evidence,
    structural_evidence_features,
)


def test_structural_evidence_detects_renamed_recursive_structure() -> None:
    """Renamed variables should still yield structural evidence."""
    left = """
def score(node):
    if node is None:
        return 0
    left_total = score(node.left)
    right_total = score(node.right)
    if left_total > right_total:
        return left_total
    return right_total
"""
    right = """
def compute(current):
    if current is None:
        return 0
    first = compute(current.left)
    second = compute(current.right)
    if first > second:
        return first
    return second
"""

    evidence = compare_structural_evidence(left, right)

    assert evidence.same_function_decomposition is True
    assert evidence.same_branch_order is True
    assert evidence.same_helper_function_pattern is True
    assert "same branch order" in evidence.evidence


def test_structural_evidence_exports_ranker_features() -> None:
    """Evidence booleans should convert into numeric feature payloads."""
    evidence = compare_structural_evidence(
        "def a(x):\n    if x:\n        return len(x)\n    return 0\n",
        "def b(y):\n    if y:\n        return len(y)\n    return 0\n",
    )

    features = structural_evidence_features(evidence)

    assert features["same_function_decomposition"] == 1.0
    assert features["same_branch_order"] == 0.0
    assert features["same_helper_function_pattern"] == 0.0
