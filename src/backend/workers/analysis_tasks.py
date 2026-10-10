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
import logging
from pathlib import Path
from typing import Any

from src.backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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

    Returns:
        Mapping with the job id and final status (``completed``).
    """
    # Local import: pulling ``server`` at module scope wouldboot the whole
    # API app inside every Celery worker prefork child before the broker
    # connection is even established, and creates import cycles in tests.
    from src.backend.api import server

    current_user: dict[str, Any] | None = None
    if owner_user_id or tenant_id:
        current_user = {"id": owner_user_id, "tenant_id": tenant_id}

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
    except Exception:
        logger.exception("Celery analysis failed for job %s", job_id)
        raise
    return {"job_id": job_id, "status": "completed"}
