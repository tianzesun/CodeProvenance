"""
API routes for managing Organizations, Courses, Assignments, Students, and Enrollments.
"""

from datetime import date, datetime
from typing import Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import (
    dashboard_user,
    get_current_tenant,
    require_admin,
    require_user_permission,
)
from src.backend.application.services import academic_access
from src.backend.config.database import get_db
from src.backend.models.database import (
    Assignment,
    AssignmentVersion,
    Case,
    Course,
    Enrollment,
    Job,
    Organization,
    Student,
    Term,
)
from src.backend.application.services.student_service import (
    StudentService,
    AssignmentVersionService,
)

router = APIRouter(prefix="/api", tags=["academic"])
logger = logging.getLogger(__name__)


# ==================== Role dependencies ====================
#
# Guards are derived from the RBAC matrix in
# ``src.backend.api.middleware.auth`` rather than from role names inline, so a
# single matrix edit moves every route at once:
#
#   * term / course / roster writes are admin registry work;
#   * assignment writes belong to the professor teaching the course, resolved
#     against ``course_instructors`` here because the path only carries ids.

#: Registry writes: create/rename/delete terms.
require_term_write = require_user_permission("term:manage")

#: Registry writes: create/update/delete courses and bind a course to a term.
require_course_write = require_user_permission("course:manage")

#: Roster writes: enroll or remove a student in a course.
require_roster_write = require_user_permission("roster:manage")


