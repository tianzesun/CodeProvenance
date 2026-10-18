"""Unit tests for the async AI-detection job and the code-LM cache."""

from src.backend.api import server
from src.backend.engines.ai.perplexity import (
    PerplexityScorer,
    _TRANSFORMER_CACHE,
    _load_cached_transformer,
)


class TestTransformerCache:
    """Loaded code LMs are cached process-wide and shared across scorers."""

    def test_cache_hit_returns_same_objects_without_reload(self) -> None:
        sentinel_tokenizer = object()
        sentinel_model = object()
        _TRANSFORMER_CACHE["cache/test-model"] = (sentinel_tokenizer, sentinel_model)
        try:
            loaded = _load_cached_transformer("cache/test-model")
            assert loaded == (sentinel_tokenizer, sentinel_model)
        finally:
            del _TRANSFORMER_CACHE["cache/test-model"]

    def test_scorers_share_the_cached_model(self) -> None:
        sentinel_tokenizer = object()
        sentinel_model = object()
        _TRANSFORMER_CACHE["cache/test-model"] = (sentinel_tokenizer, sentinel_model)
        try:
            first = PerplexityScorer(model_path="cache/test-model")
            second = PerplexityScorer(model_path="cache/test-model")
            assert first._transformer_available
            assert second._transformer_available
            assert first._huggingface is sentinel_model
            assert second._huggingface is sentinel_model
            assert first._tokenizer is sentinel_tokenizer
        finally:
            del _TRANSFORMER_CACHE["cache/test-model"]


