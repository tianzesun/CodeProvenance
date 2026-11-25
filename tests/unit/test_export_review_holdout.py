"""The review export writes labels only on real evidence, in the runner's layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.export_review_holdout import (
    PairReviewRow,
    build_class,
    label_pair,
    latest_reviews,
    output_problem,
    pseudonymise,
    write_class,
)
from src.backend.benchmark.runners.class_evaluation_runner import load_student_holdout


@pytest.mark.parametrize(
    ("disposition", "viva_a", "viva_b", "label"),
    [
        ("no_action", None, None, 0),
        ("no_action", "authorship_confirmed", None, 0),
        ("no_action", "breach_identified", None, None),
        ("no_action", None, "concerns_unresolved", None),
        ("formal_escalation", "breach_identified", None, 1),
        ("step_up_verification", None, "breach_identified", 1),
        ("formal_escalation", None, None, None),
        ("formal_escalation", "concerns_unresolved", None, None),
        ("conversation", None, None, None),
        ("note_on_file", "breach_identified", None, None),
        ("conversation", "authorship_confirmed", "authorship_confirmed", 0),
    ],
)
def test_label_pair_needs_a_verdict(
    disposition: str, viva_a: str | None, viva_b: str | None, label: int | None
) -> None:
    """Only a cleared review or a viva-backed escalation becomes a label."""
    assert label_pair(disposition, viva_a, viva_b)[0] == label


def test_pseudonymise_hides_names_and_keeps_extensions() -> None:
    """Student names never reach the export; the language extension does."""
    mapping = pseudonymise(["zoe_smith.py", "alex_lee.java", "README"])
    assert mapping == {
        "README": "submission001.txt",
        "alex_lee.java": "submission002.java",
        "zoe_smith.py": "submission003.py",
    }


def test_latest_reviews_merges_both_orderings() -> None:
    """A pair reviewed as (a, b) then (b, a) keeps only its newest decision."""
    rows = [("a.py", "b.py", "formal_escalation"), ("b.py", "a.py", "no_action")]
    assert latest_reviews(rows) == [PairReviewRow("b.py", "a.py", "no_action")]


def test_build_class_skips_unlabelled_and_missing_pairs() -> None:
    """Skipped pairs are counted by reason, and every submission is exported."""
    sources = {"ann.py": "print(1)\n", "bob.py": "print(2)\n", "cy.py": "print(3)\n"}
    reviews = [
        PairReviewRow("ann.py", "bob.py", "formal_escalation"),
        PairReviewRow("ann.py", "cy.py", "no_action"),
        PairReviewRow("bob.py", "cy.py", "conversation"),
        PairReviewRow("ann.py", "gone.py", "no_action"),
    ]
    exported = build_class("job-1", sources, reviews, {"bob.py": "breach_identified"})
    assert sorted(exported.files) == [
        "submission001.py",
        "submission002.py",
        "submission003.py",
    ]
    assert exported.rows == [
        (
            "submission001.py",
            "submission002.py",
            1,
            "review:formal_escalation;viva:breach_identified",
        ),
        ("submission001.py", "submission003.py", 0, "review:no_action"),
    ]
    assert exported.skipped == {
        "disposition conversation is not a verdict": 1,
        "submission code not found": 1,
    }


def test_export_round_trips_through_the_runner(tmp_path: Path) -> None:
    """The class evaluation runner reads back exactly what was written."""
    sources = {"ann.py": "x = 1\n", "bob.py": "x = 2\n", "cy.py": "x = 3\n"}
    reviews = [PairReviewRow("cy.py", "ann.py", "no_action")]
    write_class(tmp_path, build_class("job-1", sources, reviews, {}))

    (class_set,) = load_student_holdout(tmp_path)
    assert class_set.name == "student/job-1"
    assert sorted(class_set.files.values()) == ["x = 1\n", "x = 2\n", "x = 3\n"]
    assert class_set.labels == {("submission001.py", "submission003.py"): 0}


def test_output_problem_refuses_unsafe_folders(tmp_path: Path) -> None:
    """A folder with files in it, or one git would track, is refused."""
    assert output_problem(tmp_path / "new") is None
    (tmp_path / "old.txt").write_text("x")
    assert output_problem(tmp_path) is not None
    tracked = Path(__file__).resolve().parent / "holdout_export_probe"
    assert output_problem(tracked) is not None
