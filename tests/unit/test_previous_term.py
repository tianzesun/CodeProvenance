"""Previous-term matching: prefilter, archive scope, and the comparison pass."""

import uuid

import pytest

from src.backend.application.services import previous_term
from src.backend.config.database import SessionLocal
from src.backend.models.database import (
    Assignment,
    Course,
    CourseInstructor,
    Job,
    Organization,
    User,
)

REUSED = """
def grade_average(scores):
    total = 0
    count = 0
    for score in scores:
        if score >= 0:
            total += score
            count += 1
    if count == 0:
        return 0
    return round(total / count, 2)


def letter(avg):
    if avg >= 80:
        return "A"
    if avg >= 70:
        return "B"
    return "C"
"""

RENAMED = REUSED.replace("scores", "marks").replace("total", "s").replace("count", "n")

OTHER = """
class Stack:
    def __init__(self):
        self.items = []

    def push(self, x):
        self.items.append(x)

    def pop(self):
        return self.items.pop() if self.items else None

    def peek(self):
        return self.items[-1] if self.items else None
"""

UNRELATED = """
import sys

def main(argv):
    with open(argv[1]) as handle:
        words = handle.read().split()
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    print(sorted(freq.items(), key=lambda kv: -kv[1])[:10])

main(sys.argv)
"""


def test_a_renamed_copy_of_an_earlier_submission_is_a_candidate() -> None:
    pairs = previous_term.candidate_pairs(
        {"bob.py": RENAMED, "cara.py": OTHER},
        {"[CSC108 Fall 2025] old.py": REUSED, "[CSC108 Fall 2025] x.py": UNRELATED},
    )

    assert ("bob.py", "[CSC108 Fall 2025] old.py") in pairs
    assert all(archived != "[CSC108 Fall 2025] x.py" for _, archived in pairs)


def test_only_the_closest_few_are_kept_per_submission() -> None:
    archive = {f"[T] copy{i}.py": REUSED + f"\n# {i}\n" for i in range(10)}

    pairs = previous_term.candidate_pairs({"bob.py": RENAMED}, archive, top_k=3)

    assert len(pairs) == 3


def test_starter_code_alone_does_not_make_a_candidate() -> None:
    pairs = previous_term.candidate_pairs(
        {"bob.py": REUSED}, {"[T] old.py": REUSED}, starter_sources=[REUSED]
    )

    assert pairs == []


