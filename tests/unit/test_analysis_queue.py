"""Unit tests for the Celery analysis queue and its dispatcher fallback.

Covers the three guarantees the 100-user story depends on:

* :mod:`src.backend.workers.celery_app` resolves broker, routing, and
  reliability options (late acks, single prefetch, per-job time limit)
  from the existing ``REDIS_URL`` setting.
* :mod:`src.backend.workers.analysis_tasks` passes only JSON-safe broker
  scalars and forwards them to the existing ``server._run_analysis``
  pipeline in argument order.
* :mod:`src.backend.workers.dispatch` sends jobs to Celery when the
  broker is reachable and falls back to the in-process runner otherwise,
  so uploads keep working with no Redis running (local dev, tests).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from src.backend.workers import celery_app as celery_app_module
from src.backend.workers import dispatch as dispatch_module


@pytest.fixture(autouse=True)
def _reset_broker_probe():
    """Stop one test's cached probe result leaking into the next."""
    dispatch_module.reset_broker_cache()
    yield
    dispatch_module.reset_broker_cache()


class TestCeleryAppConfig:
    """The Celery app must be wired for reliable, bounded analysis work."""

    def test_task_routes_to_the_analysis_queue(self) -> None:
        app = celery_app_module.celery_app
        assert app.conf.task_default_queue == "analysis"

    def test_worker_does_not_hoard_queued_jobs(self) -> None:
        # A worker that prefetches N jobs while running 1 blocks N-1 jobs
        # from the other workers while holding them un-acked.
        assert celery_app_module.celery_app.conf.worker_prefetch_multiplier == 1

    def test_lost_worker_requeues_the_job(self) -> None:
        app = celery_app_module.celery_app
        assert app.conf.task_acks_late is True
        assert app.conf.task_reject_on_worker_lost is True

    def test_jobs_have_a_time_limit(self) -> None:
        app = celery_app_module.celery_app
        assert app.conf.task_time_limit == celery_app_module._task_time_limit()
        assert app.conf.task_soft_time_limit < app.conf.task_time_limit

    def test_concurrency_comes_from_settings(self, override_setting: Any) -> None:
        override_setting("CELERY_WORKER_CONCURRENCY", 2)
        assert celery_app_module.worker_concurrency() == 2


