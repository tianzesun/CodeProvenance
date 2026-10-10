"""Dispatch analysis jobs to Celery or fall back to in-process execution.

The upload endpoints call :func:`dispatch_analysis` instead of touching
``BackgroundTasks`` directly. When a Redis broker is reachable the job is
sent to the ``analysis`` queue and a bounded pool of Celery workers drains
it; otherwise (local dev without Redis, broker down, tests) the existing
``_run_analysis_background`` runner executes on a shared, bounded thread
pool so uploads never hard-fail just because the queue is unavailable —
and never spawn one CPU-heavy thread per request either.

Broker availability is probed once per process and cached — every upload
doing a TCP handshake to Redis would add latency to the hot path. Tests
can reset the cache via :func:`reset_broker_cache`.
"""

from __future__ import annotations

import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_broker_available: bool | None = None

_inline_pool: ThreadPoolExecutor | None = None
_inline_pool_lock = threading.Lock()


def reset_broker_cache() -> None:
    """Clear the cached broker-availability probe (tests only)."""
    global _broker_available
    _broker_available = None


def _inline_executor() -> ThreadPoolExecutor:
    """Return the shared pool that runs in-process analysis jobs.

    Created once per process on first use and sized by
    ``CELERY_WORKER_CONCURRENCY`` — the same knob that bounds the Celery
    pool — so a broker outage cannot turn the fallback into one
    CPU-heavy thread per concurrent upload. Jobs beyond ``max_workers``
    wait in the pool with their status still ``queued``, mirroring the
    queue behavior the fallback replaces.
    """
    global _inline_pool
    if _inline_pool is None:
        with _inline_pool_lock:
            if _inline_pool is None:
                from src.backend.config.settings import settings

                _inline_pool = ThreadPoolExecutor(
                    max_workers=settings.CELERY_WORKER_CONCURRENCY,
                    thread_name_prefix="inline-analysis",
                )
    return _inline_pool


def _redis_host_port(broker_url: str) -> tuple[str, int] | None:
    """Extract a TCP target from a ``redis://`` broker URL, if possible."""
    try:
        parsed = urlparse(broker_url)
    except ValueError:
        return None
    if parsed.scheme not in ("redis", "rediss"):
        return None
    return (parsed.hostname or "127.0.0.1", parsed.port or 6379)


def broker_available(timeout: float = 1.0) -> bool:
    """Return whether the Celery broker accepts TCP connections.

    The result is cached for the process lifetime: Redis does not flap
    under normal operation, and re-probing on every upload would add a
    round trip to the hot path. Non-Redis brokers are assumed available
    (Celery reports delivery failures itself).
    """
    global _broker_available
    if _broker_available is not None:
        return _broker_available

    try:
        from src.backend.config.settings import settings

        broker_url = settings.REDIS_URL
        broker_str = (
            broker_url.get_secret_value()
            if hasattr(broker_url, "get_secret_value")
            else str(broker_url)
        )
    except Exception:
        logger.warning("Could not read REDIS_URL; using in-process analysis")
        _broker_available = False
        return False

    target = _redis_host_port(broker_str)
    if target is None:
        _broker_available = True
        return True

    host, port = target
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        logger.warning(
            "Redis broker at %s:%s unreachable; using in-process analysis",
            host,
            port,
        )
        _broker_available = False
        return False
    _broker_available = True
    return True


def _current_user_summary(current_user: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Extract the broker-safe ownership fields from a user dict.

    The full user dict can carry non-JSON values (datetimes, secrets);
    only the identifiers cross the broker. The worker re-attaches them
    to the persisted job record.
    """
    if not current_user:
        return None, None
    owner = current_user.get("id")
    tenant = current_user.get("tenant_id")
    return (str(owner) if owner else None, str(tenant) if tenant else None)


def dispatch_analysis(
    *,
    job_id: str,
    job_dir: Any,
    course_name: str = "",
    assignment_name: str = "",
    assignment_id: str | None = None,
    assignment_mode: str = "",
    threshold: float = 0.5,
    current_user: dict[str, Any] | None = None,
    engine_keys_raw: str = "",
    tool_ids_raw: str = "",
    starter_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Enqueue analysis on Celery, falling back to in-process execution.

    Returns:
        Mapping with ``mode`` (``"celery"`` or ``"inline"``) and, for the
        Celery path, the ``task_id`` so operators can correlate jobs.
    """
    owner_user_id, tenant_id = _current_user_summary(current_user)

    if broker_available():
        try:
            from src.backend.workers.analysis_tasks import run_upload_analysis

            task = run_upload_analysis.delay(
                job_id=job_id,
                job_dir=str(job_dir),
                course_name=course_name,
                assignment_name=assignment_name,
                assignment_id=assignment_id,
                assignment_mode=assignment_mode,
                threshold=threshold,
                owner_user_id=owner_user_id,
                tenant_id=tenant_id,
                engine_keys_raw=engine_keys_raw,
                tool_ids_raw=tool_ids_raw,
                starter_sources=starter_sources,
            )
            logger.info("Enqueued analysis job %s as Celery task %s", job_id, task.id)
            return {"mode": "celery", "task_id": task.id}
        except Exception:
            logger.exception(
                "Celery enqueue failed for job %s; falling back to in-process",
                job_id,
            )

    from src.backend.api import server

    # Starlette's BackgroundTasks used to run this on a worker thread after
    # the response was sent. Call sites may be ``async def`` endpoints whose
    # running event loop forbids ``run_until_complete`` in-thread, and the
    # sync ``/v1/analyze`` route must not block its own response for the
    # whole analysis — so submit to the shared pool instead of running here.
    _inline_executor().submit(
        server._run_analysis_background,
        job_id,
        job_dir,
        course_name,
        assignment_name,
        assignment_id,
        assignment_mode,
        threshold,
        current_user,
        engine_keys_raw,
        tool_ids_raw,
        starter_sources,
    )
    logger.info("Running analysis job %s on the in-process pool", job_id)
    return {"mode": "inline"}
