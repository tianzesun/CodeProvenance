"""Case management API endpoints for Academic Integrity Investigation Platform."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, selectinload

from src.backend.application.services.case_service import (
    CaseService,
)
from src.backend.config.database import get_db
from src.backend.models.database import Assignment, Case, CaseComment, User

router = APIRouter()

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# Pydantic schemas
class CaseCreate(BaseModel):
    """Schema for creating a case."""

    title: str = Field(..., min_length=1, max_length=255)
    assignment_id: uuid.UUID | None = None
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|URGENT)$")


class CaseUpdate(BaseModel):
    """Schema for updating a case."""

    title: str | None = Field(None, min_length=1, max_length=255)
    status: str | None = Field(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$")
    priority: str | None = Field(None, pattern="^(LOW|MEDIUM|HIGH|URGENT)$")
    investigator_id: uuid.UUID | None = None


class CaseAssign(BaseModel):
    """Schema for assigning a reviewer."""

    reviewer_id: uuid.UUID


class CaseCommentCreate(BaseModel):
    """Schema for adding a comment."""

    body: str = Field(..., min_length=1, max_length=10_000)

    @field_validator("body")
    @classmethod
    def _body_not_blank(cls, value: str) -> str:
        """Reject whitespace-only comments, which ``min_length`` lets through."""
        value = value.strip()
        if not value:
            raise ValueError("Comment body must not be blank")
        return value


class ResultLinkCreate(BaseModel):
    """Schema for linking a result."""

    result_id: uuid.UUID


class CaseResponse(BaseModel):
    """Pydantic model for Case serialization."""

    id: str
    organization_id: str
    assignment_id: str | None = None
    title: str
    status: str
    priority: str
    investigator_id: str | None = None
    created_by_id: str | None = None
    created_at: str
    updated_at: str
    closed_at: str | None = None

    class Config:
        from_attributes = True


# ==================== Serialization ====================


def _serialize_value(value: Any) -> Any:
    """Make a column value JSON-safe (UUID -> str, date/datetime -> ISO)."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date):  # datetime is a subclass of date
        return value.isoformat()
    return value


def _serialize_orm(obj: Any) -> dict:
    """Serialize any mapped ORM object's columns to a JSON-safe dict.

    Walks the mapper's column attributes by *attribute key*, so it stays correct
    when an attribute name differs from its column name, and it never includes
    SQLAlchemy state or relationships.
    """
    if obj is None:
        return {}
    state = sa_inspect(obj, raiseerr=False)
    mapper = getattr(state, "mapper", None)
    if mapper is None:
        return {}
    return {
        attr.key: _serialize_value(getattr(obj, attr.key))
        for attr in mapper.column_attrs
    }


def _serialize_case(case: Any) -> dict:
    """Serialize a Case, adding its assignment and investigator summaries."""
    data = _serialize_orm(case)
    if isinstance(case, Case):
        assignment = case.assignment
        if assignment is not None:
            data["assignment"] = {
                "id": str(assignment.id),
                "title": assignment.name,
                "course_name": assignment.course.name if assignment.course else None,
            }
        investigator = case.investigator
        if investigator is not None:
            data["investigator"] = {
                "id": str(investigator.id),
                "name": investigator.full_name,
            }
    return data


def _serialize_comment(comment: Any) -> dict:
    """Serialize a CaseComment object to a dictionary."""
    return _serialize_orm(comment)


def _serialize_result_link(link: Any) -> dict:
    """Serialize a CaseResultLink object to a dictionary."""
    return _serialize_orm(link)


def _serialize_orm_event(event: Any) -> dict:
    """Serialize any ORM object to a JSON-safe dictionary."""
    return _serialize_orm(event)


def _preload_case_relations(db: Session, cases: list[Case]) -> None:
    """Eager-load assignment/course/investigator for a batch of cases.

    ``_serialize_case`` touches three lazy relationships per case, which turns a
    1000-row listing into thousands of queries. The loader options populate the
    still-unloaded attributes on the instances already in the session.
    """
    ids = [c.id for c in cases]
    if not ids:
        return
    (
        db.query(Case)
        .options(
            selectinload(Case.assignment).selectinload(Assignment.course),
            selectinload(Case.investigator),
        )
        .filter(Case.id.in_(ids))
        .all()
    )


def _case_detail(case_data: dict) -> dict:
    """Build the JSON body for a case, its linked result ids and its comments."""
    case_obj = case_data.get("case")
    return {
        "case": _serialize_case(case_obj) if isinstance(case_obj, Case) else case_obj,
        "result_ids": [str(rid) for rid in case_data.get("result_ids", [])],
        "comments": [
            _serialize_comment(c) if isinstance(c, CaseComment) else c
            for c in case_data.get("comments", [])
        ],
    }


