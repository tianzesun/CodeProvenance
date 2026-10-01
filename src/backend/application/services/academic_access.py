"""Academic access policy shared by the dashboard API and the academic router.

The RBAC matrix in :mod:`src.backend.api.middleware.auth` states *what* each
dashboard role may do. This module answers the follow-up question: *which rows*
do those rights apply to?

Two rules, one implementation, deliberately used by both route layers so the
dashboard endpoints (``src.backend.api.server``) and the academic router
(``src.backend.api.routes.academic``) cannot drift apart:

* An **admin** owns the academic registry, so every course of their
  organization is readable and writable.
* A **professor** may read and manage only the courses a ``course_instructors``
  row ties them to. Courses that still need an instructor stay invisible to
  professors until an admin performs that assignment — that hand-off (admin
  assigns a user to a course, the professor then creates the assignments) is
  the supported workflow, and it keeps "my courses" honest.

Row-level checks are pure predicates where possible
(:func:`is_registry_admin`, :func:`can_manage_assignments`) so the policy is
unit-testable without a database.
"""

from __future__ import annotations

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from src.backend.api.middleware.auth import has_permission
from src.backend.models.database import Assignment, Course, CourseInstructor

#: 403 message used whenever a caller may not manage a course's assignments.
#: Worded for both failure modes: an admin (whose role holds no
#: ``assignment:manage`` right) and a professor who is not linked to the course.
ASSIGNMENT_MANAGER_REQUIRED = (
    "Only the professor assigned to a course can manage its assignments"
)


def _user_id(user: dict | None) -> str | None:
    """Return the caller's user id as a string, or None."""
    if not isinstance(user, dict):
        return None
    raw = user.get("id")
    return str(raw) if raw else None


def _organization_id(user: dict | None) -> str | None:
    """Return the caller's organization id as a string, or None."""
    if not isinstance(user, dict):
        return None
    raw = user.get("organization_id")
    return str(raw) if raw else None


def is_registry_admin(user: dict | None) -> bool:
    """Return True when the caller holds the registry-wide academic rights."""
    return has_permission(user, "course:manage")


def can_manage_assignments(user: dict | None) -> bool:
    """Return True when the caller's *role* may manage assignments at all.

    The admin role intentionally returns False: assignments belong to the
    professor teaching the course (see ``ROLE_PERMISSIONS``).
    """
    return has_permission(user, "assignment:manage")


def is_course_instructor(db: Session, user: dict | None, course_id: str) -> bool:
    """Return True when a ``course_instructors`` row links the user to the course."""
    user_id = _user_id(user)
    if not user_id or not course_id:
        return False
    return (
        db.query(CourseInstructor.id)
        .filter(
            CourseInstructor.course_id == course_id,
            CourseInstructor.user_id == user_id,
        )
        .first()
        is not None
    )


def visible_course_id_query(db: Session, user: dict | None) -> Query:
    """Return a query yielding the ids of courses the caller may read.

    Admins get every course in their organization (all of them when they carry
    no organization, e.g. a platform-wide operator); professors get only the
    courses they are assigned to, across every term and year — history
    included, so past offerings and their assignments remain reachable.
    """
    if is_registry_admin(user):
        query = db.query(Course.id)
        organization_id = _organization_id(user)
        if organization_id:
            query = query.filter(Course.organization_id == organization_id)
        return query

    user_id = _user_id(user)
    if not user_id:
        # No identity and no registry rights: match nothing rather than all.
        return db.query(Course.id).filter(false())
    return db.query(CourseInstructor.course_id).filter(
        CourseInstructor.user_id == user_id
    )


def can_read_course(db: Session, user: dict | None, course_id: str) -> bool:
    """Return True when the caller may read ``course_id``."""
    if not course_id:
        return False
    if is_registry_admin(user):
        organization_id = _organization_id(user)
        if not organization_id:
            return True
        return (
            db.query(Course.id)
            .filter(
                Course.id == course_id,
                Course.organization_id == organization_id,
            )
            .first()
            is not None
        )
    return is_course_instructor(db, user, course_id)


def can_manage_course_assignments(
    db: Session, user: dict | None, course_id: str
) -> bool:
    """Return True when the caller may create/delete assignments in a course.

    Requires both the role right (``assignment:manage``) *and* the instructor
    link to this specific course, so an admin cannot author assignments and a
    professor cannot touch a course they do not teach.
    """
    if not can_manage_assignments(user):
        return False
    return is_course_instructor(db, user, course_id)


def course_id_for_assignment(db: Session, assignment_id: str) -> str | None:
    """Return the course id owning ``assignment_id``, or None when unknown."""
    if not assignment_id:
        return None
    row = db.query(Assignment.course_id).filter(Assignment.id == assignment_id).first()
    return str(row[0]) if row and row[0] else None
