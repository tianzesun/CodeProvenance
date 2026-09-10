"""
API routes for managing Organizations, Courses, Assignments, Students, and Enrollments.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session, joinedload

from src.backend.api.middleware.auth import get_current_tenant, require_admin
from src.backend.config.database import get_db
from src.backend.models.database import (
    Assignment,
    AssignmentVersion,
    Course,
    CourseInstructor,
    Enrollment,
    Organization,
    Student,
    Tenant,
    User,
)
from src.backend.application.services.student_service import StudentService, AssignmentVersionService

router = APIRouter(prefix="/api", tags=["academic"])


# ==================== Request/Response Models ====================

class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: str

    class Config:
        from_attributes = True


class CourseCreate(BaseModel):
    name: str
    code: Optional[str] = None
    term: Optional[str] = None
    year: Optional[int] = None


class CourseResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: Optional[str]
    term: Optional[str]
    year: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


class AssignmentCreate(BaseModel):
    name: str
    term: Optional[str] = None
    version: int = 1
    due_at: Optional[str] = None
    settings: Optional[dict] = None


class AssignmentResponse(BaseModel):
    id: str
    course_id: str
    name: str
    term: Optional[str]
    version: int
    due_at: Optional[str]
    settings: Optional[dict]
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


# ==================== Organization Routes ====================

@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
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

@router.post("/organizations/{org_id}/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
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


# ==================== Assignment Routes ====================

@router.post("/courses/{course_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
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
        due_at=assignment_data.due_at,
        settings=assignment_data.settings or {},
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return AssignmentResponse(
        id=str(assignment.id),
        course_id=str(assignment.course_id),
        name=assignment.name,
        term=assignment.term,
        version=assignment.version,
        due_at=assignment.due_at.isoformat() if assignment.due_at else None,
        settings=assignment.settings,
        created_at=assignment.created_at.isoformat() if assignment.created_at else "",
    )


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
    return [
        AssignmentResponse(
            id=str(a.id),
            course_id=str(a.course_id),
            name=a.name,
            term=a.term,
            version=a.version,
            due_at=a.due_at.isoformat() if a.due_at else None,
            settings=a.settings,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in assignments
    ]


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
    return AssignmentResponse(
        id=str(assignment.id),
        course_id=str(assignment.course_id),
        name=assignment.name,
        term=assignment.term,
        version=assignment.version,
        due_at=assignment.due_at.isoformat() if assignment.due_at else None,
        settings=assignment.settings,
        created_at=assignment.created_at.isoformat() if assignment.created_at else "",
    )


# ==================== Student Routes ====================

@router.post("/organizations/{org_id}/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
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
        raise HTTPException(status_code=400, detail="Student with this email already exists")

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

@router.post("/courses/{course_id}/enrollments", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
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
        raise HTTPException(status_code=400, detail="Student already enrolled in this course")

    enrollment = StudentService.enroll_student(
        db, course_id, enrollment_data.student_id, enrollment_data.role
    )
    return EnrollmentResponse(
        id=str(enrollment.id),
        course_id=str(enrollment.course_id),
        student_id=str(enrollment.student_id),
        role=enrollment.role,
        enrolled_at=enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else "",
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
        result.append(EnrollmentResponse(
            id=str(e.id),
            course_id=str(e.course_id),
            student_id=str(e.student_id),
            role=e.role,
            enrolled_at=e.enrolled_at.isoformat() if e.enrolled_at else "",
            student=StudentResponse(
                id=str(student.id),
                organization_id=str(student.organization_id),
                email=student.email,
                full_name=student.full_name,
                student_number=student.student_number,
                created_at=student.created_at.isoformat() if student.created_at else "",
            ) if student else None,
        ))
    return result


@router.delete("/courses/{course_id}/enrollments/{enrollment_id}")
async def remove_enrollment(
    course_id: str,
    enrollment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Remove a student from a course."""
    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.course_id == course_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()
    return {"success": True, "message": "Enrollment removed"}


# ==================== Assignment Version Routes ====================

@router.post("/assignments/{assignment_id}/versions", response_model=AssignmentVersionResponse, status_code=status.HTTP_201_CREATED)
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
    existing = AssignmentVersionService.get_version(db, assignment_id, version_data.version)
    if existing:
        raise HTTPException(status_code=400, detail=f"Version {version_data.version} already exists")

    # Deactivate other versions if this is the new active one
    if version_data.settings and version_data.settings.get("is_active"):
        db.query(AssignmentVersion).filter(
            AssignmentVersion.assignment_id == assignment_id,
            AssignmentVersion.is_active == True
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


@router.get("/assignments/{assignment_id}/versions", response_model=list[AssignmentVersionResponse])
async def list_assignment_versions(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_tenant),
):
    """List all versions of an assignment."""
    versions = AssignmentVersionService.get_versions_for_course(db, assignment_id)
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


@router.get("/assignments/{assignment_id}/versions/active", response_model=Optional[AssignmentVersionResponse])
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