# ==================== Authentication helpers ====================

DEV_FALLBACK_TENANT_ID = "2bde87ba-3ad4-4282-b199-02243991150e"
DEV_FALLBACK_USER_ID = "00000000-0000-4000-8000-000000000001"


def get_current_user(request: Request = None) -> dict:
    """Resolve the current user from the authenticated request or session cookie.

    Prefers the user attached by the dashboard auth middleware, then validates
    the session cookie directly. Raises 401 for unauthenticated requests unless
    DEBUG_MODE is enabled, which keeps the mock-user fallback for local
    development only.
    """
    from src.backend.config.settings import settings

    middleware_user = getattr(request.state, "user", None) if request else None
    if isinstance(middleware_user, dict) and middleware_user.get("id"):
        return middleware_user

    token = (request.cookies if request else {}).get("integritydesk_session")
    # The settings object was read as ``AUTH_JWT_SECRET`` for the guard but
    # ``auth_jwt_secret`` for the decode, so one of the two raised and the
    # blanket ``except`` hid it. Read it once, tolerating either spelling.
    secret = getattr(settings, "AUTH_JWT_SECRET", None) or getattr(
        settings, "auth_jwt_secret", None
    )
    if token and secret:
        try:
            import jwt as _jwt

            payload = _jwt.decode(token, secret, algorithms=["HS256"])
            user_id = str(payload.get("sub") or "").strip()
            if user_id:
                from src.backend.config.database import SessionLocal

                with SessionLocal() as db:
                    user = db.get(User, user_id)
                    if user and user.is_active:
                        return {
                            "id": str(user.id),
                            "email": user.email,
                            "role": user.role,
                            "tenant_id": (
                                str(user.tenant_id)
                                if user.tenant_id is not None
                                else None
                            ),
                            "organization_id": (
                                str(user.organization_id)
                                if user.organization_id is not None
                                else None
                            ),
                        }
        except Exception as exc:
            # Invalid/expired token or a lookup failure: fall through to 401
            # (or the dev fallback). Log the type only, never the token.
            logger.debug("Session cookie rejected: %s", type(exc).__name__)

    if settings.DEBUG_MODE:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Organization

        # In dev mode, prefer the first existing organization/user so seeded
        # data is visible and foreign keys resolve. Fall back to stable dev ids.
        dev_org_id: str | None = None
        dev_user_id: str | None = None
        try:
            with SessionLocal() as dev_db:
                org = dev_db.query(Organization).first()
                if org is not None:
                    dev_org_id = str(org.id)
                    dev_user = (
                        dev_db.query(User)
                        .filter(User.organization_id == org.id)
                        .first()
                    )
                    if dev_user is not None:
                        dev_user_id = str(dev_user.id)
        except Exception as exc:
            logger.debug("Dev fallback lookup failed: %s", type(exc).__name__)
        if dev_org_id is None:
            dev_org_id = DEV_FALLBACK_TENANT_ID

        return {
            # Stable across requests: a fresh uuid4 per call made every dev
            # action come from a different, non-existent user.
            "id": dev_user_id or DEV_FALLBACK_USER_ID,
            "email": "user@example.com",
            "role": "professor",
            "tenant_id": dev_org_id,
            "organization_id": dev_org_id,
        }

    raise HTTPException(status_code=401, detail="Authentication required")


def get_current_tenant(user: dict = Depends(get_current_user)) -> dict:
    """Get current organization from the resolved authenticated user."""
    org_id = user.get("organization_id") or user.get("tenant_id")
    if org_id:
        try:
            return {"id": uuid.UUID(str(org_id))}
        except ValueError:
            logger.warning("Malformed organization id on authenticated user")
    raise HTTPException(
        status_code=403,
        detail="User is not associated with an organization",
    )


# ==================== Tenant-scoping helpers ====================


def _load_case_for_tenant(service: CaseService, case_id: uuid.UUID, tenant: dict):
    """Fetch a case, requiring it to belong to the caller's organization.

    A case in another organization is reported as 404, not 403, so ids from
    other tenants cannot be probed.
    """
    case = service.get_case(case_id)
    if case is None or str(case.organization_id) != str(tenant["id"]):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _require_user_in_org(db: Session, user_id: uuid.UUID, tenant: dict) -> None:
    """404 unless ``user_id`` is a user of the caller's organization."""
    person = db.get(User, user_id)
    if person is None or str(person.organization_id) != str(tenant["id"]):
        raise HTTPException(status_code=404, detail="Reviewer not found")


