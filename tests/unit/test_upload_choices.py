"""Per-upload choices (source scanning, previous terms) outrank workspace settings."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.responses import JSONResponse

from src.backend.api import server


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("off", "off"),
        ("Same_Course_Only", "same_course_only"),
        ("all_historical_courses", "all_historical_courses"),
    ],
)
def test_previous_term_choice_is_validated(raw, expected) -> None:
    assert server._previous_term_override(raw) == expected


def test_an_unknown_previous_term_choice_is_rejected() -> None:
    assert isinstance(server._previous_term_override("everything"), JSONResponse)


def test_upload_choices_are_collected_for_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_jobs",
        {
            "j": {
                "status": "processing",
                "source_scan_enabled_override": False,
                "previous_term_override": "same_course_only",
            }
        },
    )

    assert server._upload_choices("j") == {
        "source_scan_enabled_override": False,
        "previous_term_override": "same_course_only",
    }


def test_a_celery_worker_receives_the_upload_choices(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The worker process has no copy of the uploader's job dict."""
    from src.backend.workers.analysis_tasks import run_upload_analysis

    seen: dict[str, Any] = {}

    async def fake_run_analysis(job_id, *args, **kwargs):
        seen.update(server._jobs.get(job_id, {}))

    monkeypatch.setattr(server, "_jobs", {})
    monkeypatch.setattr(server, "_run_analysis", fake_run_analysis)

    run_upload_analysis.run(
        job_id="job-c",
        job_dir=str(tmp_path),
        job_overrides={
            "source_scan_enabled_override": False,
            "previous_term_override": "off",
        },
    )

    assert seen == {
        "source_scan_enabled_override": False,
        "previous_term_override": "off",
    }


def test_dispatch_sends_the_choices_to_celery(monkeypatch) -> None:
    from src.backend.workers import analysis_tasks, dispatch

    sent: dict[str, Any] = {}

    class FakeTask:
        id = "task-1"

    monkeypatch.setattr(dispatch, "broker_available", lambda: True)
    monkeypatch.setattr(
        analysis_tasks.run_upload_analysis,
        "delay",
        lambda **kwargs: sent.update(kwargs) or FakeTask(),
    )

    dispatch.dispatch_analysis(
        job_id="j", job_dir="/tmp/x", job_overrides={"previous_term_override": "off"}
    )

    assert sent["job_overrides"] == {"previous_term_override": "off"}
