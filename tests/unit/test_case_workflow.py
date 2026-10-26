"""Case linking and status rules (cases router + CaseService)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings as app_settings
from src.backend.models.database import (
    Assignment,
    Case,
    CaseResultLink,
    Course,
    Job,
    Organization,
    SimilarityResult,
    TimelineEvent,
    User,
)


def _ids() -> dict[str, str]:
    return {
        name: str(uuid.uuid4())
        for name in (
            "org_mine",
            "org_other",
            "course_mine",
            "course_other",
            "assignment_mine",
            "assignment_other",
            "job_mine",
            "job_other",
            "result_mine",
            "result_other",
            "user",
        )
    }


@pytest.fixture
def seeded(job_tenant_id):
    ids = _ids()
    with SessionLocal() as db:
        for org in ("org_mine", "org_other"):
            db.add(Organization(id=ids[org], name=f"Case test {ids[org]}"))
        db.flush()
        for side in ("mine", "other"):
            db.add(
                Course(
                    id=ids[f"course_{side}"],
                    organization_id=ids[f"org_{side}"],
                    name=f"Case test course {side}",
                )
            )
            db.flush()
            db.add(
                Assignment(
                    id=ids[f"assignment_{side}"],
                    course_id=ids[f"course_{side}"],
                    name=f"Case test assignment {side}",
                )
            )
            db.flush()
            db.add(
                Job(
                    id=ids[f"job_{side}"],
                    tenant_id=job_tenant_id,
                    name="case test",
                    status="completed",
                    assignment_id=ids[f"assignment_{side}"],
                )
            )
            db.flush()
            db.add(
                SimilarityResult(
                    id=ids[f"result_{side}"],
                    job_id=ids[f"job_{side}"],
                    submission_a_id="a.py",
                    submission_b_id="b.py",
                    similarity_score=0.9,
                )
            )
        db.add(
            User(
                id=ids["user"],
                organization_id=ids["org_mine"],
                email=f"case-test-{ids['user']}@example.com",
                full_name="Case Test",
                password_hash="x",
                role="professor",
                is_active=True,
            )
        )
        db.commit()
    try:
        yield ids
    finally:
        with SessionLocal() as db:
            case_ids = [
                c.id
                for c in db.query(Case).filter(Case.organization_id == ids["org_mine"])
            ]
            if case_ids:
                db.query(TimelineEvent).filter(
                    TimelineEvent.case_id.in_(case_ids)
                ).delete(synchronize_session=False)
                db.query(CaseResultLink).filter(
                    CaseResultLink.case_id.in_(case_ids)
                ).delete(synchronize_session=False)
                db.query(Case).filter(Case.id.in_(case_ids)).delete(
                    synchronize_session=False
                )
            for side in ("mine", "other"):
                db.query(SimilarityResult).filter(
                    SimilarityResult.id == ids[f"result_{side}"]
                ).delete()
                db.query(Job).filter(Job.id == ids[f"job_{side}"]).delete()
                db.query(Assignment).filter(
                    Assignment.id == ids[f"assignment_{side}"]
                ).delete()
                db.query(Course).filter(Course.id == ids[f"course_{side}"]).delete()
            db.query(User).filter(User.id == ids["user"]).delete()
            for org in ("org_mine", "org_other"):
                db.query(Organization).filter(Organization.id == ids[org]).delete()
            db.commit()


@pytest.fixture
def client(seeded, monkeypatch) -> TestClient:
    user = {
        "id": seeded["user"],
        "role": "professor",
        "tenant_id": None,
        "organization_id": seeded["org_mine"],
    }
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(user))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": user["id"], "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    test_client = TestClient(server.app)
    test_client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return test_client


def _new_case(client: TestClient) -> str:
    response = client.post("/api/cases", json={"title": "Case test"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_only_results_from_the_callers_organization_can_be_linked(
    client, seeded
) -> None:
    case_id = _new_case(client)

    def link(result_id: str) -> int:
        return client.post(
            f"/api/cases/{case_id}/link", json={"result_id": result_id}
        ).status_code

    assert link(seeded["result_other"]) == 404
    assert link(str(uuid.uuid4())) == 404  # unknown id: was a 500
    assert link(seeded["result_mine"]) == 201
    assert link(seeded["result_mine"]) == 201  # idempotent, not a duplicate

    body = client.get(f"/api/cases/{case_id}").json()
    assert body["result_ids"] == [seeded["result_mine"]]


def test_assigning_a_reviewer_does_not_reopen_a_closed_case(client, seeded) -> None:
    case_id = _new_case(client)

    closed = client.patch(
        f"/api/cases/{case_id}",
        json={"status": "CLOSED", "investigator_id": seeded["user"]},
    ).json()
    assert closed["status"] == "CLOSED"
    assert closed["closed_at"]

    reassigned = client.post(
        f"/api/cases/{case_id}/assign", json={"reviewer_id": seeded["user"]}
    ).json()
    assert reassigned["status"] == "CLOSED"

    reopened = client.patch(f"/api/cases/{case_id}", json={"status": "OPEN"}).json()
    assert reopened["status"] == "OPEN"
    assert not reopened["closed_at"]
