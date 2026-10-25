"""Stuck-queue watchdog for IntegrityDesk analysis jobs.

Jobs reach Celery whenever Redis answers; if no worker drains the queue
(or a worker dies mid-task and redelivery stalls), rows sit ``queued`` or
``processing`` forever with no timeout and no fallback. This module watches
for that state and POSTs one alert per stuck job to the workspace webhook
URL, so an admin learns about it from their phone instead of a student.

Design notes:

* Runs in a daemon thread started with the other background workers; the
  loop never raises (every probe degrades internally).
* Alert-once per job id while it stays stuck; ids are forgotten as soon as
  the job leaves the stuck set, so a recurrence re-alerts. No persistence:
  a backend restart may resend one alert per still-stuck job, which is the
  desired behavior after an outage.
* Webhook delivery is a direct stdlib POST, not the outbox/worker pipeline —
  adding another unsupervised process to supervise the first ones would
  recreate the original failure mode.
* The same https-only, public-host SSRF policy as job webhooks applies:
  ``validate_webhook_url`` from the jobs routes module.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

#: How often the watchdog scans, in seconds.
CHECK_INTERVAL_SECONDS = 300
#: A queued (never started) job this old is stuck, not busy.
QUEUED_STUCK_MINUTES = 30
#: A processing job gets longer: huge classes can legitimately run.
PROCESSING_STUCK_MINUTES = 120
#: Network timeout for the alert POST itself, in seconds.
ALERT_TIMEOUT_SECONDS = 10

#: Job ids already alerted while continuously stuck (in-memory only).
_alerted_job_ids: set[str] = set()
_alerted_lock = threading.Lock()


def _webhook_url() -> str | None:
    """Return the validated platform webhook URL (server config), if one is set.

    The platform webhook hears about every stuck job; each workspace's own
    webhook hears about that workspace's (``_workspace_webhook_url``).

    Returns:
        The URL string, or ``None`` when unset or failing validation.
    """
    try:
        from src.backend.config.settings import settings

        raw = settings.WEBHOOK_URL
        url = raw.get_secret_value() if hasattr(raw, "get_secret_value") else raw
    except Exception:
        return None
    return _validated(url)


def _workspace_webhook_url(tenant_id: str | None) -> str | None:
    """Return the validated webhook URL a workspace saved, if any."""
    if not tenant_id:
        return None
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Tenant

        with SessionLocal() as db:
            tenant = db.get(Tenant, tenant_id)
            record = (
                tenant.settings if tenant and isinstance(tenant.settings, dict) else {}
            )
    except Exception:
        logger.debug("Could not read workspace %s webhook", tenant_id)
        return None
    return _validated(record.get("webhook_url"))


def _validated(url: Any) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        from src.backend.api.routes.jobs import validate_webhook_url

        return validate_webhook_url(url)
    except Exception:
        logger.debug("Ignoring invalid webhook URL for queue alerts")
        return None


def _stuck_jobs(
    queued_minutes: float = QUEUED_STUCK_MINUTES,
    processing_minutes: float = PROCESSING_STUCK_MINUTES,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List jobs stuck beyond their status-specific age threshold.

    Args:
        queued_minutes: Age past which a queued job counts as stuck.
        processing_minutes: Age past which a processing job counts as stuck.
        limit: Maximum jobs to return (newest stuck first).

    Returns:
        A list of ``{id, name, status, age_seconds}`` dicts. Never raises:
        database trouble yields an empty list (and a log line).
    """
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Job
    except Exception:
        logger.debug("Queue watchdog unavailable (no database module)")
        return []
    now = datetime.now(timezone.utc)
    stuck: list[dict[str, Any]] = []
    try:
        with SessionLocal() as db:
            rows = (
                db.query(Job)
                .filter(Job.status.in_(["queued", "processing"]))
                .order_by(Job.created_at.desc())
                .limit(limit)
                .all()
            )
            for row in rows:
                created = getattr(row, "created_at", None)
                if created is None:
                    continue
                try:
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    age_seconds = (now - created).total_seconds()
                except Exception:
                    logger.debug(
                        "Skipping job %s with unreadable timestamp",
                        getattr(row, "id", "?"),
                    )
                    continue
                threshold = (
                    queued_minutes * 60
                    if str(row.status) == "queued"
                    else processing_minutes * 60
                )
                if age_seconds >= threshold:
                    stuck.append(
                        {
                            "id": str(row.id),
                            "name": getattr(row, "name", "") or "",
                            "status": str(row.status),
                            "age_seconds": round(age_seconds, 1),
                            "tenant_id": (
                                str(row.tenant_id)
                                if getattr(row, "tenant_id", None)
                                else None
                            ),
                        }
                    )
    except Exception:
        logger.warning("Stuck-job scan failed", exc_info=True)
        return []
    return stuck


