"""Previous-term matching: compare a class against earlier offerings' submissions.

A professor can ask for each submission to be checked against submissions
from earlier analyses:

* ``same_course_only``: other offerings of the same course (same course code),
* ``all_historical_courses``: every other course,

limited in both cases to courses the uploader can already open (their own,
and ones shared with them), so the comparison never reaches work they could
not see anyway.

Comparing every submission with a whole archive would multiply the run time,
so a cheap fingerprint prefilter first picks, for each submission, the few
archived submissions that share the most code with it; only those pairs go
through the full engines. Fingerprints common to the current class (shared
starter or class code) are ignored by the prefilter.
"""

from __future__ import annotations

import logging
import re
import zlib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MODES = ("same_course_only", "all_historical_courses")
#: Most recent earlier analyses read per run, and archived files kept.
MAX_ARCHIVE_JOBS = 30
MAX_ARCHIVE_FILES = 3000
#: Archived candidates fully compared per current submission.
TOP_K = 3
#: Share of a submission's fingerprints an archived one must contain.
MIN_OVERLAP = 0.3
#: A fingerprint in at least this share of the current class is class code.
COMMON_SHARE = 0.5
_GRAM = 6
_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")
_COMMENT = re.compile(r"#[^\n]*|//[^\n]*|/\*.*?\*/", re.DOTALL)
_KEYWORDS = frozenset(
    "if else elif for while return def class import from in not and or try except "
    "finally with as public private static void int float double char new break "
    "continue switch case lambda yield None True False null true false".split()
)


@dataclass
class Archive:
    """Earlier submissions to compare against, keyed by their display name."""

    sources: dict[str, str] = field(default_factory=dict)
    offerings: list[str] = field(default_factory=list)
    note: str = ""


def fingerprints(code: str) -> set[int]:
    """Hashed token 6-grams, with identifiers and literals normalized away."""
    tokens = []
    for token in _TOKEN.findall(_COMMENT.sub(" ", code)):
        if token[0].isdigit():
            tokens.append("0")
        elif token[0].isalpha() or token[0] == "_":
            tokens.append(token if token in _KEYWORDS else "v")
        else:
            tokens.append(token)
    return {
        zlib.crc32(" ".join(tokens[i : i + _GRAM]).encode())
        for i in range(max(0, len(tokens) - _GRAM + 1))
    }


def candidate_pairs(
    current: Mapping[str, str],
    archive: Mapping[str, str],
    *,
    starter_sources: Iterable[str] = (),
    top_k: int = TOP_K,
    min_overlap: float = MIN_OVERLAP,
) -> list[tuple[str, str]]:
    """``(current, archived)`` pairs worth a full comparison, best first per submission."""
    if not current or not archive:
        return []
    prints = {name: fingerprints(code) for name, code in current.items()}
    ignored: set[int] = set()
    for source in starter_sources:
        ignored |= fingerprints(source)
    if len(prints) >= 3:
        counts = Counter(fp for fps in prints.values() for fp in fps)
        floor = COMMON_SHARE * len(prints)
        ignored |= {fp for fp, n in counts.items() if n >= floor}

    archived = {name: fingerprints(code) - ignored for name, code in archive.items()}
    pairs: list[tuple[str, str]] = []
    for name, fps in prints.items():
        own = fps - ignored
        if len(own) < 5:
            continue
        scored = []
        for other, other_fps in archived.items():
            if not other_fps:
                continue
            overlap = len(own & other_fps) / min(len(own), len(other_fps))
            if overlap >= min_overlap:
                scored.append((overlap, other))
        scored.sort(reverse=True)
        pairs.extend((name, other) for _, other in scored[:top_k])
    return pairs


def load_archive(
    db: Session,
    *,
    mode: str,
    user: dict | None,
    assignment_id: str | None,
    exclude_job_id: str,
    read_job_files: Callable[[str], dict[str, str]],
) -> Archive:
    """Collect earlier submissions for ``mode`` that the uploader can access."""
    from src.backend.application.services import sharing
    from src.backend.models.database import Assignment, Course, Job

    if mode not in MODES:
        return Archive()
    current_course = None
    if assignment_id:
        assignment = db.get(Assignment, str(assignment_id))
        current_course = db.get(Course, assignment.course_id) if assignment else None
    if mode == "same_course_only" and not (current_course and current_course.code):
        return Archive(
            note="Choose a course with a course code to compare with its earlier offerings."
        )

    course_ids = set(sharing.access_scope(db, user).course_ids)
    if current_course is not None:
        course_ids.discard(str(current_course.id))
    if not course_ids:
        return Archive(note="No earlier courses you can access to compare with.")
    query = db.query(Course).filter(Course.id.in_(course_ids))
    if mode == "same_course_only":
        code = current_course.code.strip().lower()
        courses = [c for c in query.all() if (c.code or "").strip().lower() == code]
    else:
        courses = query.all()
    if not courses:
        return Archive(note="No earlier offerings of this course you can access.")
    labels = {
        str(c.id): " ".join(
            p for p in ((c.code or c.name or "").strip(), (c.term or "").strip()) if p
        )
        for c in courses
    }
    rows = (
        db.query(Job.id, Assignment.course_id)
        .join(Assignment, Job.assignment_id == Assignment.id)
        .filter(
            Assignment.course_id.in_(list(labels)),
            Job.status == "completed",
            Job.id != exclude_job_id,
        )
        .order_by(Job.created_at.desc())
        .limit(MAX_ARCHIVE_JOBS)
        .all()
    )

    archive = Archive()
    for job_id, course_id in rows:
        label = labels.get(str(course_id), "Earlier course")
        try:
            files = read_job_files(str(job_id))
        except OSError:
            continue
        added = False
        for name, code in files.items():
            if len(archive.sources) >= MAX_ARCHIVE_FILES:
                break
            archive.sources[f"[{label}] {Path(name).as_posix()}"] = code
            added = True
        if added and label not in archive.offerings:
            archive.offerings.append(label)
    if not archive.sources:
        archive.note = "Earlier offerings have no stored submissions to compare with."
    return archive
