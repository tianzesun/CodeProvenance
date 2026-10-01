"""Guest demo session regression tests.

Guest login deliberately re-opens the anonymous compute surface that
``ALLOW_ANONYMOUS_ANALYSIS`` closed, while promising to save nothing. These
tests pin down each half of that promise:

* the session is a real, server-signed cookie whose principal owns no
  workspace and never reaches the ``User`` table;
* that principal can only reach jobs it created itself;
* guest jobs are written nowhere — no metadata file, no ``Report`` row, no
  ``SessionLocal`` at all — and are swept from memory and disk when the TTL
  elapses;
* a guest may read, but its only permitted write is uploading files.
"""

import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.settings import settings

AUTH_COOKIE_NAME = server.AUTH_COOKIE_NAME


class _NullThread:
    """Thread stand-in that never runs, so tests stay deterministic."""

    def __init__(self, **kwargs) -> None:
        """Record the thread's kwargs for assertions."""
        self.kwargs = kwargs

    def start(self) -> None:
        """Do nothing — no daemon sweeper races the assertions below."""


@pytest.fixture(autouse=True)
def _no_background_sweeper(monkeypatch) -> None:
    """Replace ``threading`` for the module under test.

    The guest endpoint starts a daemon sweeper on first use. Letting it run
    would make the expiry tests race a 30-second timer; stubbing it keeps every
    sweep explicit.
    """
    monkeypatch.setattr(server, "threading", SimpleNamespace(Thread=_NullThread))


def _make_request(
    method: str = "GET", path: str = "/api/auth/me", cookie: str = ""
) -> Request:
    """Build a bare ASGI request carrying an optional session cookie."""
    headers = []
    if cookie:
        headers.append((b"cookie", f"{AUTH_COOKIE_NAME}={cookie}".encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 80),
        "state": {},
    }
    return Request(scope)


def _guest_client() -> TestClient:
    """Return a TestClient that already holds a fresh guest session cookie."""
    client = TestClient(server.app)
    response = client.post("/api/auth/guest")
    assert response.status_code == 200, response.text
    return client


class TestGuestSessionIssuance:
    """``POST /api/auth/guest`` must mint a workspace-less principal."""

    def test_guest_login_returns_a_guest_without_a_workspace(self) -> None:
        client = TestClient(server.app)

        response = client.post("/api/auth/guest")

        assert response.status_code == 200, response.text
        user = response.json()["user"]
        assert user["role"] == "guest"
        assert user["is_guest"] is True
        assert user["tenant_id"] is None
        assert user["tenant_name"] is None
        # The cookie rides back on the response, HttpOnly, like a user session.
        assert AUTH_COOKIE_NAME in client.cookies

    def test_guest_cookie_authenticates_subsequent_requests(self) -> None:
        client = _guest_client()

        response = client.get("/api/auth/me")

        assert response.status_code == 200, response.text
        user = response.json()["user"]
        assert user["role"] == "guest"
        assert user["is_guest"] is True

    def test_guest_login_is_disabled_by_configuration(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "GUEST_LOGIN_ENABLED", False)

        client = TestClient(server.app)
        response = client.post("/api/auth/guest")

        assert response.status_code == 403

    def test_guest_endpoint_stays_on_the_public_surface(self) -> None:
        """The endpoint is public; everything it unlocks still requires auth."""
        assert "/api/auth/guest" in server.PUBLIC_PATHS
        assert server._should_require_auth("/api/auth/guest") is False
        assert server._should_require_auth("/api/job/some-job") is True


class TestGuestTokenValidation:
    """Guest tokens decode without a ``User`` row and honour the feature flag."""

    def test_guest_token_never_queries_the_user_table(self, monkeypatch) -> None:
        token = server._create_guest_token("guest-abc123")
        request = _make_request(cookie=token)

        def explode():  # pragma: no cover - fails loudly if a DB is opened
            raise AssertionError("guest authentication opened a database session")

        monkeypatch.setattr(server, "SessionLocal", explode)

        user = server._authenticate_request(request)

        assert user["is_guest"] is True
        assert user["id"] == "guest-abc123"
        assert user["role"] == "guest"

    def test_guest_token_is_rejected_once_the_feature_is_disabled(
        self, monkeypatch
    ) -> None:
        token = server._create_guest_token("guest-abc123")
        request = _make_request(cookie=token)
        monkeypatch.setattr(settings, "GUEST_LOGIN_ENABLED", False)

        with pytest.raises(HTTPException) as excinfo:
            server._authenticate_request(request)

        assert excinfo.value.status_code == 401

    def test_user_tokens_still_fall_through_to_the_user_lookup(
        self, monkeypatch
    ) -> None:
        """The guest branch must not swallow a normal session token."""
        user_token = server.jwt.encode(
            {"sub": "someone-else", "role": "professor"},
            server.settings.AUTH_JWT_SECRET,
            algorithm="HS256",
        )
        lookups: list[bool] = []

        class _FakeSession:
            """Stands in for the DB session, reporting no such user."""

            def __enter__(self):
                lookups.append(True)
                return self

            def __exit__(self, *exc) -> bool:
                return False

            def scalar(self, *_args, **_kwargs):
                return None

        monkeypatch.setattr(server, "SessionLocal", _FakeSession)

        with pytest.raises(HTTPException) as excinfo:
            server._authenticate_request(_make_request(cookie=user_token))

        assert excinfo.value.status_code == 401
        assert lookups, "a non-guest token must still be checked against the User table"


