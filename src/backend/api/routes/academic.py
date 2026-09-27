"""
API routes for managing Organizations, Courses, Assignments, Students, and Enrollments.
"""

from datetime import datetime
from typing import Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant, require_admin
from src.backend.config.database import get_db
from src.backend.models.database import (
    Assignment,
    AssignmentVersion,
    Course,
    Enrollment,
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


class TermResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    year: int
    label: str
    description: Optional[str] = None
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


def _term_to_response(term: Term, course_count: int) -> TermResponse:
    """Serialize a term registry row for the API."""
    return TermResponse(
        id=str(term.id),
        organization_id=str(term.organization_id),
        name=term.name,
        year=term.year,
        label=term_label(term.name, term.year),
        description=term.description,
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """List the terms registered for the current user's organization."""
    org_id = current_user.get("organization_id")
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
    term_data: TermCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Register a new academic term for the current user's organization."""
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(
            status_code=400, detail="No organization associated with user"
        )

    name = term_data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Term name is required")

    existing = (
        db.query(Term)
        .filter(
            Term.organization_id == org_id,
            Term.year == term_data.year,
            func.lower(Term.name) == name.lower(),
        )
        .first()
    )
    if existing:
        # Idempotent: returning the existing term (rather than a 409) lets the
        # UI create-then-assign without a separate pre-check for conflicts.
        return _term_to_response(existing, 0)

    term = Term(
        organization_id=org_id,
        name=name.title(),
        year=term_data.year,
        description=term_data.description,
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return _term_to_response(term, 0)


@router.delete("/terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(
    term_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Unregister a term.

    Courses keep their mirrored ``term``/``year`` text, so removing a term from
    the registry never strips a course of its term label.
    """
    org_id = current_user.get("organization_id")
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
    """List courses for an organization, optionally filtered by term."""
    query = db.query(Course).filter(Course.organization_id == org_id)
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
    """List all courses for the current user's organization with assignment counts."""
    user = getattr(request.state, "user", {}) or {}
    org_id = user.get("organization_id")
    if not org_id:
        return []

    courses = (
        db.query(Course)
        .filter(Course.organization_id == org_id)
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
    current_user: dict = Depends(get_current_tenant),
):
    """Get course by ID."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """Create a new assignment within a course."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """List assignments for a course, optionally filtered by term."""
    query = db.query(Assignment).filter(Assignment.course_id == course_id)
    if term:
        query = query.filter(Assignment.term == term)
    assignments = query.order_by(Assignment.created_at.desc()).all()
    return [_assignment_to_response(a) for a in assignments]


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Get assignment by ID."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return _assignment_to_response(assignment)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment_by_id(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """Delete an assignment by ID."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
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
    current_user: dict = Depends(get_current_tenant),
):
    """Create a new student profile."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """Enroll a student in a course."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """List all enrollments for a course."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """Create a new version of an assignment."""
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
    current_user: dict = Depends(get_current_tenant),
):
    """List all versions of an assignment."""
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
    current_user: dict = Depends(get_current_tenant),
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
