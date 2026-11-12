"""The Integrity Assessment Report must only state what the analysis found."""

from src.backend.infrastructure.integrity_assessment_report import (
    IntegrityAssessmentReportGenerator,
)
from src.backend.infrastructure.integrity_assessment_report_html import (
    render_integrity_report_html,
)

CODE_A = "def total(xs):\n    s = 0\n    for x in xs:\n        s += x\n    return s\n"
CODE_B = "def add_all(values):\n    acc = 0\n    for v in values:\n        acc += v\n    return acc\n"


def _job(**extra) -> dict:
    return {
        "id": "job-1",
        "assignment_name": "Lab 3",
        "course_name": "CSC108",
        "owner_user_id": "prof-1",
        "owner_user_email": "professor@example.edu",
        "results": [
            {
                "file_a": "a.py",
                "file_b": "b.py",
                "score": 0.93,
                "features": {"winnowing": 0.67, "fused_score": 1.0, "raw_score": 0.93},
                "contributions": {"winnowing": 3.0, "coverage": 1.0, "embedding": -0.2},
                "matching_blocks": [
                    {
                        "lines_a": "1-5",
                        "lines_b": "1-5",
                        "similarity": 0.95,
                        "clone_type": "Type 2",
                    }
                ],
                "code_a": CODE_A,
                "code_b": CODE_B,
            },
            {"file_a": "a.py", "file_b": "c.py", "score": 0.2, "features": {}},
            {"file_a": "b.py", "file_b": "c.py", "score": 0.4, "features": {}},
        ],
        **extra,
    }


def _render(job: dict) -> tuple:
    report = IntegrityAssessmentReportGenerator().generate_from_job(job)
    return report, render_integrity_report_html(report)


def test_the_uploader_is_never_named_as_the_student() -> None:
    report, page = _render(_job())

    assert report.student_display == ""
    assert "professor@example.edu" not in page
    assert "Whole class (3 submissions)" in page


def test_types_come_from_matched_blocks_not_from_scores() -> None:
    report, _ = _render(_job())

    top, *rest = report.pair_results
    assert (
        top.plagiarism_type == "T2"
    )  # the block says renamed, the 0.93 score once said "T1"
    assert all(
        p.plagiarism_type == "" for p in rest
    )  # no blocks, no type (0.2 was "T4")
    assert report.plagiarism_type_breakdown == {"T2": 1.0}


def test_the_appendix_shows_code_not_line_ranges() -> None:
    _, page = _render(_job())

    assert "acc += v" in page
    assert "1-5</div>" not in page


def test_engine_section_shows_what_raised_the_top_score() -> None:
    report, _ = _render(_job())

    assert [e.engine for e in report.engine_scores] == ["winnowing", "coverage"]
    assert abs(sum(e.score for e in report.engine_scores) - 1.0) < 1e-9
    assert [e.label for e in report.engine_scores] == [
        "Chunk hash match",
        "Matched-line coverage",
    ]


def test_class_context_is_computed_not_zero() -> None:
    report, _ = _render(_job())

    cc = report.class_context
    assert (cc.total_submissions, cc.total_pairs) == (3, 3)
    assert cc.median_similarity == 0.4
    assert abs(cc.flagged_ratio - 1 / 3) < 1e-9


def test_no_legal_claims_invented_policy_or_made_up_statistics() -> None:
    report, page = _render(_job())

    for phrase in (
        "preponderance",
        "FERPA",
        "bootstrap",
        "independent engines",
        "Sanctions Matrix",
        "Confidence Interval",
        "Course failure to suspension",
    ):
        assert phrase not in page, phrase
    assert report.sanctions_matrix == []
    assert "does not set or recommend any sanction" in page
    assert "confidence" not in report.to_dict()["pair_results"][0]


def test_bands_match_the_product() -> None:
    generator = IntegrityAssessmentReportGenerator()

    assert generator._classify_risk(0.35) == "moderate"
    assert generator._classify_risk(0.65) == "high"
    assert generator._classify_risk(0.85) == "critical"


def test_a_check_without_results_still_renders() -> None:
    report, page = _render({"id": "job-2", "results": []})

    assert report.pair_results == [] and report.engine_scores == []
    assert "Integrity Assessment Report" in page
