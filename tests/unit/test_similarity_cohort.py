"""Tests for the per-job cohort context attached to similarity scores."""

from __future__ import annotations

import json

import pytest

from src.backend.api import server
from src.backend.application.services.similarity_cohort import (
    COHORT_DISCLOSURE,
    CohortContext,
    annotate_results,
    percentile_rank,
)
from src.backend.infrastructure.professional_report_generator import ReportGenerator


def test_percentile_rank_halves_ties() -> None:
    """A block of identical scores must not all rank as top of the class."""
    scores = [0.0, 1.0, 1.0, 1.0]
    assert percentile_rank(0.0, scores) == pytest.approx(0.125)
    assert percentile_rank(1.0, scores) == pytest.approx(0.625)


def test_percentile_rank_without_cohort() -> None:
    """An empty cohort has no ranking."""
    assert percentile_rank(0.5, []) == 0.0


def test_cohort_context_reports_quartiles() -> None:
    """Quartiles are interpolated over the ordered cohort."""
    context = CohortContext.from_scores([0.0, 0.5, 1.0])
    assert context.size == 3
    assert context.median == pytest.approx(0.5)
    assert context.p25 == pytest.approx(0.25)
    assert context.p75 == pytest.approx(0.75)


def test_cohort_context_discloses_that_scores_are_not_probabilities() -> None:
    """The payload must say what the number is, not only what it is not."""
    payload = CohortContext.from_scores([0.2, 0.4]).to_dict()
    assert payload["disclosure"] == COHORT_DISCLOSURE
    assert "not a probability of plagiarism" in payload["disclosure"]


def test_annotate_results_uses_the_full_cohort_for_a_truncated_page() -> None:
    """A capped page must be ranked against every score, not against itself."""
    page = [{"file_a": "a", "file_b": "b", "score": 0.9}]
    context = annotate_results(page, scores=[0.1, 0.2, 0.9])
    # Midrank: two scores below, one tied -> (2 + 0.5) / 3.
    assert page[0]["cohort_percentile"] == pytest.approx(0.8333)
    assert context["size"] == 3
    assert context["median"] == pytest.approx(0.2)


def test_annotate_results_skips_rows_without_a_score() -> None:
    """A malformed row must not break the cohort or get a percentile."""
    rows = [{"score": 0.4}, {"score": None}, {"note": "no score"}]
    context = annotate_results(rows)
    assert context["size"] == 1
    assert rows[0]["cohort_percentile"] == pytest.approx(0.5)
    assert "cohort_percentile" not in rows[1]
    assert "cohort_percentile" not in rows[2]


def test_normalize_job_attaches_context_and_percentiles() -> None:
    """Every job payload carries the distribution its pairs were ranked in."""
    job = {
        "id": "job-1",
        "results": [
            {"file_a": "a", "file_b": "b", "score": 0.9},
            {"file_a": "a", "file_b": "c", "score": 0.3},
        ],
    }
    normalized = server._normalize_job(job)
    assert normalized["similarity_context"]["size"] == 2
    assert normalized["similarity_context"]["median"] == pytest.approx(0.6)
    assert [row["cohort_percentile"] for row in normalized["results"]] == [
        pytest.approx(0.75),
        pytest.approx(0.25),
    ]


def test_normalize_job_keeps_a_context_computed_from_the_full_cohort() -> None:
    """A page load must not replace the database's full-cohort context."""
    job = {
        "id": "job-1",
        "similarity_context": {"size": 500, "median": 0.2, "p25": 0.1, "p75": 0.4},
        "results": [{"file_a": "a", "file_b": "b", "score": 0.9}],
    }
    normalized = server._normalize_job(job)
    assert normalized["similarity_context"]["size"] == 500
    assert normalized["results"][0]["cohort_percentile"] is None


def test_normalize_result_keeps_the_percentile() -> None:
    """Re-normalising a cached job must not drop the stamped percentile."""
    result = server._normalize_result(
        {"file_a": "a", "file_b": "b", "score": 0.9, "cohort_percentile": 0.75}
    )
    assert result["cohort_percentile"] == 0.75


def test_report_shows_cohort_context_and_disclosure() -> None:
    """The committee-facing report must state what the score ranks against."""
    generator = ReportGenerator(institution_name="Test University")
    note = generator._cohort_note(
        {
            "size": 435,
            "median": 0.21,
            "p25": 0.12,
            "p75": 0.38,
            "disclosure": COHORT_DISCLOSURE,
        }
    )
    assert "435 pairs" in note
    assert "median similarity 0.21" in note
    assert COHORT_DISCLOSURE in note


def test_report_omits_cohort_context_without_a_cohort() -> None:
    """A job without pair scores must not render an empty cohort note."""
    generator = ReportGenerator(institution_name="Test University")
    assert generator._cohort_note({}) == ""


def test_ensure_similarity_context_backfills_an_old_report() -> None:
    """Reports written before the cohort context existed still get one."""
    payload = {
        "pairs": [
            {"similarity_score": 0.1},
            {"similarity_score": 0.2},
            {"similarity_score": 0.6},
        ]
    }
    server._ensure_similarity_context(payload)
    assert payload["similarity_context"]["size"] == 3
    assert payload["similarity_context"]["median"] == pytest.approx(0.2)
    assert payload["similarity_context"]["disclosure"] == COHORT_DISCLOSURE


def test_ensure_similarity_context_never_replaces_a_measured_cohort() -> None:
    """A context computed from the full cohort must survive regeneration."""
    context = {"size": 900, "median": 0.2, "p25": 0.1, "p75": 0.4}
    payload = {"similarity_context": context, "pairs": [{"similarity_score": 0.9}]}
    server._ensure_similarity_context(payload)
    assert payload["similarity_context"] == context


def test_json_report_carries_the_cohort_context() -> None:
    """Machine consumers get the same context as the HTML decision panel."""
    generator = ReportGenerator(institution_name="Test University")
    context = CohortContext.from_scores([0.1, 0.2, 0.3]).to_dict()
    report = json.loads(
        generator.generate_json_report({"similarity_context": context, "summary": {}})
    )
    assert report["similarity_context"]["size"] == 3
    assert report["similarity_context"]["disclosure"] == COHORT_DISCLOSURE