class TestGuestWriteGuard:
    """A guest may read, but its only permitted write is an upload."""

    def test_guest_cannot_list_workspace_jobs(self) -> None:
        client = _guest_client()

        response = client.get("/api/jobs")

        assert response.status_code == 403, response.text
        assert "sign in" in response.json()["detail"].lower()

    def test_guest_cannot_record_a_review_decision(self) -> None:
        client = _guest_client()

        response = client.patch(
            "/api/job/some-job/review", json={"review_status": "confirmed"}
        )

        assert response.status_code == 403, response.text

    def test_guest_post_to_a_management_endpoint_is_rejected(self) -> None:
        """The middleware guard fires before the handler, not inside it."""
        client = _guest_client()

        response = client.post("/api/admin/users", json={})

        assert response.status_code == 403, response.text
        assert "guest" in response.json()["detail"].lower()

    def test_guest_reads_are_allowed(self) -> None:
        client = _guest_client()

        assert client.get("/api/auth/me").status_code == 200
        # Reads are allowed by the write guard, but the endpoint's own access
        # policy still decides what a guest may actually see.
        assert client.get("/api/courses").status_code in (200, 403)

    def test_upload_endpoints_remain_writable_for_guests(self) -> None:
        assert "/api/upload" in server.GUEST_WRITE_EXEMPT_PATHS
        assert "/api/upload-zip" in server.GUEST_WRITE_EXEMPT_PATHS
        assert "/api/auth/refresh" in server.GUEST_WRITE_EXEMPT_PATHS

    def test_professor_sessions_are_not_affected_by_the_guard(self) -> None:
        """A real session writes exactly as before — no guest flag, no 403."""
        assert (
            server._is_guest_principal(
                {"id": "p1", "role": "professor", "tenant_id": "t1"}
            )
            is False
        )

        request = _make_request()
        request.state.user = {"id": "p1", "role": "professor", "tenant_id": "t1"}

        assert server._require_non_guest(request)["id"] == "p1"


