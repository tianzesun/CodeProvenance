"""The v1 job API applies per-person access to dashboard sessions."""

import types
import uuid

import pytest
from fastapi import HTTPException

from src.backend.api import server
from src.backend.api.routes import analyze
from src.backend.application.services import sharing

JOB_ID = uuid.uuid4()
OWNER = {"id": str(uuid.uuid4()), "role": "professor", "tenant_id": "t1"}
COLLEAGUE = {"id": str(uuid.uuid4()), "role": "professor", "tenant_id": "t1"}
API_KEY = {"id": "", "role": "api", "tenant_id": "t1"}


def _request(user):
    return types.SimpleNamespace(state=types.SimpleNamespace(user=user, tenant_id="t1"))


@pytest.fixture
def owned_job(monkeypatch):
    """A job in workspace t1 owned by OWNER, shared with nobody."""
    shared: set[str] = set()
    monkeypatch.setattr(
        server, "_get_job", lambda job_id: {"id": job_id, "owner_user_id": OWNER["id"]}
    )
    monkeypatch.setattr(
        sharing,
        "access_scope",
        lambda db, user: sharing.AccessScope(
            user_id=user["id"],
            tenant_id="t1",
            organization_id="org-1",
            is_admin=False,
            shared_job_ids=frozenset(shared),
        ),
    )
    return shared


def test_the_owner_keeps_access(owned_job) -> None:
    analyze._require_session_job_access(_request(OWNER), JOB_ID)


def test_a_colleague_in_the_same_workspace_gets_404(owned_job) -> None:
    with pytest.raises(HTTPException) as exc:
        analyze._require_session_job_access(_request(COLLEAGUE), JOB_ID)
    assert exc.value.status_code == 404


def test_sharing_the_job_lets_the_colleague_in(owned_job) -> None:
    owned_job.add(str(JOB_ID))
    analyze._require_session_job_access(_request(COLLEAGUE), JOB_ID)


def test_api_keys_keep_workspace_scope(owned_job) -> None:
    analyze._require_session_job_access(_request(API_KEY), JOB_ID)
    analyze._require_session_job_access(_request(None), JOB_ID)


@pytest.mark.parametrize(
    ("endpoint", "kwargs"),
    [
        (analyze.get_job_status, {"include_results": False}),
        (analyze.get_job_results, {"threshold": None, "limit": 10, "offset": 0}),
        (analyze.get_job_report, {"report_format": "json"}),
    ],
)
def test_every_v1_job_endpoint_applies_the_rule(
    owned_job, monkeypatch, endpoint, kwargs
) -> None:
    monkeypatch.setattr(analyze, "get_current_tenant", lambda request: "t1")
    monkeypatch.setattr(analyze, "set_tenant_context", lambda db, tenant_id: None)
    monkeypatch.setattr(
        analyze.JobService,
        "get_job_by_id",
        staticmethod(lambda db, job_id, tenant_id: object()),
    )

    with pytest.raises(HTTPException) as exc:
        endpoint(JOB_ID, _request(COLLEAGUE), db=None, **kwargs)
    assert exc.value.status_code == 404
