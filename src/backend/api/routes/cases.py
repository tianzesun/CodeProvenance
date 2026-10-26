"""Case management API endpoints for Academic Integrity Investigation Platform."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, selectinload

from src.backend.application.services import academic_access, sharing
from src.backend.application.services.case_service import (
    CaseService,
)
from src.backend.config.database import get_db
from src.backend.models.database import (
    Assignment,
    Case,
    CaseComment,
    CaseResultLink,
    Job,
    SimilarityResult,
    User,
)

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


class CaseFromPairCreate(BaseModel):
    """Schema for opening a case on one pair of a check.

    The pair is named by its check and file names, not a result id: the
    results page reads pairs from the job's file copy, whose ids are not the
    ``similarity_results`` row ids.
    """

    job_id: str = Field(..., min_length=1, max_length=64)
    file_a: str = Field(..., min_length=1, max_length=512)
    file_b: str = Field(..., min_length=1, max_length=512)


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


def _load_case_for_tenant(
    service: CaseService, case_id: uuid.UUID, tenant: dict, user: dict
):
    """Fetch a case the caller may see (application/services/sharing).

    It must be in the caller's organization and theirs, shared with them, or
    under a course they teach; any professor in the organization used to
    reach every case. Reported as 404, not 403, so ids cannot be probed.
    """
    case = service.get_case(case_id)
    if case is None or str(case.organization_id) != str(tenant["id"]):
        raise HTTPException(status_code=404, detail="Case not found")
    scope = sharing.access_scope(service.db, user)
    if not sharing.case_in_scope(service.db, case, user, scope):
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


def _require_result_in_org(
    db: Session, result_id: uuid.UUID, user: dict, tenant: dict
) -> None:
    """404 unless the similarity result belongs to the caller's workspace.

    The result id was never checked: a case could be linked to another
    tenant's result (which then showed in the case and its export), and an
    unknown id was a 500 from the foreign key.
    """
    row = (
        db.query(SimilarityResult, Job)
        .join(Job, Job.id == SimilarityResult.job_id)
        .filter(SimilarityResult.id == str(result_id))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Result not found")
    job = row[1]
    same_tenant = bool(
        job.tenant_id and str(job.tenant_id) == str(user.get("tenant_id") or "")
    )
    assignment = db.get(Assignment, job.assignment_id) if job.assignment_id else None
    course = assignment.course if assignment is not None else None
    same_org = course is not None and str(course.organization_id) == str(tenant["id"])
    if not (same_tenant or same_org):
        raise HTTPException(status_code=404, detail="Result not found")


# A pair this similar opens as a HIGH priority case; below it, MEDIUM.
HIGH_PRIORITY_SCORE = 0.9
CASE_TITLE_MAX = 255


def _find_pair_result(
    db: Session, job_id: str, file_a: str, file_b: str
) -> SimilarityResult | None:
    """The stored result for a pair; rows keep the two file names sorted."""
    a_name, b_name = sorted([file_a, file_b])
    return (
        db.query(SimilarityResult)
        .filter(
            SimilarityResult.job_id == job_id,
            SimilarityResult.submission_a_id == a_name,
            SimilarityResult.submission_b_id == b_name,
        )
        .first()
    )


def _visible_cases_by_result(
    db: Session, result_ids: list[str], user: dict, tenant: dict
) -> dict[str, Case]:
    """Newest case the caller may see for each result id, keyed by result id."""
    if not result_ids:
        return {}
    rows = (
        db.query(CaseResultLink.similarity_result_id, Case)
        .join(Case, Case.id == CaseResultLink.case_id)
        .filter(
            CaseResultLink.similarity_result_id.in_(result_ids),
            Case.organization_id == tenant["id"],
        )
        .order_by(Case.created_at.desc())
        .all()
    )
    scope = sharing.access_scope(db, user)
    courses = sharing.assignment_course_map(db, [case for _, case in rows])
    found: dict[str, Case] = {}
    for result_id, case in rows:
        key = str(result_id)
        if key not in found and sharing.case_in_scope(db, case, user, scope, courses):
            found[key] = case
    return found


def _pair_case_title(
    job: Job, assignment: Assignment | None, file_a: str, file_b: str
) -> str:
    """``a.py and b.py · Assignment 1``, cut to the column's length."""
    title = f"{file_a} and {file_b}"
    context = (assignment.name if assignment is not None else None) or job.name
    if context:
        title = f"{title} · {context}"
    if len(title) > CASE_TITLE_MAX:
        title = f"{title[: CASE_TITLE_MAX - 1]}…"
    return title


# ==================== Routes ====================


