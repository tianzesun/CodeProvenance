"""Celery application for IntegrityDesk background analysis jobs.

Upload endpoints enqueue analysis here instead of running it inline via
Starlette ``BackgroundTasks``. That keeps the API process responsive when
many professors upload at once: jobs wait in Redis and a bounded pool of
worker processes drains them, instead of every analysis running unbounded
inside the single web process.

Configuration is read from the existing ``REDIS_URL`` setting (already in
``.env.example`` and ``deploy.conf.example``) plus two optional env vars:

* ``CELERY_WORKER_CONCURRENCY`` — worker child processes (default 4;
  analysis is CPU-heavy so more rarely helps).
* ``CELERY_TASK_TIME_LIMIT`` — hard kill per job in seconds (default 3600).

The task modules import ``server`` lazily (inside the task body) so this
module stays importable without pulling the whole API app — important for
``celery -A ... worker`` startup time and for unit tests that have no
broker.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _worker_concurrency() -> int:
    """Resolve worker child-process count from the settings object."""
    from src.backend.config.settings import settings

    return int(settings.CELERY_WORKER_CONCURRENCY)


def _task_time_limit() -> int:
    """Resolve the hard per-job time limit in seconds."""
    from src.backend.config.settings import settings

    return int(settings.CELERY_TASK_TIME_LIMIT)


def _broker_url() -> str:
    """Read the broker URL without importing the frozen settings object."""
    from src.backend.config.settings import settings

    url = settings.REDIS_URL
    return url.get_secret_value() if hasattr(url, "get_secret_value") else str(url)


def create_celery_app() -> object:
    """Build the Celery app used by analysis workers.

    Reliability options matter more than throughput here: a killed worker
    must re-queue the job (``task_acks_late`` +
    ``task_reject_on_worker_lost``) and a worker must not hoard queued
    jobs it cannot run yet (``worker_prefetch_multiplier=1``).
    """
    from celery import Celery

    broker = _broker_url()
    app = Celery("integritydesk", broker=broker, backend=broker)
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_time_limit=_task_time_limit(),
        task_soft_time_limit=max(60, _task_time_limit() - 60),
        task_default_queue="analysis",
        task_routes={"src.backend.workers.analysis_tasks.*": {"queue": "analysis"}},
        result_expires=3600,
    )
    app.autodiscover_tasks(["src.backend.workers"])
    return app


celery_app = create_celery_app()


def worker_concurrency() -> int:
    """Public accessor so deploy scripts and tests share one resolution."""
    return _worker_concurrency()
