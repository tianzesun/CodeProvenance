"""Shared integration fixtures: a test client signed in as a throwaway professor.

Analysis and benchmark endpoints require a dashboard session or an API key.
``signed_in_client`` creates a workspace and a professor in the configured
database, issues a session the same way sign-in does
(``server._create_access_token``), and removes the rows afterwards.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


def _db_available() -> bool:
    """Check whether the configured database is reachable."""
    try:
        from sqlalchemy import text

        from src.backend.config.database import SessionLocal

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _create_professor() -> tuple[str, str, str]:
    """Create a workspace and an active professor in it.

    Returns:
        The user id, the workspace (tenant) id, and a session token for the user.
    """
    from src.backend.api import server
    from src.backend.config.database import SessionLocal
    from src.backend.infrastructure.security import hash_password
    from src.backend.models.database import User

    with SessionLocal() as db:
        tenant = server._create_tenant(db, f"integration-tests-{uuid.uuid4().hex[:8]}")
        user = User(
            tenant_id=tenant.id,
            email=f"integration-{uuid.uuid4().hex}@example.invalid",
            full_name="Integration Test Professor",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="professor",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id), str(tenant.id), server._create_access_token(user)


def _delete_professor(user_id: str, tenant_id: str) -> None:
    """Remove the professor, the workspace and its jobs (best effort)."""
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import (
            Job,
            SimilarityResult,
            Submission,
            Tenant,
            User,
        )

        with SessionLocal() as db:
            job_ids = [
                row.id for row in db.query(Job.id).filter(Job.tenant_id == tenant_id)
            ]
            if job_ids:
                db.query(SimilarityResult).filter(
                    SimilarityResult.job_id.in_(job_ids)
                ).delete(synchronize_session=False)
                db.query(Submission).filter(Submission.job_id.in_(job_ids)).delete(
                    synchronize_session=False
                )
                db.query(Job).filter(Job.id.in_(job_ids)).delete(
                    synchronize_session=False
                )
            db.query(User).filter(User.id == user_id).delete()
            db.query(Tenant).filter(Tenant.id == tenant_id).delete()
            db.commit()
    except Exception:
        logger.warning(
            "Could not remove integration test workspace %s", tenant_id, exc_info=True
        )


@pytest.fixture(scope="module")
def signed_in_client() -> Iterator[TestClient]:
    """A client for the real API app, signed in as a throwaway professor."""
    if not _db_available():
        pytest.skip("Database is not reachable — skipping database-dependent tests")

    from src.backend.api import server

    user_id, tenant_id, token = _create_professor()
    try:
        with TestClient(server.app) as client:
            client.cookies.set(server.AUTH_COOKIE_NAME, token)
            yield client
    finally:
        _delete_professor(user_id, tenant_id)