def require_course_read_access(
    course_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Dependency: the caller must be allowed to read ``course_id``.

    Admins may read any course in their organization; professors only the
    courses they are assigned to.
    """
    user = dashboard_user(request)
    if not academic_access.can_read_course(db, user, course_id):
        raise HTTPException(status_code=403, detail="Not authorized for this course")
    return user


def require_assignment_write_access(
    course_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Dependency: only the professor teaching ``course_id`` may write its assignments."""
    user = dashboard_user(request)
    if not academic_access.can_manage_course_assignments(db, user, course_id):
        raise HTTPException(
            status_code=403, detail=academic_access.ASSIGNMENT_MANAGER_REQUIRED
        )
    return user


def require_assignment_read_access(
    assignment_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Dependency: the caller must be allowed to read the assignment's course."""
    user = dashboard_user(request)
    course_id = academic_access.course_id_for_assignment(db, assignment_id)
    if course_id is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not academic_access.can_read_course(db, user, course_id):
        raise HTTPException(
            status_code=403, detail="Not authorized for this assignment"
        )
    return user


def require_assignment_write_access_by_id(
    assignment_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Dependency for ``/assignments/{id}``: resolve its course, then check rights."""
    user = dashboard_user(request)
    course_id = academic_access.course_id_for_assignment(db, assignment_id)
    if course_id is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not academic_access.can_manage_course_assignments(db, user, course_id):
        raise HTTPException(
            status_code=403, detail=academic_access.ASSIGNMENT_MANAGER_REQUIRED
        )
    return user


# ==================== Request/Response Models ====================


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: str

    class Config:
        from_attributes = True


class TermCreate(BaseModel):
    name: str
    year: int
    description: Optional[str] = None
    # Optional planning window. Either end may be omitted.
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class TermUpdate(BaseModel):
    """Full replacement of the fields the admin term form edits.

    ``name`` and ``year`` are always applied. ``start_date`` / ``end_date`` are
    applied as given, so omitting or sending ``null`` clears that end of the
    window. ``description`` is only touched when the body includes it, which
    keeps a registry note intact when a client edits just the name or dates.
    """

    name: str
    year: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class TermResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    year: int
    label: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    course_count: int = 0
    created_at: str

    class Config:
        from_attributes = True


class CourseCreate(BaseModel):
    name: str
    code: Optional[str] = None
    term: Optional[str] = None
    year: Optional[int] = None
    department: Optional[str] = None
    description: Optional[str] = None
    # Registry term to attach. When set, ``term``/``year`` are mirrored from it.
    term_id: Optional[str] = None


class CourseResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: Optional[str]
    term: Optional[str]
    year: Optional[int]
    term_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class AssignmentCreate(BaseModel):
    name: str
    term: Optional[str] = None
    version: int = 1
    due_at: Optional[str] = None
    settings: Optional[dict] = None
    # Analytics metadata. ``assignment_type`` drives which detection mode and
    # engine weights are recommended for the assignment (see assignment_modes).
    assignment_type: Optional[str] = None
    description: Optional[str] = None
    max_score: Optional[float] = None
    team_mode: Optional[str] = None
    open_book: Optional[bool] = None
    time_limited: Optional[bool] = None


class AssignmentResponse(BaseModel):
    id: str
    course_id: str
    name: str
    term: Optional[str]
    version: int
    due_at: Optional[str]
    settings: Optional[dict]
    assignment_type: Optional[str]
    description: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    email: EmailStr
    full_name: str
    student_number: Optional[str] = None


class StudentResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    full_name: str
    student_number: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class EnrollmentCreate(BaseModel):
    student_id: str
    role: str = "student"


class EnrollmentResponse(BaseModel):
    id: str
    course_id: str
    student_id: str
    role: str
    enrolled_at: str
    student: Optional[StudentResponse] = None

    class Config:
        from_attributes = True


class AssignmentVersionCreate(BaseModel):
    version: int
    name: str
    description: Optional[str] = None
    starter_files: Optional[dict] = None
    settings: Optional[dict] = None


class AssignmentVersionResponse(BaseModel):
    id: str
    assignment_id: str
    course_id: str
    version: int
    name: str
    description: Optional[str]
    starter_files: Optional[dict]
    settings: Optional[dict]
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


# ==================== Shared Academic Helpers ====================

# Season display order within a year, used to sort the term registry.
TERM_SEASON_RANK: dict[str, int] = {
    "winter": 1,
    "spring": 2,
    "summer": 3,
    "fall": 4,
    "autumn": 4,
}


def term_label(name: str, year: int) -> str:
    """Render a term as its display label, e.g. ``("Fall", 2026) -> "Fall 2026"``."""
    return f"{name.strip().title()} {year}"


def _term_sort_key(term: Term) -> tuple[int, int, str]:
    """Order terms newest-first, then by season within the year.

    Mirrors the frontend ordering in ``src/frontend/lib/terms.ts`` so the API
    and UI present the same sequence. Unknown season names sort last.
    """
    rank = TERM_SEASON_RANK.get((term.name or "").strip().lower(), 99)
    return (-term.year, rank, term.name or "")


def _request_org_id(request: Request) -> Optional[str]:
    """Resolve the caller's organization id from the authenticated request.

    ``get_current_tenant`` deliberately returns the *tenant id*, and this
    deployment keeps tenants and organizations as separate tables, so academic
    routes that scope by organization must read the session user instead (the
    same source ``list_my_courses`` uses). Kept as a helper so every term route
    scopes identically.
    """
    user = getattr(request.state, "user", None) or {}
    org_id = user.get("organization_id")
    return str(org_id) if org_id else None


def _term_date_to_response(value: Optional[date]) -> Optional[str]:
    """Serialize an optional term date as ``YYYY-MM-DD``, or ``None``."""
    return value.isoformat() if value else None


def _validate_term_window(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Reject an inverted planning window.

    Raises:
        HTTPException: 400 when both ends are set and start is after end.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="Term start date must be on or before the end date"
        )


def find_term_conflict(
    db: Session,
    organization_id: str,
    year: int,
    name: str,
    exclude_id: Optional[str] = None,
) -> Optional[Term]:
    """Find an existing term with the same ``(name, year)`` for the org.

    Matching is case-insensitive to mirror the registry's uniqueness rule. When
    ``exclude_id`` is given that row is ignored, so a term can be saved without
    colliding with itself.
    """
    query = db.query(Term).filter(
        Term.organization_id == organization_id,
        Term.year == year,
        func.lower(Term.name) == name.strip().lower(),
    )
    if exclude_id:
        query = query.filter(Term.id != exclude_id)
    return query.first()


def sync_term_on_courses(db: Session, term: Term) -> int:
    """Mirror a term's name/year onto every course linked to it.

    ``courses.term`` / ``courses.year`` are denormalized copies kept in sync
    with the registry (see :func:`resolve_course_term`), so renaming a term has
    to rewrite them or listings and reporting that read the text go stale. Only
    courses whose ``term_id`` points at this term are touched, which keeps other
    organizations' rows untouched.

    Returns:
        The number of course rows updated.
    """
    return (
        db.query(Course)
        .filter(Course.term_id == term.id)
        .update(
            {Course.term: term.name, Course.year: term.year},
            synchronize_session=False,
        )
    )


def _term_to_response(term: Term, course_count: int) -> TermResponse:
    """Serialize a term registry row for the API."""
    return TermResponse(
        id=str(term.id),
        organization_id=str(term.organization_id),
        name=term.name,
        year=term.year,
        label=term_label(term.name, term.year),
        description=term.description,
        start_date=_term_date_to_response(term.start_date),
        end_date=_term_date_to_response(term.end_date),
        course_count=course_count,
        created_at=term.created_at.isoformat() if term.created_at else "",
    )


def resolve_course_term(
    db: Session,
    organization_id: str,
    term_id: Optional[str],
    term_name: Optional[str],
    year: Optional[int],
) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Resolve a course's term to a ``(term_id, term_name, year)`` triple.

    A ``term_id`` from the org's registry wins, and its name/year are mirrored
    onto the course. Without one, a ``(term, year)`` pair matching an existing
    registry entry is linked to it so historical terms stay reusable; an unknown
    pair is stored as free text with no registry link.

    Raises:
        HTTPException: 404 when ``term_id`` does not exist, 403 when it belongs
            to another organization.
    """
    if term_id:
        term = db.query(Term).filter(Term.id == term_id).first()
        if not term:
            raise HTTPException(status_code=404, detail="Term not found")
        if str(term.organization_id) != str(organization_id):
            raise HTTPException(
                status_code=403, detail="Term belongs to another organization"
            )
        return str(term.id), term.name, term.year

    name = (term_name or "").strip()
    if not name or year is None:
        return None, (name or None), year

    match = (
        db.query(Term)
        .filter(
            Term.organization_id == organization_id,
            Term.year == year,
            func.lower(Term.name) == name.lower(),
        )
        .first()
    )
    if match:
        return str(match.id), match.name, match.year
    return None, name, year


# ==================== Term Routes ====================


@router.get("/terms", response_model=list[TermResponse])
async def list_terms(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """List the terms registered for the current user's organization."""
    org_id = _request_org_id(request)
    if not org_id:
        return []

    terms = (
        db.query(Term)
        .filter(Term.organization_id == org_id)
        .order_by(Term.year.desc(), Term.name)
        .all()
    )
    if not terms:
        return []

    counts = dict(
        db.query(Course.term_id, func.count(Course.id))
        .filter(Course.term_id.in_([t.id for t in terms]))
        .group_by(Course.term_id)
        .all()
    )
    return [
        _term_to_response(t, int(counts.get(t.id, 0)))
        for t in sorted(terms, key=_term_sort_key)
    ]


@router.post("/terms", response_model=TermResponse, status_code=status.HTTP_201_CREATED)
async def create_term(
    request: Request,
    term_data: TermCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_term_write),
):
    """Register a new academic term for the current user's organization.

    Admin-only: the term registry is part of the academic structure an
    administrator owns. Professors only ever read the terms their courses are
    already filed under (``GET /api/terms``).
    """
    org_id = _request_org_id(request)
    if not org_id:
        raise HTTPException(
            status_code=400, detail="No organization associated with user"
        )

    name = term_data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Term name is required")
    _validate_term_window(term_data.start_date, term_data.end_date)

    existing = find_term_conflict(db, org_id, term_data.year, name)
    if existing:
        # Idempotent: returning the existing term (rather than a 409) lets the
        # UI create-then-assign without a separate pre-check for conflicts.
        return _term_to_response(existing, 0)

    term = Term(
        organization_id=org_id,
        name=name.title(),
        year=term_data.year,
        description=term_data.description,
        start_date=term_data.start_date,
        end_date=term_data.end_date,
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return _term_to_response(term, 0)


@router.put("/terms/{term_id}", response_model=TermResponse)
async def update_term(
    request: Request,
    term_id: str,
    term_data: TermUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_term_write),
):
    """Rename a term or adjust its planning window, mirroring the change on courses.

    Admin-only: reorganising the term registry is registry work, not teaching.

    Courses linked to the term keep ``term``/``year`` text copies that listings
    and reporting read, so the new name/year are written onto them in the same
    transaction. Only rows whose ``term_id`` points at this term change, which
    leaves other organizations (and unlinked free-text terms) untouched.

    Raises:
        HTTPException: 404 unknown term, 403 term from another organization,
            400 blank name or inverted date window, 409 when the new
            ``(name, year)`` is already registered for the organization.
    """
    org_id = _request_org_id(request)
    term = db.query(Term).filter(Term.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    if org_id and str(term.organization_id) != str(org_id):
        raise HTTPException(
            status_code=403, detail="Term belongs to another organization"
        )

    name = term_data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Term name is required")
    _validate_term_window(term_data.start_date, term_data.end_date)

    conflict = find_term_conflict(
        db, term.organization_id, term_data.year, name, exclude_id=str(term.id)
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"{term_label(name, term_data.year)} is already registered",
        )

    term.name = name.title()
    term.year = term_data.year
    term.start_date = term_data.start_date
    term.end_date = term_data.end_date
    if "description" in term_data.model_fields_set:
        term.description = term_data.description

    # Flush first so the mirrored course text carries the new name/year.
    db.flush()
    sync_term_on_courses(db, term)
    db.commit()
    db.refresh(term)

    course_count = db.query(Course).filter(Course.term_id == term.id).count()
    return _term_to_response(term, course_count)


@router.delete("/terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(
    request: Request,
    term_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_term_write),
):
    """Unregister a term.

    Admin-only: deleting registry entries is administrative.

    Courses keep their mirrored ``term``/``year`` text, so removing a term from
    the registry never strips a course of its term label.
    """
    org_id = _request_org_id(request)
    term = db.query(Term).filter(Term.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    if org_id and str(term.organization_id) != str(org_id):
        raise HTTPException(
            status_code=403, detail="Term belongs to another organization"
        )

    db.query(Course).filter(Course.term_id == term_id).update(
        {Course.term_id: None}, synchronize_session=False
    )
    db.delete(term)
    db.commit()


# ==================== Organization Routes ====================


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new organization."""
    org = Organization(name=org_data.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        created_at=org.created_at.isoformat() if org.created_at else "",
    )


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List all organizations."""
    orgs = db.query(Organization).all()
    return [
        OrganizationResponse(
            id=str(o.id),
            name=o.name,
            created_at=o.created_at.isoformat() if o.created_at else "",
        )
        for o in orgs
    ]


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Get organization by ID."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        created_at=org.created_at.isoformat() if org.created_at else "",
    )


# ==================== Course Routes ====================


@router.post(
    "/organizations/{org_id}/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course(
    org_id: str,
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new course within an organization."""
    # Verify organization exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    course = Course(
        organization_id=org_id,
        name=course_data.name,
        code=course_data.code,
        term=course_data.term,
        year=course_data.year,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return CourseResponse(
        id=str(course.id),
        organization_id=str(course.organization_id),
        name=course.name,
        code=course.code,
        term=course.term,
        year=course.year,
        created_at=course.created_at.isoformat() if course.created_at else "",
    )


@router.get("/organizations/{org_id}/courses", response_model=list[CourseResponse])
async def list_courses(
    org_id: str,
    term: Optional[str] = Query(None, description="Filter by term"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """List courses for an organization, optionally filtered by term.

    A professor's listing is narrowed to the courses they are assigned to, so
    the org filter can never widen "my courses" into the whole catalog.
    """
    query = db.query(Course).filter(Course.organization_id == org_id)
    query = query.filter(
        Course.id.in_(academic_access.visible_course_id_query(db, current_user))
    )
    if term:
        query = query.filter(Course.term == term)
    courses = query.order_by(Course.created_at.desc()).all()
    return [
        CourseResponse(
            id=str(c.id),
            organization_id=str(c.organization_id),
            name=c.name,
            code=c.code,
            term=c.term,
            year=c.year,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in courses
    ]


@router.get("/courses")
async def list_my_courses(
    request: Request,
    db: Session = Depends(get_db),
):
    """List the courses the caller may work on, with assignment counts.

    Admins see the whole organization's catalog (they own it); professors see
    only the courses they are assigned to, across every term and year, so past
    offerings and their assignments stay reachable.
    """
    user = getattr(request.state, "user", {}) or {}
    visible_ids = academic_access.visible_course_id_query(db, user)

    courses = (
        db.query(Course)
        .filter(Course.id.in_(visible_ids))
        .order_by(Course.created_at.desc())
        .all()
    )

    result = []
    for c in courses:
        count = db.query(Assignment).filter(Assignment.course_id == c.id).count()
        result.append(
            {
                "id": str(c.id),
                "name": c.name,
                "code": c.code,
                "term": c.term,
                "year": c.year,
                "department": c.department,
                "assignmentCount": count,
            }
        )
    return result


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_course_read_access),
):
    """Get course by ID.

    Read access is row-scoped: an admin reaches any course in their
    organization, a professor only a course they teach.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseResponse(
        id=str(course.id),
        organization_id=str(course.organization_id),
        name=course.name,
        code=course.code,
        term=course.term,
        year=course.year,
        created_at=course.created_at.isoformat() if course.created_at else "",
    )


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def create_course_for_org(
    request: Request,
    course_data: CourseCreate,
    db: Session = Depends(get_db),
):
    """Create a new course in the current user's organization."""
    user = getattr(request.state, "user", {}) or {}
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(
            status_code=400, detail="No organization associated with user"
        )

    term_id, term_name, year = resolve_course_term(
        db, org_id, course_data.term_id, course_data.term, course_data.year
    )

    course = Course(
        organization_id=org_id,
        name=course_data.name,
        code=course_data.code,
        term_id=term_id,
        term=term_name,
        year=year,
        department=course_data.department,
        description=course_data.description,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return {
        "id": str(course.id),
        "name": course.name,
        "code": course.code,
        "term": course.term,
        "year": course.year,
        "term_id": str(course.term_id) if course.term_id else None,
        "department": course.department,
        "assignmentCount": 0,
    }


@router.put("/courses/{course_id}")
async def update_course_by_id(
    course_id: str,
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Update a course by ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    term_id, term_name, year = resolve_course_term(
        db,
        str(course.organization_id),
        course_data.term_id,
        course_data.term,
        course_data.year,
    )
    course.name = course_data.name
    course.code = course_data.code
    course.term_id = term_id
    course.term = term_name
    course.year = year
    course.department = course_data.department
    course.description = course_data.description
    db.commit()
    db.refresh(course)
    return {
        "id": str(course.id),
        "name": course.name,
        "code": course.code,
        "term": course.term,
        "year": course.year,
        "term_id": str(course.term_id) if course.term_id else None,
        "department": course.department,
    }


def _history_attachments(db: Session, assignment_ids: list[str]) -> tuple[int, int]:
    """Count check-history rows and cases still pointing at ``assignment_ids``.

    ``jobs.assignment_id`` and ``cases.assignment_id`` are nullable foreign
    keys with no ON DELETE rule, so deleting an assignment (or a course that
    owns one) while they point at it surfaces as an opaque 500 from the driver.
    Evidence wins over structure: callers get the counts back and decide the
    message instead of orphaning history silently.
    """
    if not assignment_ids:
        return 0, 0
    jobs = db.query(func.count(Job.id)).filter(Job.assignment_id.in_(assignment_ids)).scalar() or 0
    cases = (
        db.query(func.count(Case.id)).filter(Case.assignment_id.in_(assignment_ids)).scalar() or 0
    )
    return jobs, cases


def _attachment_detail(jobs: int, cases: int) -> str:
    """Build the 409 detail naming which evidence blocks the deletion."""
    parts = []
    if jobs:
        parts.append(f"{jobs} check{'s' if jobs != 1 else ''}")
    if cases:
        parts.append(f"{cases} case{'s' if cases != 1 else ''}")
    return (
        "still has "
        + " and ".join(parts)
        + " attached. Check history and cases are kept, so remove those first."
    )


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_by_id(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Delete a course by ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
    if assignments:
        jobs, cases = _history_attachments(db, [a.id for a in assignments])
        if jobs or cases:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This course's assignments " + _attachment_detail(jobs, cases),
            )
        db.query(Assignment).filter(Assignment.course_id == course.id).delete(
            synchronize_session=False
        )
    db.delete(course)
    db.commit()


def _parse_due_at(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 due date, returning ``None`` when absent or invalid.

    Invalid input is tolerated (a bad date must not block assignment creation)
    but surfaces as a warning log so the data problem is still visible.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        logger.warning("Ignoring unparseable due_at value: %r", value)
        return None


def _assignment_to_response(assignment: Assignment) -> AssignmentResponse:
    """Serialize an assignment for the API."""
    return AssignmentResponse(
        id=str(assignment.id),
        course_id=str(assignment.course_id),
        name=assignment.name,
        term=assignment.term,
        version=assignment.version,
        due_at=assignment.due_at.isoformat() if assignment.due_at else None,
        settings=assignment.settings,
        assignment_type=assignment.assignment_type or "programming",
        description=assignment.description,
        created_at=assignment.created_at.isoformat() if assignment.created_at else "",
    )


# ==================== Assignment Routes ====================


@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    course_id: str,
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_write_access),
):
    """Create a new assignment within a course.

    Only the professor assigned to the course may create assignments: an
    assignment is a teaching artefact. An admin creating a course assigns a
    professor to it, and that professor authors the assignments.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    assignment = Assignment(
        course_id=course_id,
        name=assignment_data.name,
        term=assignment_data.term or course.term,
        version=assignment_data.version,
        due_at=_parse_due_at(assignment_data.due_at),
        settings=assignment_data.settings or {},
        assignment_type=assignment_data.assignment_type or "programming",
        description=assignment_data.description,
        max_score=assignment_data.max_score,
        team_mode=assignment_data.team_mode or "individual",
        open_book=(
            True if assignment_data.open_book is None else assignment_data.open_book
        ),
        time_limited=(
            False
            if assignment_data.time_limited is None
            else assignment_data.time_limited
        ),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_to_response(assignment)


@router.get("/courses/{course_id}/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    course_id: str,
    term: Optional[str] = Query(None, description="Filter by term"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_course_read_access),
):
    """List assignments for a course, optionally filtered by term.

    No term filter is applied by default, so a professor reviewing a past
    offering still sees that course's older assignments.
    """
    query = db.query(Assignment).filter(Assignment.course_id == course_id)
    if term:
        query = query.filter(Assignment.term == term)
    assignments = query.order_by(Assignment.created_at.desc()).all()
    return [_assignment_to_response(a) for a in assignments]


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_read_access),
):
    """Get assignment by ID (read access is scoped to the owning course)."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return _assignment_to_response(assignment)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment_by_id(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_write_access_by_id),
):
    """Delete an assignment by ID."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    jobs, cases = _history_attachments(db, [assignment.id])
    if jobs or cases:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment " + _attachment_detail(jobs, cases),
        )
    db.delete(assignment)
    db.commit()


# ==================== Student Routes ====================


@router.post(
    "/organizations/{org_id}/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_student(
    org_id: str,
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roster_write),
):
    """Create a new student profile (admin-only: the roster is registry data)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if student already exists
    existing = StudentService.get_student_by_email(db, org_id, student_data.email)
    if existing:
        raise HTTPException(
            status_code=400, detail="Student with this email already exists"
        )

    student = StudentService.create_student(
        db,
        org_id,
        student_data.email,
        student_data.full_name,
        student_data.student_number,
    )
    return StudentResponse(
        id=str(student.id),
        organization_id=str(student.organization_id),
        email=student.email,
        full_name=student.full_name,
        student_number=student.student_number,
        created_at=student.created_at.isoformat() if student.created_at else "",
    )


@router.get("/organizations/{org_id}/students", response_model=list[StudentResponse])
async def list_students(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """List all students in an organization."""
    students = db.query(Student).filter(Student.organization_id == org_id).all()
    return [
        StudentResponse(
            id=str(s.id),
            organization_id=str(s.organization_id),
            email=s.email,
            full_name=s.full_name,
            student_number=s.student_number,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in students
    ]


@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Get student by ID."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponse(
        id=str(student.id),
        organization_id=str(student.organization_id),
        email=student.email,
        full_name=student.full_name,
        student_number=student.student_number,
        created_at=student.created_at.isoformat() if student.created_at else "",
    )


# ==================== Enrollment Routes ====================


@router.post(
    "/courses/{course_id}/enrollments",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_student(
    course_id: str,
    enrollment_data: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roster_write),
):
    """Enroll a student in a course (admin-only: assigning users is registry work)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    student = db.query(Student).filter(Student.id == enrollment_data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Check if already enrolled
    existing = StudentService.get_enrollment(db, course_id, enrollment_data.student_id)
    if existing:
        raise HTTPException(
            status_code=400, detail="Student already enrolled in this course"
        )

    enrollment = StudentService.enroll_student(
        db, course_id, enrollment_data.student_id, enrollment_data.role
    )
    return EnrollmentResponse(
        id=str(enrollment.id),
        course_id=str(enrollment.course_id),
        student_id=str(enrollment.student_id),
        role=enrollment.role,
        enrolled_at=(
            enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else ""
        ),
        student=StudentResponse(
            id=str(student.id),
            organization_id=str(student.organization_id),
            email=student.email,
            full_name=student.full_name,
            student_number=student.student_number,
            created_at=student.created_at.isoformat() if student.created_at else "",
        ),
    )


@router.get("/courses/{course_id}/enrollments", response_model=list[EnrollmentResponse])
async def list_enrollments(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_course_read_access),
):
    """List a course's roster (admin, or the professor teaching the course)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollments = StudentService.get_course_enrollments(db, course_id)
    result = []
    for e in enrollments:
        student = db.query(Student).filter(Student.id == e.student_id).first()
        result.append(
            EnrollmentResponse(
                id=str(e.id),
                course_id=str(e.course_id),
                student_id=str(e.student_id),
                role=e.role,
                enrolled_at=e.enrolled_at.isoformat() if e.enrolled_at else "",
                student=(
                    StudentResponse(
                        id=str(student.id),
                        organization_id=str(student.organization_id),
                        email=student.email,
                        full_name=student.full_name,
                        student_number=student.student_number,
                        created_at=(
                            student.created_at.isoformat() if student.created_at else ""
                        ),
                    )
                    if student
                    else None
                ),
            )
        )
    return result


@router.delete("/courses/{course_id}/enrollments/{enrollment_id}")
async def remove_enrollment(
    course_id: str,
    enrollment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Remove a student from a course."""
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.id == enrollment_id, Enrollment.course_id == course_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()
    return {"success": True, "message": "Enrollment removed"}


# ==================== Assignment Version Routes ====================


@router.post(
    "/assignments/{assignment_id}/versions",
    response_model=AssignmentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment_version(
    assignment_id: str,
    version_data: AssignmentVersionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_write_access_by_id),
):
    """Create a new version of an assignment (professor teaching the course)."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check if version already exists
    existing = AssignmentVersionService.get_version(
        db, assignment_id, version_data.version
    )
    if existing:
        raise HTTPException(
            status_code=400, detail=f"Version {version_data.version} already exists"
        )

    # Deactivate other versions if this is the new active one
    if version_data.settings and version_data.settings.get("is_active"):
        db.query(AssignmentVersion).filter(
            AssignmentVersion.assignment_id == assignment_id,
            AssignmentVersion.is_active.is_(True),
        ).update({"is_active": False})

    av = AssignmentVersionService.create_version(
        db,
        assignment_id,
        assignment.course_id,
        version_data.version,
        version_data.name,
        version_data.description,
        version_data.starter_files,
        version_data.settings,
    )
    return AssignmentVersionResponse(
        id=str(av.id),
        assignment_id=str(av.assignment_id),
        course_id=str(av.course_id),
        version=av.version,
        name=av.name,
        description=av.description,
        starter_files=av.starter_files,
        settings=av.settings,
        is_active=av.is_active,
        created_at=av.created_at.isoformat() if av.created_at else "",
    )


@router.get(
    "/assignments/{assignment_id}/versions",
    response_model=list[AssignmentVersionResponse],
)
async def list_assignment_versions(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_read_access),
):
    """List all versions of an assignment (read access scoped to its course)."""
    versions = AssignmentVersionService.get_versions_for_assignment(db, assignment_id)
    return [
        AssignmentVersionResponse(
            id=str(v.id),
            assignment_id=str(v.assignment_id),
            course_id=str(v.course_id),
            version=v.version,
            name=v.name,
            description=v.description,
            starter_files=v.starter_files,
            settings=v.settings,
            is_active=v.is_active,
            created_at=v.created_at.isoformat() if v.created_at else "",
        )
        for v in versions
    ]


@router.get(
    "/assignments/{assignment_id}/versions/active",
    response_model=Optional[AssignmentVersionResponse],
)
async def get_active_assignment_version(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_assignment_read_access),
):
    """Get the currently active version of an assignment."""
    av = AssignmentVersionService.get_active_version(db, assignment_id)
    if not av:
        return None
    return AssignmentVersionResponse(
        id=str(av.id),
        assignment_id=str(av.assignment_id),
        course_id=str(av.course_id),
        version=av.version,
        name=av.name,
        description=av.description,
        starter_files=av.starter_files,
        settings=av.settings,
        is_active=av.is_active,
        created_at=av.created_at.isoformat() if av.created_at else "",
    )
