"""Who may see a course, job or case: owners plus whoever it was shared with.

Professors see only their own courses unless an owner shares. A course, job
or case can be shared with selected faculty or with the whole workspace
(organization, or tenant for tenant-only workspaces); nothing is shared by
default. Shares only add access, and sharing a course reaches everything
under it (assignments, jobs, cases, dossiers, viva outcomes). Shared faculty
get the same rights as owners.

``access_scope`` resolves a caller's reach once per request so that list
endpoints do not query per row.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.backend.application.services import academic_access
from src.backend.models.database import (
    SHARE_RESOURCE_TYPES,
    Case,
    CourseInstructor,
    ResourceShare,
    User,
)

#: Course roles that may change a course's sharing (not TAs or assistants).
SHARE_MANAGER_ROLES = frozenset({"primary", "instructor"})


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def workspace_id(user: dict | None) -> str | None:
    """The workspace an organization-wide share is scoped to."""
    if not user:
        return None
    value = user.get("organization_id") or user.get("tenant_id")
    return str(value) if value else None


def _audience(user: dict):
    """SQL filter: shares addressed to this user or to their workspace."""
    clauses = []
    user_id = academic_access._user_id(user)
    if user_id and _is_uuid(user_id):
        clauses.append(ResourceShare.shared_with_user_id == user_id)
    workspace = workspace_id(user)
    if workspace:
        clauses.append(ResourceShare.shared_with_workspace == workspace)
    return or_(*clauses) if clauses else None


def shared_resource_ids(db: Session, user: dict | None, resource_type: str) -> set[str]:
    """Ids of ``resource_type`` items shared with the caller."""
    if not user:
        return set()
    audience = _audience(user)
    if audience is None:
        return set()
    rows = (
        db.query(ResourceShare.resource_id)
        .filter(ResourceShare.resource_type == resource_type, audience)
        .all()
    )
    return {str(row[0]) for row in rows}


def is_shared_with(
    db: Session, user: dict | None, resource_type: str, resource_id: str
) -> bool:
    """True when this item was shared with the caller or their workspace."""
    if not user or not resource_id:
        return False
    audience = _audience(user)
    if audience is None:
        return False
    return (
        db.query(ResourceShare.id)
        .filter(
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == str(resource_id),
            audience,
        )
        .first()
        is not None
    )


@dataclass(frozen=True)
class AccessScope:
    """Everything one caller can reach, resolved once per request."""

    user_id: str | None
    tenant_id: str | None
    organization_id: str | None
    is_admin: bool
    #: Courses taught by, shared with, or (admins) in the caller's organization.
    course_ids: frozenset[str] = field(default_factory=frozenset)
    shared_job_ids: frozenset[str] = field(default_factory=frozenset)
    shared_case_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_platform_admin(self) -> bool:
        """An admin bound to no organization or tenant (platform operator)."""
        return self.is_admin and not self.organization_id and not self.tenant_id


def access_scope(db: Session, user: dict | None) -> AccessScope:
    """Resolve the caller's reach (owned and shared courses, jobs and cases)."""
    if not user:
        return AccessScope(None, None, None, False)
    if not academic_access.is_registry_admin(user) and not _is_uuid(user.get("id")):
        # User ids are UUID columns: a non-UUID principal (API key, test
        # double) matches no instructor or share row, and comparing it in SQL
        # raises instead of returning nothing.
        return AccessScope(
            str(user.get("id") or "") or None,
            str(user["tenant_id"]) if user.get("tenant_id") else None,
            str(user["organization_id"]) if user.get("organization_id") else None,
            False,
        )
    visible = academic_access.visible_course_id_query(db, user)
    return AccessScope(
        user_id=str(user["id"]) if user.get("id") else None,
        tenant_id=str(user["tenant_id"]) if user.get("tenant_id") else None,
        organization_id=(
            str(user["organization_id"]) if user.get("organization_id") else None
        ),
        is_admin=user.get("role") == "admin",
        course_ids=frozenset(str(row[0]) for row in visible.all()),
        shared_job_ids=frozenset(shared_resource_ids(db, user, "job")),
        shared_case_ids=frozenset(shared_resource_ids(db, user, "case")),
    )