@router.get("/cases", response_model=list[dict])
async def list_cases(
    status: str | None = Query(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$"),
    limit: int = Query(100, ge=1, le=1000),
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """List the organization's cases the caller may see."""
    service = CaseService(db)
    scope = sharing.access_scope(db, user)
    # Fetch the organization's cases, then keep the caller's; a small limit
    # applied before filtering could hide every case they can see.
    candidates = service.get_cases_by_organization(
        organization_id=tenant["id"], status=status, limit=1000
    )
    courses = sharing.assignment_course_map(db, candidates)
    cases = [
        case
        for case in candidates
        if sharing.case_in_scope(db, case, user, scope, courses)
    ][:limit]
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
        course_id = academic_access.course_id_for_assignment(
            db, str(payload.assignment_id)
        )
        if not academic_access.can_read_course(db, user, course_id):
            raise HTTPException(status_code=404, detail="Assignment not found")
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
    _load_case_for_tenant(service, case_id, tenant, user)
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
    case = _load_case_for_tenant(service, case_id, tenant, user)
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

    # Assign first so an explicit status in the same update has the last word.
    if payload.investigator_id:
        service.assign_reviewer(case_id, payload.investigator_id, user["id"])
    if payload.status and payload.status != service.get_case(case_id).status:
        service.update_status(case_id, payload.status, user["id"])

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
    _load_case_for_tenant(service, case_id, tenant, user)
    _require_user_in_org(db, payload.reviewer_id, tenant)
    case = service.assign_reviewer(case_id, payload.reviewer_id, user["id"])
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
    _load_case_for_tenant(service, case_id, tenant, user)
    _require_result_in_org(db, payload.result_id, user, tenant)
    link = service.link_result(case_id, payload.result_id)
    return _serialize_result_link(link)


@router.post("/cases/from-pair", response_model=dict)
async def open_case_for_pair(
    payload: CaseFromPairCreate,
    response: Response,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Open a case on one flagged pair of a check, linked to its result.

    A pair that already has a case the caller can see returns that case
    (200) rather than opening a second one, so a repeated click is safe. A
    new case is 201. The case joins the check's assignment when the caller
    can read its course; otherwise it has none and stays visible to its
    creator, as a case opened from the cases API would.
    """
    result = _find_pair_result(db, payload.job_id, payload.file_a, payload.file_b)
    if result is None:
        raise HTTPException(status_code=404, detail="Pair not found")
    _require_result_in_org(db, uuid.UUID(str(result.id)), user, tenant)

    existing = _visible_cases_by_result(db, [str(result.id)], user, tenant)
    if str(result.id) in existing:
        response.status_code = 200
        return {"case": _serialize_case(existing[str(result.id)]), "created": False}

    job = db.get(Job, payload.job_id)
    assignment = db.get(Assignment, job.assignment_id) if job.assignment_id else None
    assignment_id = None
    if assignment is not None and academic_access.can_read_course(
        db, user, str(assignment.course_id)
    ):
        assignment_id = uuid.UUID(str(assignment.id))

    service = CaseService(db)
    case = service.create_case(
        organization_id=tenant["id"],
        title=_pair_case_title(job, assignment, payload.file_a, payload.file_b),
        assignment_id=assignment_id,
        created_by_id=user["id"],
        priority=(
            "HIGH"
            if float(result.similarity_score or 0) >= HIGH_PRIORITY_SCORE
            else "MEDIUM"
        ),
    )
    service.link_result(case.id, uuid.UUID(str(result.id)))
    response.status_code = 201
    return {"case": _serialize_case(case), "created": True}


@router.get("/cases/for-job/{job_id}", response_model=list[dict])
async def list_cases_for_job(
    job_id: str,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Cases the caller can see on each pair of a check, for the results page."""
    results = (
        db.query(SimilarityResult).filter(SimilarityResult.job_id == job_id).all()
    )
    if not results:
        return []
    _require_result_in_org(db, uuid.UUID(str(results[0].id)), user, tenant)
    cases = _visible_cases_by_result(db, [str(r.id) for r in results], user, tenant)
    return [
        {
            "file_a": r.submission_a_id,
            "file_b": r.submission_b_id,
            "case_id": str(cases[str(r.id)].id),
            "status": cases[str(r.id)].status,
        }
        for r in results
        if str(r.id) in cases
    ]


class CaseSharing(BaseModel):
    """Who a case is shared with beyond its owners and its course's audience."""

    workspace: bool = False
    user_ids: list[uuid.UUID] = Field(default_factory=list)


def _can_manage_case_sharing(db: Session, case: Case, user: dict) -> bool:
    """The case's creator, or a primary instructor of its course."""
    if str(case.created_by_id or "") == str(user.get("id") or ""):
        return True
    course_id = (
        academic_access.course_id_for_assignment(db, str(case.assignment_id))
        if case.assignment_id
        else None
    )
    return bool(course_id) and sharing.can_manage_course_sharing(db, user, course_id)


@router.get("/cases/{case_id}/sharing", response_model=dict)
async def get_case_sharing(
    case_id: uuid.UUID,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Who a case is shared with, for anyone who can see it."""
    case = _load_case_for_tenant(CaseService(db), case_id, tenant, user)
    return {
        **sharing.get_sharing(db, "case", str(case_id)),
        "can_manage": _can_manage_case_sharing(db, case, user),
    }


@router.put("/cases/{case_id}/sharing", response_model=dict)
async def set_case_sharing(
    case_id: uuid.UUID,
    payload: CaseSharing,
    user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Replace a case's shares (its creator or course instructors)."""
    case = _load_case_for_tenant(CaseService(db), case_id, tenant, user)
    if not _can_manage_case_sharing(db, case, user):
        raise HTTPException(
            status_code=403,
            detail="Only the case's creator or the course's primary instructors "
            "can change sharing",
        )
    try:
        shares = sharing.set_sharing(
            db,
            "case",
            str(case_id),
            sharer=user,
            workspace=payload.workspace,
            user_ids=[str(uid) for uid in payload.user_ids],
        )
    except sharing.SharingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {**shares, "can_manage": True}


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
    _load_case_for_tenant(service, case_id, tenant, user)
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
    _load_case_for_tenant(service, case_id, tenant, user)
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
    _load_case_for_tenant(service, case_id, tenant, user)
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
