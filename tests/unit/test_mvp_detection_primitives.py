"""Tests for the five MVP detection primitives."""

from src.backend.engines.mvp import (
    ASTSubtreeHasher,
    CodeNormalizer,
    PrecisionAt20Ranker,
    MVPDetectionPipeline,
    SameBugDetector,
    StarterCodeRemover,
)
from src.backend.engines.mvp.same_bug import RuntimeOutcome


def test_code_normalizer_removes_comments_and_normalizes_names_and_literals() -> None:
    """Normalization should hide superficial edits while preserving structure."""
    source = """
# student comment
def add_numbers(first, second):
    total = first + second + 42
    return total
"""

    normalized = CodeNormalizer().normalize(source)

    assert "student" not in normalized.normalized_code
    assert "add_numbers" not in normalized.normalized_code
    assert "first" not in normalized.normalized_code
    assert "LIT_NUM" in normalized.tokens
    assert normalized.identifier_count > 0


def test_starter_code_remover_filters_template_lines() -> None:
    """Starter-code lines should be removed before pair comparison."""
    starter = """
def read_input():
    return input().strip()
"""
    submission = """
def read_input():
    return input().strip()

def solve(values):
    return sum(values)
"""

    result = StarterCodeRemover([starter]).remove(submission)

    assert "read_input" not in result.filtered_source
    assert "solve" in result.filtered_source
    assert result.removed_line_count == 2
    assert result.starter_overlap > 0


def test_ast_subtree_hashing_is_identifier_and_literal_resistant() -> None:
    """AST subtree hashing should stay high under renames and literal edits."""
    left = """
def tree_score(node):
    if node is None:
        return 0
    return tree_score(node.left) + 1
"""
    right = """
def compute(current):
    if current is None:
        return 99
    return compute(current.left) + 2
"""

    similarity = ASTSubtreeHasher().similarity(left, right)

    assert similarity >= 0.55


def test_same_bug_detector_boosts_shared_wrong_answer() -> None:
    """Two submissions with the same wrong edge-case output should be strong evidence."""
    outcomes_a = [
        RuntimeOutcome("empty_array", output="1", expected_output="0"),
        RuntimeOutcome("single", output="5", expected_output="5"),
        RuntimeOutcome("bad_type", exception_type="ValueError"),
    ]
    outcomes_b = [
        RuntimeOutcome("empty_array", output="1", expected_output="0"),
        RuntimeOutcome("single", output="5", expected_output="5"),
        RuntimeOutcome("bad_type", exception_type="ValueError"),
    ]

    finding = SameBugDetector().compare(outcomes_a, outcomes_b)

    assert finding.score >= 0.6
    assert finding.same_wrong_outputs == ["empty_array"]
    assert finding.same_exceptions == ["bad_type"]
    assert "same wrong outputs" in finding.evidence


def test_precision_at_20_ranker_prioritizes_same_bug_and_discounts_starter_code() -> (
    None
):
    """Precision@20 ranking should put worth-reviewing cases ahead of hard negatives."""
    cases = [
        {
            "case_id": "starter_false_positive",
            "label": 0,
            "category": "starter_code_false_positive",
            "base_score": 0.95,
            "features": {
                "fingerprint": 0.95,
                "ast": 0.9,
                "starter_code_overlap": 0.9,
            },
        },
        {
            "case_id": "same_bug_case",
            "label": 1,
            "category": "same_bug",
            "features": {
                "runtime_bug_similarity": 0.95,
                "edge_case_behavior_similarity": 0.9,
            },
        },
    ]

    ranker = PrecisionAt20Ranker()
    ranked = ranker.rank(cases)

    assert ranked[0].case_id == "same_bug_case"
    assert ranker.precision_at_20(cases) == 0.5


def test_mvp_detection_pipeline_runs_all_five_improvements() -> None:
    """Pipeline should expose starter, token, AST, same-bug, and ranker outputs."""
    starter = "def read_input():\n    return input().strip()\n"
    source_a = (
        starter
        + "\ndef solve(values):\n    if values == []:\n        return 1\n    return sum(values)\n"
    )
    source_b = (
        starter
        + "\ndef answer(items):\n    if items == []:\n        return 1\n    return sum(items)\n"
    )
    outcomes_a = [RuntimeOutcome("empty", output="1", expected_output="0")]
    outcomes_b = [RuntimeOutcome("empty", output="1", expected_output="0")]

    result = MVPDetectionPipeline([starter]).analyze_pair(
        "pair_1",
        source_a,
        source_b,
        outcomes_a=outcomes_a,
        outcomes_b=outcomes_b,
        label=1,
        category="same_bug",
    )

    assert result.features["starter_code_overlap"] > 0
    assert result.features["fingerprint"] > 0
    assert result.features["ast"] > 0
    assert result.features["runtime_bug_similarity"] == 1.0
    assert result.ranked_case.review_priority >= 0.86