def can_manage_course_sharing(db: Session, user: dict | None, course_id: str) -> bool:
    """Primary instructors (role primary/instructor) may change a course's sharing."""
    user_id = academic_access._user_id(user)
    if not user_id or not course_id:
        return False
    link = (
        db.query(CourseInstructor.role)
        .filter(
            CourseInstructor.course_id == str(course_id),
            CourseInstructor.user_id == user_id,
        )
        .first()
    )
    return link is not None and (link[0] or "instructor") in SHARE_MANAGER_ROLES


def get_sharing(db: Session, resource_type: str, resource_id: str) -> dict:
    """``{"workspace": bool, "user_ids": [...]}`` for one item."""
    rows = (
        db.query(ResourceShare)
        .filter(
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == str(resource_id),
        )
        .all()
    )
    return {
        "workspace": any(row.shared_with_workspace for row in rows),
        "user_ids": sorted(
            str(row.shared_with_user_id) for row in rows if row.shared_with_user_id
        ),
    }


class SharingError(ValueError):
    """A share request that names users outside the sharer's workspace."""


def set_sharing(
    db: Session,
    resource_type: str,
    resource_id: str,
    *,
    sharer: dict,
    workspace: bool,
    user_ids: Iterable[str],
) -> dict:
    """Replace an item's shares; returns the new ``get_sharing`` value.

    Faculty can only be chosen from the sharer's own workspace, and sharing
    with the whole workspace means the sharer's workspace.

    Raises:
        SharingError: an unknown user, or one outside the sharer's workspace.
        ValueError: an unknown resource type.
    """
    if resource_type not in SHARE_RESOURCE_TYPES:
        raise ValueError(f"Unknown resource type: {resource_type}")
    sharer_workspace = workspace_id(sharer)
    wanted = {str(uid) for uid in user_ids} - {str(sharer.get("id") or "")}
    if wanted:
        found = {
            str(row.id): workspace_id(
                {"organization_id": row.organization_id, "tenant_id": row.tenant_id}
            )
            for row in db.query(User).filter(User.id.in_(wanted)).all()
        }
        if set(found) != wanted or any(ws != sharer_workspace for ws in found.values()):
            raise SharingError("Share only with faculty in your organization")
    if workspace and not sharer_workspace:
        raise SharingError("You belong to no organization to share with")

    db.query(ResourceShare).filter(
        ResourceShare.resource_type == resource_type,
        ResourceShare.resource_id == str(resource_id),
    ).delete(synchronize_session=False)
    granted_by = str(sharer["id"]) if sharer.get("id") else None
    for uid in sorted(wanted):
        db.add(
            ResourceShare(
                resource_type=resource_type,
                resource_id=str(resource_id),
                shared_with_user_id=uid,
                granted_by_id=granted_by,
            )
        )
    if workspace:
        db.add(
            ResourceShare(
                resource_type=resource_type,
                resource_id=str(resource_id),
                shared_with_workspace=sharer_workspace,
                granted_by_id=granted_by,
            )
        )
    db.commit()
    return get_sharing(db, resource_type, resource_id)


def case_in_scope(db: Session, case: Case, user: dict, scope: AccessScope) -> bool:
    """Whether the caller may see a case (and so, with full edit, change it).

    Its creator and assigned reviewer, anyone it or its course was shared
    with, the course's instructors, and admins of its organization.
    """
    user_id = str(user.get("id") or "")
    if user_id and user_id in {str(case.created_by_id), str(case.investigator_id)}:
        return True
    if str(case.id) in scope.shared_case_ids or scope.is_platform_admin:
        return True
    if case.assignment_id:
        course_id = academic_access.course_id_for_assignment(
            db, str(case.assignment_id)
        )
        if course_id and course_id in scope.course_ids:
            return True
    return bool(
        scope.is_admin
        and scope.organization_id
        and str(case.organization_id) == scope.organization_id
    )
