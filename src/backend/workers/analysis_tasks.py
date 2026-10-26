"""Celery tasks for IntegrityDesk analysis jobs.

``run_upload_analysis`` is a thin serialization boundary around the
existing synchronous ``server._run_analysis`` pipeline: the API process
persists the upload to disk, enqueues the job id plus scalar parameters,
and worker processes do the CPU-heavy comparison. Only JSON-safe scalars
cross the broker — file bytes, request objects, and live user dicts never
do (the worker re-resolves ownership from the persisted job record).

Progress polling keeps working across processes because ``_run_analysis``
already writes status/progress to the per-job ``job.json`` metadata file
on every stage, and ``server._get_job`` reads that file back. No shared
in-memory state is required.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _mark_failed_without_server(job_id: str) -> None:
    """Best-effort failed status for a job whose task could not load ``server``.

    Writes the jobs row and, when present, job.json (the two places
    ``server._get_job`` reads). Never raises: the caller re-raises the
    original error.
    """
    message = "Analysis worker failed to start; restart the worker and resubmit."
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Job

        with SessionLocal() as db:
            db_job = db.query(Job).filter(Job.id == job_id).first()
            if db_job is not None:
                db_job.status = "failed"
                db_job.failed_at = datetime.now()
                db_job.error_message = message
                db.commit()
    except Exception:
        logger.warning("Could not mark job %s failed in DB", job_id, exc_info=True)
    try:
        # Mirrors server.REPORTS_DIR / job_id / JOB_METADATA_FILENAME.
        metadata_path = (
            Path(__file__).resolve().parent.parent.parent / "reports" / job_id / "job.json"
        )
        if metadata_path.exists():
            stored = json.loads(metadata_path.read_text(encoding="utf-8"))
            stored["status"] = "failed"
            stored["error"] = message
            metadata_path.write_text(json.dumps(stored, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("Could not mark job %s failed on disk", job_id, exc_info=True)


@celery_app.task(
    name="src.backend.workers.analysis_tasks.run_upload_analysis",
    bind=True,
    max_retries=0,
    autoretry_for=(),
)
def run_upload_analysis(
    self: Any,
    job_id: str,
    job_dir: str,
    course_name: str = "",
    assignment_name: str = "",
    assignment_id: str | None = None,
    assignment_mode: str = "",
    threshold: float = 0.5,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    engine_keys_raw: str = "",
    tool_ids_raw: str = "",
    starter_sources: list[str] | None = None,
    is_guest: bool = False,
    job_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one uploaded job's analysis pipeline inside a worker process.

    Args:
        job_id: Short job identifier already inserted into the job store
            by the uploading endpoint.
        job_dir: Absolute path to the directory holding the submissions.
        course_name: Human-readable course name (may be empty).
        assignment_name: Human-readable assignment name (may be empty).
        assignment_id: Optional FK to the ``assignments`` table row.
        assignment_mode: Mode identifier string for the scoring engine.
        threshold: Similarity score threshold (0.0-1.0).
        owner_user_id: Uploader id, re-attached for ownership stamping.
        tenant_id: Uploader tenant id, re-attached for tenant scoping.
        engine_keys_raw: JSON-encoded list of engine keys to enable.
        tool_ids_raw: Comma-separated list of external tool IDs.
        starter_sources: Optional starter/template source strings.
        job_overrides: The upload's own choices (source scanning, previous
            terms). This process has no copy of the uploading process's job
            dict, so they would otherwise be lost.
        is_guest: The uploader is a guest demo session, so the job stays
            ephemeral (no tenant, no database rows).

    Returns:
        Mapping with the job id and final status (``completed``).
    """
    # Local import: pulling ``server`` at module scope wouldboot the whole
    # API app inside every Celery worker prefork child before the broker
    # connection is even established, and creates import cycles in tests.
    try:
        from src.backend.api import server
    except Exception:
        # A worker running older code than the files on disk fails here,
        # before ``server`` can record anything — the job then sat at
        # "queued" forever. Mark it failed without ``server``'s helpers.
        logger.exception("Could not load analysis server for job %s", job_id)
        _mark_failed_without_server(job_id)
        raise

    current_user: dict[str, Any] | None = None
    if owner_user_id or tenant_id or is_guest:
        current_user = {"id": owner_user_id, "tenant_id": tenant_id}
        if is_guest:
            current_user["is_guest"] = True

    # Cooperative cancellation: a job killed while queued (or redelivered
    # after a lost worker) must die here, before any heavy work. The flag
    # lives in the DB/job.json so it works across processes.
    try:
        if server._job_cancelled(job_id):
            logger.info("Skipping cancelled job %s", job_id)
            return {"job_id": job_id, "status": "cancelled", "cancelled": True}
    except Exception:
        logger.debug("Cancel-flag check failed for job %s", job_id, exc_info=True)

    if job_overrides:
        server._jobs.setdefault(job_id, {}).update(job_overrides)

    try:
        asyncio.run(
            server._run_analysis(
                job_id,
                Path(job_dir),
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
        )
    except server._JobCancelled:
        logger.info("Celery analysis cancelled for job %s", job_id)
        return {"job_id": job_id, "status": "cancelled", "cancelled": True}
    except Exception:
        logger.exception("Celery analysis failed for job %s", job_id)
        raise
    return {"job_id": job_id, "status": "completed"}
