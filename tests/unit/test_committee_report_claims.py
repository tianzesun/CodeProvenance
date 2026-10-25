"""The committee report must describe how scores were actually produced."""

import pytest

from src.backend.api import server


def _render(tmp_path, summary: dict) -> str:
    report = {
        "summary": {"total_pairs": 3, "suspicious_pairs": 0, **summary},
        "suspicious": [],
        "all_results": [
            {"file_a": "a.py", "file_b": "b.py", "score": 0.2},
            {"file_a": "a.py", "file_b": "c.py", "score": 0.4},
            {"file_a": "b.py", "file_b": "c.py", "score": 0.6},
        ],
    }
    out = tmp_path / "committee_report.html"
    server._generate_committee_report_inner(
        "job-1", "CSC108", "A1", 0.5, report, [], {}, out
    )
    return out.read_text(encoding="utf-8")


def test_report_does_not_claim_scores_are_normalised(tmp_path) -> None:
    html = _render(tmp_path, {})

    assert "normalized relative" not in html
    assert "not rescaled to this class" in html
    assert "median similarity was 40%" in html


def test_report_discloses_ignored_shared_code(tmp_path) -> None:
    assert "16 distinct lines" in _render(tmp_path, {"common_code_lines": 16})
    assert "Shared code:" not in _render(tmp_path, {})


def test_error_report_hides_the_traceback(tmp_path, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(server, "_generate_committee_report_inner", boom)
    out = tmp_path / "committee_report.html"
    with pytest.raises(RuntimeError):
        server._generate_committee_report("job-1", "CSC108", "A1", 0.5, {}, [], {}, out)

    html = out.read_text(encoding="utf-8")
    assert "secret internal detail" not in html
    assert "Traceback" not in html
    assert "job-1" in html