class TestGuestJobAccess:
    """Guests see their own run and nothing else, in either direction."""

    def setup_method(self) -> None:
        """Build the principals and job shapes used across the cases."""
        self.guest = server._guest_principal("guest-abc")
        self.other_guest = server._guest_principal("guest-zzz")
        self.own_job = {
            "id": "j-own",
            "guest": True,
            "owner_user_id": "guest-abc",
            "tenant_id": None,
        }
        self.foreign_guest_job = {
            "id": "j-foreign",
            "guest": True,
            "owner_user_id": "guest-zzz",
            "tenant_id": None,
        }
        self.workspace_job = {
            "id": "j-workspace",
            "owner_user_id": "prof-1",
            "tenant_id": "tenant-1",
        }

    def test_guest_reaches_only_the_job_it_created(self) -> None:
        assert server._job_is_accessible(self.own_job, self.guest) is True
        assert server._job_is_accessible(self.foreign_guest_job, self.guest) is False
        assert server._job_is_accessible(self.workspace_job, self.guest) is False

    def test_workspace_users_cannot_reach_guest_jobs(self) -> None:
        professor = {"id": "prof-1", "role": "professor", "tenant_id": "tenant-1"}
        other_professor = {"id": "prof-2", "role": "professor", "tenant_id": "tenant-2"}
        assert server._job_is_accessible(self.own_job, professor) is False
        assert server._job_is_accessible(self.own_job, other_professor) is False

    def test_admins_keep_their_unrestricted_view(self) -> None:
        admin = {"id": "admin-1", "role": "admin", "tenant_id": "tenant-1"}
        assert server._job_is_accessible(self.own_job, admin) is True

    def test_guest_job_flags_are_only_set_for_guests(self) -> None:
        flags = server._guest_job_flags(self.guest)
        assert flags["guest"] is True
        assert flags["guest_expires_at"] > time.time()

        assert server._guest_job_flags(None) == {}
        assert server._guest_job_flags({"id": "prof-1", "role": "professor"}) == {}

    def test_first_poll_after_upload_is_already_authorized(
        self, monkeypatch, tmp_path
    ) -> None:
        """The UI polls the instant the upload returns — no ownership race.

        The background analysis stamps ``owner_user_id`` when it rebuilds the
        job, which starts *after* the response is sent. Ownership therefore has
        to exist on the seeded job too, or that very first poll would be denied
        and the guest would see "Job not found" for a job they just created.
        """
        # Keep the heavy analysis out of the test: only the seeded job matters.
        monkeypatch.setattr(server, "_run_analysis_background", lambda *a, **k: None)
        monkeypatch.setattr(server, "_jobs", dict(server._jobs))
        monkeypatch.setattr(server, "UPLOADS_DIR", tmp_path / "uploads")
        monkeypatch.setattr(
            server, "_job_report_dir", lambda job_id: tmp_path / "reports" / job_id
        )

        client = _guest_client()
        session_user = client.get("/api/auth/me").json()["user"]
        response = client.post(
            "/api/upload",
            files=[
                ("files", ("a.py", "print('a')\n", "text/x-python")),
                ("files", ("b.py", "print('b')\n", "text/x-python")),
            ],
            data={
                "course_name": "Demo",
                "assignment_name": "Demo",
                "engine_keys": "token",
            },
            timeout=30,
        )

        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]

        poll = client.get(f"/api/job/{job_id}")

        assert poll.status_code == 200, poll.text
        assert poll.json()["guest"] is True
        assert poll.json()["owner_user_id"] == session_user["id"]

    def test_guest_uploads_never_enable_external_source_scanning(
        self, monkeypatch, tmp_path
    ) -> None:
        """A demo run must not spend the deployment's external API quota.

        The upload form can ask for GitHub / Stack Overflow source scanning;
        the server forces it off for a guest, because the override is the
        highest-priority switch and those keys belong to the workspace.
        """
        monkeypatch.setattr(server, "_run_analysis_background", lambda *a, **k: None)
        monkeypatch.setattr(server, "_jobs", dict(server._jobs))
        monkeypatch.setattr(server, "UPLOADS_DIR", tmp_path / "uploads")
        monkeypatch.setattr(
            server, "_job_report_dir", lambda job_id: tmp_path / "reports" / job_id
        )
        client = _guest_client()

        response = client.post(
            "/api/upload",
            files=[
                ("files", ("a.py", "print('a')\n", "text/x-python")),
                ("files", ("b.py", "print('b')\n", "text/x-python")),
            ],
            data={"source_scan_enabled": "true"},
            timeout=30,
        )

        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        assert server._jobs[job_id]["source_scan_enabled_override"] is False

    def test_uploaded_guest_job_stays_visible_until_the_sweeper_runs(
        self, monkeypatch, tmp_path
    ) -> None:
        """A guest reaches its own job through the alias route as well."""
        monkeypatch.setitem(
            server._jobs,
            "guest-job-alias",
            {
                "id": "guest-job-alias",
                "guest": True,
                "guest_expires_at": time.time() + 60,
                "owner_user_id": "guest-abc",
                "tenant_id": None,
                "status": "processing",
            },
        )
        request = _make_request()
        request.state.user = server._guest_principal("guest-abc")

        assert server._require_job_access("guest-job-alias", request)["id"] == (
            "guest-job-alias"
        )


class TestGuestJobsAreNeverPersisted:
    """No metadata file, no report row, no database session."""

    def test_persist_job_writes_no_metadata_for_a_guest_job(
        self, monkeypatch, tmp_path
    ) -> None:
        metadata_path = tmp_path / "metadata.json"
        monkeypatch.setattr(server, "_job_metadata_path", lambda job_id: metadata_path)
        monkeypatch.setitem(
            server._jobs,
            "guest-job-1",
            {"id": "guest-job-1", "guest": True, "status": "completed", "results": []},
        )

        server._persist_job("guest-job-1")

        assert not metadata_path.exists()
        # Normalisation still runs, so the in-memory job stays queryable.
        assert server._jobs["guest-job-1"]["guest"] is True

    def test_persist_job_still_writes_metadata_for_workspace_jobs(
        self, monkeypatch, tmp_path
    ) -> None:
        metadata_path = tmp_path / "metadata.json"
        monkeypatch.setattr(server, "_job_metadata_path", lambda job_id: metadata_path)
        monkeypatch.setitem(
            server._jobs,
            "real-job-1",
            {
                "id": "real-job-1",
                "tenant_id": "tenant-1",
                "status": "completed",
                "results": [],
            },
        )

        server._persist_job("real-job-1")

        assert metadata_path.exists()

    def test_report_records_are_skipped_for_guest_jobs(self, monkeypatch) -> None:
        monkeypatch.setitem(
            server._jobs, "guest-job-2", {"id": "guest-job-2", "guest": True}
        )

        def explode(*args, **kwargs):  # pragma: no cover - the guard must win
            raise AssertionError("guest report reached the database")

        monkeypatch.setattr(server, "SessionLocal", explode)

        # Returning at all proves no DB session was opened.
        assert (
            server._persist_report_record(
                "guest-job-2", "report", "html", "/tmp/x.html"
            )
            is None
        )

    def test_report_records_still_reach_the_database_for_workspace_jobs(
        self, monkeypatch
    ) -> None:
        monkeypatch.setitem(
            server._jobs, "real-job-2", {"id": "real-job-2", "tenant_id": "tenant-1"}
        )

        def explode(*args, **kwargs):  # pragma: no cover - proves the path is live
            raise AssertionError("control case never opened the database")

        monkeypatch.setattr(server, "SessionLocal", explode)

        with pytest.raises(AssertionError):
            server._persist_report_record("real-job-2", "report", "html", "/tmp/x.html")


