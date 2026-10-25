"""Professors see only their own courses unless an owner shares."""

import uuid

import pytest

from src.backend.api import server
from src.backend.application.services import academic_access, sharing
from src.backend.config.database import SessionLocal
from src.backend.models.database import (
    Assignment,
    Case,
    Course,
    CourseInstructor,
    Job,
    Organization,
    ResourceShare,
    User,
)

PEOPLE = ("owner", "ta", "colleague", "outsider")


@pytest.fixture
def world():
    """One organization's course with an owner and a TA, a colleague, and an
    outsider from another organization."""
    ids = {name: str(uuid.uuid4()) for name in (*PEOPLE, "org", "other_org")}
    ids.update(
        course=str(uuid.uuid4()),
        assignment=str(uuid.uuid4()),
        job=str(uuid.uuid4()),
        case=str(uuid.uuid4()),
    )
    with SessionLocal() as db:
        db.add(Organization(id=ids["org"], name=f"Sharing test {ids['org']}"))
        db.add(
            Organization(id=ids["other_org"], name=f"Sharing test {ids['other_org']}")
        )
        db.flush()
        for name in PEOPLE:
            db.add(
                User(
                    id=ids[name],
                    organization_id=ids["other_org" if name == "outsider" else "org"],
                    email=f"sharing-{name}-{ids[name]}@example.com",
                    full_name=name,
                    password_hash="x",
                    role="professor",
                    is_active=True,
                )
            )
        db.add(
            Course(id=ids["course"], organization_id=ids["org"], name="Sharing test")
        )
        db.flush()
        db.add(
            CourseInstructor(
                course_id=ids["course"], user_id=ids["owner"], role="primary"
            )
        )
        db.add(CourseInstructor(course_id=ids["course"], user_id=ids["ta"], role="ta"))
        db.add(Assignment(id=ids["assignment"], course_id=ids["course"], name="A1"))
        db.flush()
        db.add(
            Job(
                id=ids["job"],
                name="sharing test",
                status="completed",
                assignment_id=ids["assignment"],
            )
        )
        db.add(
            Case(
                id=ids["case"],
                organization_id=ids["org"],
                title="Sharing test",
                assignment_id=ids["assignment"],
                created_by_id=ids["owner"],
            )
        )
        db.commit()
    try:
        yield ids
    finally:
        with SessionLocal() as db:
            db.query(ResourceShare).filter(
                ResourceShare.resource_id.in_([ids["course"], ids["job"], ids["case"]])
            ).delete(synchronize_session=False)
            db.query(Case).filter(Case.id == ids["case"]).delete()
            db.query(Job).filter(Job.id == ids["job"]).delete()
            db.query(Assignment).filter(Assignment.id == ids["assignment"]).delete()
            db.query(CourseInstructor).filter(
                CourseInstructor.course_id == ids["course"]
            ).delete()
            db.query(Course).filter(Course.id == ids["course"]).delete()
            db.query(User).filter(User.id.in_([ids[n] for n in PEOPLE])).delete(
                synchronize_session=False
            )
            db.query(Organization).filter(
                Organization.id.in_([ids["org"], ids["other_org"]])
            ).delete(synchronize_session=False)
            db.commit()


def _user(world, name: str) -> dict:
    org = world["other_org" if name == "outsider" else "org"]
    return {"id": world[name], "role": "professor", "organization_id": org}


def _reach(world, name: str) -> dict[str, bool]:
    """What one person can reach: the course, its job and its case."""
    user = _user(world, name)
    with SessionLocal() as db:
        scope = sharing.access_scope(db, user)
        case = db.get(Case, world["case"])
        return {
            "course": academic_access.can_read_course(db, user, world["course"]),
            "job": server._job_is_accessible(
                {"id": world["job"], "assignment_id": world["assignment"]}, user, scope
            ),
            "case": sharing.case_in_scope(db, case, user, scope),
        }


def _share(world, resource: str, *, workspace=False, user_ids=()) -> None:
    with SessionLocal() as db:
        sharing.set_sharing(
            db,
            resource,
            world[resource],
            sharer=_user(world, "owner"),
            workspace=workspace,
            user_ids=[world[n] for n in user_ids],
        )


ALL = {"course": True, "job": True, "case": True}
NONE = {"course": False, "job": False, "case": False}


def test_everything_is_private_to_the_course_by_default(world) -> None:
    assert _reach(world, "owner") == ALL
    assert _reach(world, "ta") == ALL  # on the course, any role
    assert _reach(world, "colleague") == NONE
    assert _reach(world, "outsider") == NONE


def test_sharing_a_course_with_one_colleague_reaches_everything_under_it(world) -> None:
    _share(world, "course", user_ids=["colleague"])

    assert _reach(world, "colleague") == ALL
    assert _reach(world, "outsider") == NONE


def test_sharing_with_the_organization_excludes_other_organizations(world) -> None:
    _share(world, "course", workspace=True)

    assert _reach(world, "colleague") == ALL
    assert _reach(world, "outsider") == NONE


def test_items_can_be_shared_without_their_course(world) -> None:
    _share(world, "job", user_ids=["colleague"])
    assert _reach(world, "colleague") == {"course": False, "job": True, "case": False}

    _share(world, "case", user_ids=["colleague"])
    assert _reach(world, "colleague") == {"course": False, "job": True, "case": True}


def test_unsharing_makes_it_private_again(world) -> None:
    _share(world, "course", workspace=True, user_ids=["colleague"])
    _share(world, "course")

    assert _reach(world, "colleague") == NONE
    with SessionLocal() as db:
        assert sharing.get_sharing(db, "course", world["course"]) == {
            "workspace": False,
            "user_ids": [],
        }


def test_only_faculty_in_the_sharers_organization_can_be_added(world) -> None:
    with pytest.raises(sharing.SharingError):
        _share(world, "course", user_ids=["outsider"])
    with pytest.raises(sharing.SharingError), SessionLocal() as db:
        sharing.set_sharing(
            db,
            "course",
            world["course"],
            sharer=_user(world, "owner"),
            workspace=False,
            user_ids=[str(uuid.uuid4())],  # no such user
        )


def test_primary_instructors_manage_sharing_but_tas_do_not(world) -> None:
    with SessionLocal() as db:
        assert sharing.can_manage_course_sharing(
            db, _user(world, "owner"), world["course"]
        )
        assert not sharing.can_manage_course_sharing(
            db, _user(world, "ta"), world["course"]
        )
        assert not sharing.can_manage_course_sharing(
            db, _user(world, "colleague"), world["course"]
        )
