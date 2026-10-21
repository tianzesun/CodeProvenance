"""Poll-time job status refresh (worker in another process).

``_get_job`` serves the upload page's once-per-second poll. The analysis
usually runs in a Celery worker process that advances job.json and the
jobs row but can never mutate this process's in-memory ``_jobs`` cache;
before the refresh existed, a cached job stayed ``queued`` forever and
the page never left "Queued for analysis" after the run had finished.

These tests pin the refresh decision matrix:

* a strictly further-along re-read is adopted (the reported bug);
* same-rank progress is adopted only when newer (live inline runs win ties);
* an unchanged guest row never pays for a full database reconstruction;
* terminal cache entries are final and trigger no I/O at all.
"""

import uuid

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.models.database import Job


def _seed(job_id: str, status: str, progress: dict | None = None) -> None:
    """Put a job dict into the in-memory cache as the upload endpoint would."""
    job = {"id": job_id, "status": status}
    if progress is not None:
        job["progress"] = progress
    server._jobs[job_id] = job


def _forget(*job_ids: str) -> None:
    """Drop test jobs from the in-memory cache."""
    for job_id in job_ids:
        server._jobs.pop(job_id, None)


def _insert_row(job_id: str, status: str) -> None:
    """Insert a jobs row as the worker process would leave it."""
    with SessionLocal() as db:
        db.add(Job(id=job_id, name="poll refresh test", status=status))
        db.commit()


def _set_row_status(job_id: str, status: str) -> None:
    """Advance a jobs row's status, as another process would."""
    with SessionLocal() as db:
        db.query(Job).filter(Job.id == job_id).update({"status": status})
        db.commit()


def _delete_row(job_id: str) -> None:
    """Remove a test jobs row."""
    with SessionLocal() as db:
        db.query(Job).filter(Job.id == job_id).delete()
        db.commit()


class TestCachedJobFollowsTheWorker:
    """A cached open job re-reads its status from the shared stores."""

    def test_cached_queued_job_sees_the_workers_db_completion(self) -> None:
        # The reported bug: guest run executed by the Celery worker, whose
        # only cross-process channel (no job.json for guests) is the row.
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(job_id, "queued")
        _insert_row(job_id, "completed")
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["status"] == "completed"
            assert server._jobs[job_id]["status"] == "completed"
        finally:
            _forget(job_id)
            _delete_row(job_id)

    def test_failure_in_the_worker_reaches_the_cached_copy(self) -> None:
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(job_id, "queued")
        _insert_row(job_id, "failed")
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["status"] == "failed"
        finally:
            _forget(job_id)
            _delete_row(job_id)

    def test_unchanged_row_never_pays_for_a_full_reconstruction(
        self, monkeypatch
    ) -> None:
        # Guest mid-run: the probe reports the same rank, so the heavy
        # database reconstruction (submissions, sources, results) must not
        # run on every poll.
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(job_id, "queued")
        _insert_row(job_id, "queued")

        def _explode(_job_id: str) -> None:
            raise AssertionError("full DB load must not run while nothing changed")

        monkeypatch.setattr(server, "_load_job_from_db", _explode)
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["status"] == "queued"
        finally:
            _forget(job_id)
            _delete_row(job_id)

    def test_terminal_cache_skips_the_refresh_entirely(self, monkeypatch) -> None:
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(job_id, "completed")

        def _explode(_job_id: str) -> None:
            raise AssertionError("a finished cached job must not be re-read")

        monkeypatch.setattr(server, "_read_job_status_from_db", _explode)
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["status"] == "completed"
        finally:
            _forget(job_id)


class TestInlineRunProtection:
    """Same-rank refreshes lose ties to the live in-process copy."""

    def test_newer_cached_progress_is_kept(self, monkeypatch) -> None:
        # Inline mode (no broker): this process owns the live dict; the
        # on-disk snapshot lags between stage changes and must not win.
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(
            job_id,
            "analyzing",
            progress={
                "stage": "comparing_submissions",
                "updated_at": "2026-10-21T10:00:05",
            },
        )

        monkeypatch.setattr(
            server,
            "_load_persisted_job",
            lambda _j: {
                "id": job_id,
                "status": "analyzing",
                "progress": {
                    "stage": "reading_submissions",
                    "updated_at": "2026-10-21T10:00:01",
                },
            },
        )
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["progress"]["stage"] == "comparing_submissions"
            assert server._jobs[job_id]["progress"]["stage"] == "comparing_submissions"
        finally:
            _forget(job_id)

    def test_newer_fresh_progress_is_adopted(self, monkeypatch) -> None:
        # Cross-process non-guest run: job.json carries a later stage than
        # the stale cached copy — the worker's view wins.
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(
            job_id,
            "analyzing",
            progress={
                "stage": "reading_submissions",
                "updated_at": "2026-10-21T10:00:01",
            },
        )

        monkeypatch.setattr(
            server,
            "_load_persisted_job",
            lambda _j: {
                "id": job_id,
                "status": "analyzing",
                "progress": {
                    "stage": "comparing_submissions",
                    "updated_at": "2026-10-21T10:00:05",
                },
            },
        )
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["progress"]["stage"] == "comparing_submissions"
            assert server._jobs[job_id]["progress"]["stage"] == "comparing_submissions"
        finally:
            _forget(job_id)


class TestAdoptionPreservesIdentity:
    """A re-read copy refreshes state, never ownership."""

    def test_adoption_keeps_guest_ownership_keys(self, monkeypatch) -> None:
        # The report-recovery path cannot reconstruct the in-memory-only
        # guest identity; adopting it wholesale made _job_is_accessible
        # deny the polling session and turned its completion poll into a
        # 404.
        job_id = f"poll-refresh-{uuid.uuid4().hex[:10]}"
        _seed(job_id, "analyzing")
        server._jobs[job_id]["guest"] = True
        server._jobs[job_id]["owner_user_id"] = "guest-abc123"

        monkeypatch.setattr(
            server,
            "_load_persisted_job",
            # The real recovery path stamps owner_user_id=None via
            # _normalize_job — an explicit empty, not a missing key.
            lambda _j: {"id": job_id, "status": "completed", "owner_user_id": None},
        )
        try:
            refreshed = server._get_job(job_id)

            assert refreshed is not None
            assert refreshed["status"] == "completed"
            assert refreshed["guest"] is True
            assert refreshed["owner_user_id"] == "guest-abc123"
        finally:
            _forget(job_id)
