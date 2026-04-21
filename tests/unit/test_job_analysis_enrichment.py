"""Tests for assignment-level AI and web analysis payload enrichment."""

from src.backend.api.server import (
    _build_ai_detection_summary,
    _build_web_analysis_summary,
    _normalize_job,
)


def test_build_ai_detection_summary_returns_assignment_payload() -> None:
    submissions = {
        "human.py": """
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
""",
        "ai_like.py": """
# Let us implement a complete processing solution
def process_data(data):
    result = {}
    for item in data:
        result[item.get("key", "unknown")] = item.get("value", 0) * 2
    return result
""",
    }

    summary = _build_ai_detection_summary(submissions)

    assert summary["enabled"] is True
    assert summary["total_files"] == 2
    assert len(summary["submissions"]) == 2
    assert sum(summary["distribution"].values()) == 2
    assert summary["signal_summary"]
    assert (
        summary["submissions"][0]["ai_probability"]
        >= summary["submissions"][1]["ai_probability"]
    )


def test_build_web_analysis_summary_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("INTEGRITYDESK_ENABLE_WEB_ANALYSIS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
    monkeypatch.delenv("STACKEXCHANGE_API_KEY", raising=False)

    summary = _build_web_analysis_summary({"example.py": "print('hello world')"})

    assert summary["enabled"] is False
    assert summary["matched_submissions"] == 0
    assert summary["submissions"] == []
    assert "disabled in Settings" in summary["status_message"]


def test_normalize_job_preserves_analysis_sections() -> None:
    ai_detection = _build_ai_detection_summary({"sample.py": "print('hello world')"})
    normalized = _normalize_job(
        {
            "id": "job-123",
            "course_name": "Course",
            "assignment_name": "Assignment",
            "threshold": 0.5,
            "status": "completed",
            "results": [],
            "submissions": {"sample.py": "print('hello world')"},
            "ai_detection": ai_detection,
            "web_analysis": {
                "enabled": False,
                "configured": False,
                "status_message": "Web analysis disabled.",
                "matched_submissions": 0,
                "highest_similarity": 0,
                "average_similarity": 0,
                "source_totals": {},
                "submissions": [],
            },
        }
    )

    assert normalized["ai_detection"]["enabled"] is True
    assert normalized["ai_detection"]["total_files"] == 1
    assert normalized["web_analysis"]["enabled"] is False
    assert normalized["web_analysis"]["submissions"] == []
