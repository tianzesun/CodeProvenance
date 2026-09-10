"""Student Service - Manage students and enrollments."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.backend.models.database import Student, Enrollment, Course, Assignment


class StudentService:
    """Service for managing student profiles and enrollments."""

    @staticmethod
    def create_student(
        db: Session,
        organization_id: str,
        email: str,
        full_name: str,
        student_number: Optional[str] = None,
    ) -> Student:
        """Create a new student profile."""
        student = Student(
            organization_id=organization_id,
            email=email,
            full_name=full_name,
            student_number=student_number,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return student

    @staticmethod
    def get_student_by_email(db: Session, organization_id: str, email: str) -> Optional[Student]:
        """Get student by email within organization."""
        return db.query(Student).filter(
            Student.organization_id == organization_id,
            Student.email == email
        ).first()

    @staticmethod
    def get_student_by_number(db: Session, organization_id: str, student_number: str) -> Optional[Student]:
        """Get student by student number within organization."""
        return db.query(Student).filter(
            Student.organization_id == organization_id,
            Student.student_number == student_number
        ).first()

    @staticmethod
    def get_or_create_student(
        db: Session,
        organization_id: str,
        email: str,
        full_name: str,
        student_number: Optional[str] = None,
    ) -> Student:
        """Get existing student or create new one."""
        # Try email first
        student = StudentService.get_student_by_email(db, organization_id, email)
        if student:
            return student
        # Try student number
        if student_number:
            student = StudentService.get_student_by_number(db, organization_id, student_number)
            if student:
                return student
        # Create new
        return StudentService.create_student(db, organization_id, email, full_name, student_number)

    @staticmethod
    def enroll_student(db: Session, course_id: str, student_id: str, role: str = "student") -> Enrollment:
        """Enroll a student in a course."""
        enrollment = Enrollment(
            course_id=course_id,
            student_id=student_id,
            role=role,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment

    @staticmethod
    def get_enrollment(db: Session, course_id: str, student_id: str) -> Optional[Enrollment]:
        """Get enrollment for student in course."""
        return db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student_id
        ).first()

    @staticmethod
    def get_course_enrollments(db: Session, course_id: str) -> list[Enrollment]:
        """Get all enrollments for a course."""
        return db.query(Enrollment).filter(Enrollment.course_id == course_id).all()

    @staticmethod
    def get_student_enrollments(db: Session, student_id: str) -> list[Enrollment]:
        """Get all courses a student is enrolled in."""
        return db.query(Enrollment).filter(Enrollment.student_id == student_id).all()


class AssignmentVersionService:
    """Service for managing assignment versions."""

    @staticmethod
    def create_version(
        db: Session,
        assignment_id: str,
        course_id: str,
        version: int,
        name: str,
        description: Optional[str] = None,
        starter_files: Optional[dict] = None,
        settings: Optional[dict] = None,
    ) -> "AssignmentVersion":
        from src.backend.models.database import AssignmentVersion
        av = AssignmentVersion(
            assignment_id=assignment_id,
            course_id=course_id,
            version=version,
            name=name,
            description=description,
            starter_files=starter_files,
            settings=settings,
        )
        db.add(av)
        db.commit()
        db.refresh(av)
        return av

    @staticmethod
    def get_active_version(db: Session, assignment_id: str) -> Optional["AssignmentVersion"]:
        from src.backend.models.database import AssignmentVersion
        return db.query(AssignmentVersion).filter(
            AssignmentVersion.assignment_id == assignment_id,
            AssignmentVersion.is_active == True
        ).first()

    @staticmethod
    def get_versions_for_course(db: Session, course_id: str) -> list["AssignmentVersion"]:
        from src.backend.models.database import AssignmentVersion
        return db.query(AssignmentVersion).filter(
            AssignmentVersion.course_id == course_id
        ).order_by(AssignmentVersion.version.desc()).all()

    @staticmethod
    def get_version(db: Session, assignment_id: str, version: int) -> Optional["AssignmentVersion"]:
        from src.backend.models.database import AssignmentVersion
        return db.query(AssignmentVersion).filter(
            AssignmentVersion.assignment_id == assignment_id,
            AssignmentVersion.version == version
        ).first()