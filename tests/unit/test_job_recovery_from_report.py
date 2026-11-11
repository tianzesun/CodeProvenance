"""Jobs read back from report.json keep their names and score explanations."""

import json
from pathlib import Path

import pytest

from src.backend.api import server


def _recover_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pair: dict, **report: str
) -> dict:
    report_dir = tmp_path / "job-1"
    report_dir.mkdir()
    (report_dir / "report.json").write_text(
        json.dumps({"threshold": 0.5, "pairs": [pair], **report}), encoding="utf-8"
    )
    monkeypatch.setattr(server, "_job_report_dir", lambda job_id: report_dir)
    job = server._recover_job_from_report("job-1", store=False)
    assert job is not None
    return job


def _recover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pair: dict) -> dict:
    (result,) = _recover_job(tmp_path, monkeypatch, pair)["results"]
    return result


PAIR = {
    "file_a": "a.py",
    "file_b": "b.py",
    "similarity_score": 0.93,
    "risk_level": "CRITICAL",
    "engine_scores": {"winnowing": 0.67, "embedding": 0.98},
}


def test_recovered_results_keep_contributions(tmp_path, monkeypatch) -> None:
    pair = {**PAIR, "contributions": {"winnowing": 3.205, "embedding": -0.187}}

    result = _recover(tmp_path, monkeypatch, pair)

    assert result["contributions"] == {"winnowing": 3.205, "embedding": -0.187}


def test_reports_written_before_contributions_recover_without_them(
    tmp_path, monkeypatch
) -> None:
    result = _recover(tmp_path, monkeypatch, PAIR)

    assert result["contributions"] == {}


def test_recovered_jobs_keep_their_names(tmp_path, monkeypatch) -> None:
    job = _recover_job(
        tmp_path, monkeypatch, PAIR, course_name="CSC108", assignment_name="Lab 3"
    )

    assert job["assignment_name"] == "Lab 3"
    assert job["course_name"] == "CSC108"


def test_reports_without_names_keep_the_fallback(tmp_path, monkeypatch) -> None:
    job = _recover_job(tmp_path, monkeypatch, PAIR)

    assert job["assignment_name"] == "Recovered Assignment job-1"
    assert job["course_name"] == "Recovered Assignment job-1"


def test_the_json_report_records_the_names() -> None:
    from src.backend.infrastructure.professional_report_generator import (
        ReportGenerator,
    )

    report = json.loads(
        ReportGenerator().generate_json_report(
            {"course_name": "CSC108", "assignment_name": "Lab 3", "summary": {}}
        )
    )

    assert (report["course_name"], report["assignment_name"]) == ("CSC108", "Lab 3")