class TestRunUploadAnalysisTask:
    """The task body must forward broker scalars to the real pipeline."""

    def test_forwards_all_parameters_in_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from src.backend.api import server
        from src.backend.workers.analysis_tasks import run_upload_analysis

        calls: list[dict[str, Any]] = []

        async def _fake_run_analysis(*args: Any, **kwargs: Any) -> None:
            calls.append({"args": args, "kwargs": kwargs})

        monkeypatch.setattr(server, "_run_analysis", _fake_run_analysis)

        job_dir = tmp_path / "job-1"
        job_dir.mkdir()
        result = run_upload_analysis.run(
            job_id="job-1",
            job_dir=str(job_dir),
            course_name="CS101",
            assignment_name="A1",
            assignment_id="assign-9",
            assignment_mode="balanced",
            threshold=0.7,
            owner_user_id="user-1",
            tenant_id="tenant-1",
            engine_keys_raw='["token"]',
            tool_ids_raw="moss",
            starter_sources=["print('starter')"],
        )

        assert result == {"job_id": "job-1", "status": "completed"}
        assert len(calls) == 1
        args = calls[0]["args"]
        assert args[0] == "job-1"
        assert args[1] == Path(str(job_dir))
        assert args[2:7] == ("CS101", "A1", "assign-9", "balanced", 0.7)
        assert args[7] == {"id": "user-1", "tenant_id": "tenant-1"}
        assert args[8:12] == ('["token"]', "moss", ["print('starter')"])

    def test_anonymous_upload_passes_no_user(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from src.backend.api import server
        from src.backend.workers.analysis_tasks import run_upload_analysis

        calls: list[dict[str, Any]] = []

        async def _fake_run_analysis(*args: Any, **kwargs: Any) -> None:
            calls.append({"args": args, "kwargs": kwargs})

        monkeypatch.setattr(server, "_run_analysis", _fake_run_analysis)

        run_upload_analysis.run(job_id="job-2", job_dir=str(tmp_path))

        assert calls[0]["args"][7] is None


class TestDispatchAnalysis:
    """Uploads must queue on Celery when possible, run inline otherwise."""

    def _params(self, tmp_path: Path) -> dict[str, Any]:
        return {
            "job_id": "job-9",
            "job_dir": tmp_path / "job-9",
            "course_name": "CS101",
            "assignment_name": "A1",
            "assignment_id": None,
            "assignment_mode": "",
            "threshold": 0.5,
            "current_user": {"id": "user-1", "tenant_id": "tenant-1"},
            "engine_keys_raw": "",
            "tool_ids_raw": "",
            "starter_sources": None,
        }

    def test_uses_celery_when_broker_is_up(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from src.backend.workers import analysis_tasks

        monkeypatch.setattr(dispatch_module, "broker_available", lambda: True)
        enqueued: list[dict[str, Any]] = []

        class _Task:
            id = "celery-task-1"

        def _fake_delay(**kwargs: Any) -> Any:
            enqueued.append(kwargs)
            return _Task()

        monkeypatch.setattr(analysis_tasks.run_upload_analysis, "delay", _fake_delay)

        outcome = dispatch_module.dispatch_analysis(**self._params(tmp_path))

        assert outcome == {"mode": "celery", "task_id": "celery-task-1"}
        assert enqueued[0]["job_id"] == "job-9"
        assert enqueued[0]["owner_user_id"] == "user-1"
        assert enqueued[0]["tenant_id"] == "tenant-1"

    def test_falls_back_inline_when_broker_is_down(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from src.backend.api import server

        monkeypatch.setattr(dispatch_module, "broker_available", lambda: False)
        calls: list[dict[str, Any]] = []
        done = threading.Event()

        def _fake_background(*args: Any, **kwargs: Any) -> None:
            calls.append({"args": args, "kwargs": kwargs})
            done.set()

        monkeypatch.setattr(server, "_run_analysis_background", _fake_background)

        outcome = dispatch_module.dispatch_analysis(**self._params(tmp_path))

        assert outcome == {"mode": "inline"}
        # The fallback runs on the shared pool (never on the caller's thread),
        # so wait for it instead of racing the worker thread.
        assert done.wait(timeout=10)
        assert len(calls) == 1
        # Full user dict is passed through on the inline path (same process).
        assert calls[0]["args"][7] == {"id": "user-1", "tenant_id": "tenant-1"}

    def test_falls_back_inline_when_enqueue_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from src.backend.api import server
        from src.backend.workers import analysis_tasks

        monkeypatch.setattr(dispatch_module, "broker_available", lambda: True)

        def _raise(**kwargs: Any) -> Any:
            raise ConnectionError("broker went away mid-enqueue")

        monkeypatch.setattr(analysis_tasks.run_upload_analysis, "delay", _raise)
        calls: list[dict[str, Any]] = []
        done = threading.Event()

        def _fake_background(*args: Any, **kwargs: Any) -> None:
            calls.append({"args": args, "kwargs": kwargs})
            done.set()

        monkeypatch.setattr(server, "_run_analysis_background", _fake_background)

        outcome = dispatch_module.dispatch_analysis(**self._params(tmp_path))

        assert outcome == {"mode": "inline"}
        assert done.wait(timeout=10)
        assert len(calls) == 1

    def test_redis_url_parsing(self) -> None:
        assert dispatch_module._redis_host_port("redis://127.0.0.1:6379/0") == (
            "127.0.0.1",
            6379,
        )
        assert dispatch_module._redis_host_port("rediss://cache.internal/1") == (
            "cache.internal",
            6379,
        )
        # Non-Redis brokers skip the TCP probe (Celery reports errors itself).
        assert dispatch_module._redis_host_port("amqp://guest@localhost//") is None

    def test_user_summary_extracts_only_identifiers(self) -> None:
        assert dispatch_module._current_user_summary(None) == (None, None)
        assert dispatch_module._current_user_summary({}) == (None, None)
        assert dispatch_module._current_user_summary(
            {"id": "u", "tenant_id": "t", "email": "a@b.c", "role": "professor"}
        ) == ("u", "t")