class TestFinalizeAIDetectionJob:
    """The background finalizer drives the ai_detector job lifecycle."""

    def _seed_job(self, job_id: str) -> None:
        server._jobs[job_id] = {
            "id": job_id,
            "job_type": "ai_detector",
            "status": "processing",
            "summary": {
                "total_files": 1,
                "flagged_files": 0,
                "highest_ai_probability": 0.0,
                "average_ai_probability": 0.0,
            },
        }

    def test_completed_job_populates_summary_and_ai_detection(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(server, "_persist_job", lambda job_id: None)
        monkeypatch.setattr(
            server, "_persist_ai_detection_results", lambda job_id, summary: None
        )
        monkeypatch.setattr(
            server,
            "_build_ai_detection_summary",
            lambda submissions: {
                "flagged_count": 1,
                "highest_score": 0.9,
                "average_score": 0.6,
            },
        )
        self._seed_job("job-ok")
        try:
            server._finalize_ai_detection_job("job-ok", {"student.py": "x = 1\n" * 30})
            job = server._jobs["job-ok"]
            assert job["status"] == "completed"
            assert job["summary"]["flagged_files"] == 1
            assert job["summary"]["highest_ai_probability"] == 0.9
            assert job["ai_detection"]["average_score"] == 0.6
        finally:
            server._jobs.pop("job-ok", None)

    def test_failure_marks_job_failed(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_persist_job", lambda job_id: None)

        def boom(submissions):
            raise RuntimeError("model exploded")

        monkeypatch.setattr(server, "_build_ai_detection_summary", boom)
        self._seed_job("job-bad")
        try:
            server._finalize_ai_detection_job("job-bad", {"student.py": "x = 1\n" * 30})
            assert server._jobs["job-bad"]["status"] == "failed"
        finally:
            server._jobs.pop("job-bad", None)


class TestAssignmentResolution:
    """POST /api/ai-detect with assignment_id resolves course via organization_id.

    Regression: the endpoint compared course.tenant_id (nonexistent) against
    current_user["tenant_id"], crashing with AttributeError for every
    authenticated user who selected an assignment.
    """

    def _cookie_jar(self, user_id: str) -> dict[str, str]:
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from src.backend.api.server import AUTH_COOKIE_NAME
        from src.backend.config.settings import settings as app_settings

        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": user_id, "exp": now + timedelta(minutes=30), "iat": now},
            app_settings.auth_jwt_secret or "unit-test-secret",
            algorithm="HS256",
        )
        return {AUTH_COOKIE_NAME: token}

    def _seed_org_course_assignment(self, org_suffix: str):
        """Create org + course + assignment + user with matching organization_id."""
        import uuid as uuid_mod

        from src.backend.config.database import SessionLocal
        from src.backend.models.database import (
            Assignment,
            Course,
            Organization,
            User,
        )

        org_id = str(uuid_mod.uuid4())
        course_id = str(uuid_mod.uuid4())
        assignment_id = str(uuid_mod.uuid4())
        user_id = str(uuid_mod.uuid4())

        with SessionLocal() as db:
            db.add(Organization(id=org_id, name=f"AI-Det Org {org_suffix}"))
            db.add(
                Course(
                    id=course_id,
                    organization_id=org_id,
                    name=f"AI-Det Course {org_suffix}",
                )
            )
            db.add(
                Assignment(
                    id=assignment_id,
                    course_id=course_id,
                    name=f"AI-Det Assignment {org_suffix}",
                )
            )
            db.add(
                User(
                    id=user_id,
                    organization_id=org_id,
                    email=f"ai-detect-{org_suffix}@example.com",
                    full_name=f"AI Det {org_suffix}",
                    password_hash="x",
                    role="professor",
                    is_active=True,
                )
            )
            db.commit()
        return org_id, course_id, assignment_id, user_id

    def _cleanup(self, org_suffix: str) -> None:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import (
            Assignment,
            Course,
            Organization,
            User,
        )

        with SessionLocal() as db:
            db.query(Assignment).filter(
                Assignment.name.like(f"AI-Det Assignment {org_suffix}%")
            ).delete(synchronize_session=False)
            db.query(Course).filter(
                Course.name.like(f"AI-Det Course {org_suffix}%")
            ).delete(synchronize_session=False)
            db.query(User).filter(User.email.like(f"ai-detect-{org_suffix}-%")).delete(
                synchronize_session=False
            )
            db.query(Organization).filter(
                Organization.name.like(f"AI-Det Org {org_suffix}%")
            ).delete(synchronize_session=False)
            db.commit()

    def test_same_org_assignment_resolves_without_error(self, monkeypatch) -> None:
        """A user in the same org as the course gets a 200, not an AttributeError."""
        from fastapi.testclient import TestClient

        tag = "same-org"
        org_id, course_id, assignment_id, user_id = self._seed_org_course_assignment(
            tag
        )
        try:

            def fake_auth(*args, **kwargs):
                return {
                    "id": user_id,
                    "role": "professor",
                    "tenant_id": None,
                    "organization_id": org_id,
                }

            monkeypatch.setattr(server, "_authenticate_request", fake_auth)
            monkeypatch.setattr(server, "_finalize_ai_detection_job", lambda *a: None)

            client = TestClient(server.app)
            resp = client.post(
                "/api/ai-detect",
                data={"assignment_id": assignment_id},
                files=[
                    (
                        "files",
                        (
                            "test.py",
                            b"print('hello world this is long enough')\n",
                            "text/x-python",
                        ),
                    )
                ],
                cookies=self._cookie_jar(user_id),
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert "job_id" in body
            server._jobs.pop(body["job_id"], None)
        finally:
            self._cleanup(tag)

    def test_cross_org_assignment_returns_403(self, monkeypatch) -> None:
        """A user in a different org than the course gets 403, not a crash."""
        from fastapi.testclient import TestClient

        tag_a, tag_b = "org-a", "org-b"
        org_a, _, assignment_id, _ = self._seed_org_course_assignment(tag_a)
        org_b, _, _, user_b_id = self._seed_org_course_assignment(tag_b)
        try:

            def fake_auth(*args, **kwargs):
                return {
                    "id": user_b_id,
                    "role": "professor",
                    "tenant_id": None,
                    "organization_id": org_b,
                }

            monkeypatch.setattr(server, "_authenticate_request", fake_auth)

            client = TestClient(server.app)
            resp = client.post(
                "/api/ai-detect",
                data={"assignment_id": assignment_id},
                files=[
                    (
                        "files",
                        (
                            "test.py",
                            b"print('hello world this is long enough')\n",
                            "text/x-python",
                        ),
                    )
                ],
                cookies=self._cookie_jar(user_b_id),
            )
            assert resp.status_code == 403, resp.text
        finally:
            self._cleanup(tag_a)
            self._cleanup(tag_b)