def _worker_summary() -> dict[str, Any]:
    """Summarize Celery worker presence for the alert context.

    Returns:
        A dict with worker names (possibly empty) and any inspect error.
        Never raises.
    """
    try:
        from src.backend.integrations.system_status import check_celery
    except Exception:
        return {"workers": [], "error": "status probe unavailable"}
    try:
        import asyncio

        # The watchdog thread has no running loop; asyncio.run fails safe
        # into "probe failed" anywhere else.
        result = asyncio.run(check_celery())
    except Exception:
        return {"workers": [], "error": "probe failed"}
    if result.get("status") == "up":
        return {"workers": [], "error": None}
    return {"workers": [], "error": str(result.get("detail") or result.get("status"))}


def _post_alert(url: str, payload: dict[str, Any]) -> bool:
    """POST one alert payload, returning delivery success.

    Args:
        url: Validated webhook URL.
        payload: JSON-serializable alert body.

    Returns:
        ``True`` on HTTP 2xx, ``False`` otherwise (logged, never raised).
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "IntegrityDesk-queue-watchdog/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=ALERT_TIMEOUT_SECONDS) as response:
            ok = 200 <= int(getattr(response, "status", 200)) < 300
    except Exception as exc:
        logger.warning("Queue alert POST failed: %s", exc)
        return False
    if not ok:
        logger.warning("Queue alert POST rejected by receiver")
    return ok


def check_and_alert() -> dict[str, Any]:
    """Scan once and alert on newly-stuck jobs.

    Returns:
        A summary dict with ``stuck`` (current stuck jobs), ``alerted``
        (newly alerted ids) and ``workers`` context. Never raises.
    """
    stuck = _stuck_jobs()
    with _alerted_lock:
        # Forget jobs that recovered so a recurrence re-alerts.
        still_stuck = {job["id"] for job in stuck}
        _alerted_job_ids.intersection_update(still_stuck)
        fresh = [job for job in stuck if job["id"] not in _alerted_job_ids]
    summary: dict[str, Any] = {
        "stuck": stuck,
        "alerted": [],
        "workers": _worker_summary(),
    }
    if not fresh:
        return summary
    # The platform webhook gets every stuck job; a workspace's own webhook
    # gets its own (this used to be whichever workspace's URL a request had
    # last applied to the shared settings).
    targets: dict[str, list[dict[str, Any]]] = {}
    platform_url = _webhook_url()
    if platform_url:
        targets[platform_url] = list(fresh)
    by_workspace: dict[str, list[dict[str, Any]]] = {}
    for job in fresh:
        if job.get("tenant_id"):
            by_workspace.setdefault(job["tenant_id"], []).append(job)
    for tenant_id, jobs in by_workspace.items():
        url = _workspace_webhook_url(tenant_id)
        if url and url != platform_url:
            targets.setdefault(url, []).extend(jobs)
    if not targets:
        logger.info(
            "Queue watchdog: %d stuck job(s) but no webhook URL configured",
            len(fresh),
        )
        return summary
    delivered: set[str] = set()
    for url, jobs in targets.items():
        listed = [{k: v for k, v in job.items() if k != "tenant_id"} for job in jobs]
        payload = {
            "event": "jobs.stuck",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "stuck": listed,
            "workers": summary["workers"],
            "message": (
                f"{len(jobs)} job(s) stuck beyond their age threshold: "
                + ", ".join(job["id"][:8] for job in jobs)
            ),
        }
        if _post_alert(url, payload):
            delivered.update(job["id"] for job in jobs)
    if delivered:
        with _alerted_lock:
            _alerted_job_ids.update(delivered)
        summary["alerted"] = [job["id"] for job in fresh if job["id"] in delivered]
    return summary


def _watchdog_loop(
    interval_seconds: float = CHECK_INTERVAL_SECONDS,
) -> None:
    """Sleep-scan forever; entry point for the daemon thread."""
    while True:
        time.sleep(interval_seconds)
        try:
            check_and_alert()
        except Exception:
            logger.exception("Queue watchdog iteration failed")


def reset_alert_state() -> None:
    """Clear alerted ids (tests only)."""
    with _alerted_lock:
        _alerted_job_ids.clear()