def _require_assignment_in_org(
    db: Session, assignment_id: uuid.UUID, tenant: dict
) -> None:
    """404 unless the assignment's course belongs to the caller's organization."""
    assignment = db.get(Assignment, assignment_id)
    course = assignment.course if assignment is not None else None
    if course is None or str(course.organization_id) != str(tenant["id"]):
        raise HTTPException(status_code=404, detail="Assignment not found")


# ==================== Routes ====================


@router.get("/cases", response_model=list[dict])
async def list_cases(
    status: str | None = Query(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$"),
    limit: int = Query(100, ge=1, le=1000),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """List cases for the current tenant/organization."""
    service = CaseService(db)
    cases = service.get_cases_by_organization(
        organization_id=tenant["id"],
        status=status,
        limit=limit,
    )
    _preload_case_relations(db, cases)
    return [_serialize_case(c) for c in cases]


@router.post("/cases", response_model=dict, status_code=201)
async def create_case(
    payload: CaseCreate,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Create a new investigation case."""
    if payload.assignment_id is not None:
        _require_assignment_in_org(db, payload.assignment_id, tenant)
    service = CaseService(db)
    case = service.create_case(
        organization_id=tenant["id"],
        title=payload.title,
        assignment_id=payload.assignment_id,
        created_by_id=user["id"],
        priority=payload.priority,
    )
    return _serialize_case(case)


@router.get("/cases/{case_id}", response_model=dict)
async def get_case(
    case_id: uuid.UUID,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Get a case with all linked results and comments."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    case_data = service.get_case_with_results(case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_detail(case_data)


@router.patch("/cases/{case_id}", response_model=dict)
async def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Update a case (title, priority, status and/or investigator)."""
    service = CaseService(db)
    case = _load_case_for_tenant(service, case_id, tenant)
    if payload.investigator_id:
        _require_user_in_org(db, payload.investigator_id, tenant)

    # ``title`` and ``priority`` were accepted by the schema but never applied.
    changed = False
    if payload.title is not None and payload.title != case.title:
        case.title = payload.title
        changed = True
    if payload.priority is not None and payload.priority != case.priority:
        case.priority = payload.priority
        changed = True
    if changed:
        db.commit()

    if payload.status and payload.status != case.status:
        service.update_status(case_id, payload.status, user["id"])
    if payload.investigator_id:
        service.assign_reviewer(case_id, payload.investigator_id)

    # Re-read so the response reflects every change, and never serialize None.
    refreshed = service.get_case(case_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize_case(refreshed)


@router.post("/cases/{case_id}/assign", response_model=dict)
async def assign_reviewer(
    case_id: uuid.UUID,
    payload: CaseAssign,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Assign a reviewer to a case."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    _require_user_in_org(db, payload.reviewer_id, tenant)
    case = service.assign_reviewer(case_id, payload.reviewer_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize_case(case)


@router.post("/cases/{case_id}/link", response_model=dict, status_code=201)
async def link_result(
    case_id: uuid.UUID,
    payload: ResultLinkCreate,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Link a similarity result to a case."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    link = service.link_result(case_id, payload.result_id)
    return _serialize_result_link(link)


@router.post("/cases/{case_id}/comments", response_model=dict, status_code=201)
async def add_comment(
    case_id: uuid.UUID,
    payload: CaseCommentCreate,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Add a comment to a case."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    comment = service.add_comment(case_id, user["id"], payload.body)
    return _serialize_comment(comment)


@router.get("/cases/{case_id}/timeline", response_model=list[dict])
async def get_timeline(
    case_id: uuid.UUID,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Get timeline events for a case."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    events = service.timeline.get_case_timeline(case_id)
    return [_serialize_orm_event(e) for e in events]


@router.get("/cases/{case_id}/export", response_model=dict)
async def export_case(
    case_id: uuid.UUID,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Export case data as JSON for audit purposes."""
    service = CaseService(db)
    _load_case_for_tenant(service, case_id, tenant)
    case_data = service.get_case_with_results(case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")

    # The raw service result holds ORM objects, which cannot be returned as JSON
    # (and would expose every column); serialize it the same way as get_case.
    export = _case_detail(case_data)
    export["timeline"] = [
        _serialize_orm_event(e) for e in service.timeline.get_case_timeline(case_id)
    ]
    export["exported_at"] = datetime.now(timezone.utc).isoformat()
    export["exported_by"] = str(user["id"])
    logger.info("Case %s exported by user %s", case_id, user["id"])
    return export