class TestGuestJobSweeper:
    """Guest results live only as long as the session that produced them."""

    def _prepare_dirs(self, tmp_path):
        uploads = tmp_path / "uploads"
        reports = tmp_path / "reports"
        (uploads / "g1").mkdir(parents=True)
        (reports / "g1").mkdir(parents=True)
        (uploads / "g1" / "sample.py").write_text("print('hi')", encoding="utf-8")
        (reports / "g1" / "report.html").write_text("<html></html>", encoding="utf-8")
        return uploads, reports

    def test_expired_guest_job_is_removed_from_memory_and_disk(
        self, monkeypatch, tmp_path
    ) -> None:
        uploads, reports = self._prepare_dirs(tmp_path)
        monkeypatch.setattr(server, "UPLOADS_DIR", uploads)
        monkeypatch.setattr(server, "_job_report_dir", lambda job_id: reports / job_id)
        monkeypatch.setitem(
            server._jobs,
            "g1",
            {"id": "g1", "guest": True, "guest_expires_at": 100.0},
        )

        removed = server._sweep_expired_guest_jobs(now=200.0)

        assert removed == 1
        assert "g1" not in server._jobs
        assert not (uploads / "g1").exists()
        assert not (reports / "g1").exists()

    def test_live_guest_jobs_and_workspace_jobs_are_left_alone(
        self, monkeypatch, tmp_path
    ) -> None:
        uploads, reports = self._prepare_dirs(tmp_path)
        monkeypatch.setattr(server, "UPLOADS_DIR", uploads)
        monkeypatch.setattr(server, "_job_report_dir", lambda job_id: reports / job_id)
        monkeypatch.setitem(
            server._jobs,
            "g1",
            {"id": "g1", "guest": True, "guest_expires_at": 9_999_999_999.0},
        )
        monkeypatch.setitem(
            server._jobs,
            "ws1",
            {"id": "ws1", "tenant_id": "tenant-1", "owner_user_id": "prof-1"},
        )

        removed = server._sweep_expired_guest_jobs(now=200.0)

        assert removed == 0
        assert "g1" in server._jobs
        assert "ws1" in server._jobs
        assert (uploads / "g1").exists()

    def test_sweeper_starts_only_once_a_guest_session_exists(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_GUEST_SWEEPER_STARTED", False)
        started = []
        monkeypatch.setattr(
            server.threading,
            "Thread",
            lambda **kwargs: started.append(kwargs)
            or type("FakeThread", (), {"start": lambda self: None})(),
        )

        server._ensure_guest_sweeper()
        server._ensure_guest_sweeper()

        assert len(started) == 1


class TestGuestReadsSkipWorkspaceQueries:
    """The demo's landing page must not query another workspace's registry."""

    def test_courses_and_assignments_answer_before_the_policy_query(
        self, monkeypatch
    ) -> None:
        """``/api/courses`` and ``/api/assignments`` short-circuit for guests.

        The shared visibility policy compares ``user.id`` against a UUID
        column; a guest id would be rejected by the database (and logged as an
        error on every page load) instead of returning the empty list a demo
        session is entitled to.
        """
        policy_calls: list[object] = []
        original = server.academic_access.visible_course_id_query

        def spy(db, user):
            policy_calls.append(user)
            return original(db, user)

        monkeypatch.setattr(server.academic_access, "visible_course_id_query", spy)
        client = _guest_client()

        courses = client.get("/api/courses")
        assignments = client.get("/api/assignments")

        assert courses.status_code == 200, courses.text
        assert courses.json() == {"courses": []}
        assert assignments.status_code == 200, assignments.text
        assert assignments.json() == {"assignments": []}
        assert policy_calls == [], "the guest must never reach the policy query"