@pytest.fixture
def offerings(job_tenant_id):
    """CSC108 now and in Fall 2025 (taught by the owner), plus a colleague's
    Fall 2025 CSC108 that was never shared."""
    ids = {k: str(uuid.uuid4()) for k in ("org", "owner", "colleague")}
    courses = {k: str(uuid.uuid4()) for k in ("now", "fall", "theirs", "other_code")}
    assignments = {k: str(uuid.uuid4()) for k in courses}
    jobs = {k: f"pt-{uuid.uuid4().hex[:12]}" for k in courses}
    with SessionLocal() as db:
        db.add(Organization(id=ids["org"], name=f"Previous term test {ids['org']}"))
        db.flush()
        for person in ("owner", "colleague"):
            db.add(
                User(
                    id=ids[person],
                    organization_id=ids["org"],
                    email=f"pt-{person}-{ids[person]}@example.com",
                    full_name=person,
                    password_hash="x",
                    role="professor",
                    is_active=True,
                )
            )
        spec = {
            "now": ("CSC108", "Fall 2026", "owner"),
            "fall": ("csc108", "Fall 2025", "owner"),
            "theirs": ("CSC108", "Fall 2025", "colleague"),
            "other_code": ("CSC148", "Winter 2026", "owner"),
        }
        for key, (code, term, teacher) in spec.items():
            db.add(
                Course(
                    id=courses[key],
                    organization_id=ids["org"],
                    name="Intro",
                    code=code,
                    term=term,
                )
            )
            db.flush()
            db.add(
                CourseInstructor(
                    course_id=courses[key], user_id=ids[teacher], role="primary"
                )
            )
            db.add(Assignment(id=assignments[key], course_id=courses[key], name="A1"))
            db.flush()
            db.add(
                Job(
                    id=jobs[key],
                    tenant_id=job_tenant_id,
                    name="pt",
                    status="completed",
                    assignment_id=assignments[key],
                )
            )
        db.commit()
    files = {
        jobs["fall"]: {"old.py": REUSED},
        jobs["theirs"]: {"secret.py": REUSED},
        jobs["other_code"]: {"stack.py": OTHER},
    }
    try:
        yield {
            "user": {
                "id": ids["owner"],
                "role": "professor",
                "organization_id": ids["org"],
            },
            "assignment": assignments["now"],
            "job": jobs["now"],
            "read": lambda job_id: files.get(job_id, {}),
        }
    finally:
        with SessionLocal() as db:
            db.query(Job).filter(Job.id.in_(list(jobs.values()))).delete(
                synchronize_session=False
            )
            db.query(Assignment).filter(
                Assignment.id.in_(list(assignments.values()))
            ).delete(synchronize_session=False)
            db.query(CourseInstructor).filter(
                CourseInstructor.course_id.in_(list(courses.values()))
            ).delete(synchronize_session=False)
            db.query(Course).filter(Course.id.in_(list(courses.values()))).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id.in_([ids["owner"], ids["colleague"]])).delete(
                synchronize_session=False
            )
            db.query(Organization).filter(Organization.id == ids["org"]).delete()
            db.commit()


def _archive(offerings, mode):
    with SessionLocal() as db:
        return previous_term.load_archive(
            db,
            mode=mode,
            user=offerings["user"],
            assignment_id=offerings["assignment"],
            exclude_job_id=offerings["job"],
            read_job_files=offerings["read"],
        )


def test_same_course_reads_only_earlier_offerings_you_can_open(offerings) -> None:
    archive = _archive(offerings, "same_course_only")

    assert list(archive.sources) == ["[csc108 Fall 2025] old.py"]
    assert archive.offerings == ["csc108 Fall 2025"]


def test_all_courses_widens_to_other_codes_but_not_unshared_ones(offerings) -> None:
    archive = _archive(offerings, "all_historical_courses")

    assert set(archive.sources) == {
        "[csc108 Fall 2025] old.py",
        "[CSC148 Winter 2026] stack.py",
    }


def test_off_reads_nothing(offerings) -> None:
    assert _archive(offerings, "off").sources == {}


def test_a_job_finds_its_reused_submission(monkeypatch) -> None:
    """End to end through the server's comparison pass."""
    from src.backend.api import server

    archive = previous_term.Archive(
        sources={
            "[CSC108 Fall 2025] old.py": REUSED,
            "[CSC108 Fall 2025] x.py": UNRELATED,
        },
        offerings=["CSC108 Fall 2025"],
    )
    monkeypatch.setattr(previous_term, "load_archive", lambda db, **kw: archive)
    monkeypatch.setattr(server, "_jobs", {"job-pt": {"id": "job-pt"}})
    monkeypatch.setattr(server, "_set_job_progress", lambda *a, **k: None)

    results, used = server._compare_with_previous_terms(
        "job-pt",
        "same_course_only",
        {"id": "u"},
        {"bob.py": RENAMED, "cara.py": OTHER},
        [],
        0.5,
        {},
        True,
    )

    pairs = {(r.file_a, r.file_b) for r in results}
    assert ("[CSC108 Fall 2025] old.py", "bob.py") in pairs
    assert all("cara.py" not in pair or "old.py" not in "".join(pair) for pair in pairs)
    assert set(used) <= set(archive.sources)
    info = server._jobs["job-pt"]["previous_term"]
    assert info["offerings"] == ["CSC108 Fall 2025"] and info["compared_pairs"] >= 1
