"""Unit tests for the per-submission source-scan override surviving job setup.

The upload endpoints store ``source_scan_enabled_override`` on the job, then
``_run_analysis`` fully rebuilds ``_jobs[job_id]``. These tests guard the fix
that preserves the override through that rebuild so the form toggle actually
reaches the web-analysis step.
"""

import asyncio

from src.backend.api import server


def _capturing_persist(captured: list[dict]):
    """Return a ``_persist_job`` stand-in that snapshots the job at call time."""

    def _fake(job_id: str) -> None:
        captured.append(dict(server._jobs.get(job_id, {})))

    return _fake


def _run_analysis_to_job_setup(
    monkeypatch,
    tmp_path,
    override,
):
    """Drive ``_run_analysis`` far enough to rebuild the job, capturing the state.

    ``_read_files_from_dir`` returns ``{}`` so ``_run_analysis`` takes the
    <2-files early-return path (no awaits, no DB). ``_persist_job`` is swapped
    for a capture, and engine-weight resolution is stubbed so the test is fully
    DB-free and focused only on the source-scan override preservation.
    """
    captured: list[dict] = []
    monkeypatch.setattr(server, "_persist_job", _capturing_persist(captured))
    monkeypatch.setattr(server, "_read_files_from_dir", lambda _job_dir: {})
    monkeypatch.setattr(
        server,
        "_get_upload_engine_weights",
        lambda *_a, **_k: {key: 1.0 for key in server.UPLOAD_ENGINE_KEYS},
    )
    # Avoid writing into the repo's reports directory during tests.
    monkeypatch.setattr(server, "_job_report_dir", lambda _job_id: tmp_path)

    server._jobs["testjob"] = {"source_scan_enabled_override": override}
    try:
        asyncio.run(server._run_analysis("testjob", tmp_path, "Course", "Assignment"))
    finally:
        server._jobs.pop("testjob", None)
    return captured


def test_run_analysis_preserves_false_override(monkeypatch, tmp_path) -> None:
    """A False source-scan override survives the job-dict rebuild."""
    captured = _run_analysis_to_job_setup(monkeypatch, tmp_path, False)
    assert captured, "_persist_job must have been called during job setup"
    job = captured[0]
    assert job.get("source_scan_enabled_override") is False


def test_run_analysis_preserves_true_override(monkeypatch, tmp_path) -> None:
    """A True source-scan override survives the job-dict rebuild."""
    captured = _run_analysis_to_job_setup(monkeypatch, tmp_path, True)
    assert captured, "_persist_job must have been called during job setup"
    job = captured[0]
    assert job.get("source_scan_enabled_override") is True


def test_run_analysis_adds_no_override_when_none_set(monkeypatch, tmp_path) -> None:
    """The rebuilt job gains no spurious override key when none was submitted."""
    # Seed an override-free job entry so we exercise the rebuild itself rather
    # than the capture happening to see an empty dict.
    captured: list[dict] = []
    monkeypatch.setattr(server, "_persist_job", _capturing_persist(captured))
    monkeypatch.setattr(server, "_read_files_from_dir", lambda _job_dir: {})
    monkeypatch.setattr(
        server,
        "_get_upload_engine_weights",
        lambda *_a, **_k: {key: 1.0 for key in server.UPLOAD_ENGINE_KEYS},
    )
    monkeypatch.setattr(server, "_job_report_dir", lambda _job_id: tmp_path)

    server._jobs["testjob"] = {}
    try:
        asyncio.run(server._run_analysis("testjob", tmp_path, "Course", "Assignment"))
    finally:
        server._jobs.pop("testjob", None)

    assert captured, "_persist_job must have been called during job setup"
    job = captured[0]
    assert "source_scan_enabled_override" not in job
