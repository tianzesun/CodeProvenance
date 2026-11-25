"""Export instructors' pair reviews as a labelled student holdout.

Writes the folder layout ``class_evaluation_runner --student-holdout`` reads
(``docs/STUDENT_DATA_REQUEST_PACK.md``), one assignment folder per analysis:

    <output>/<job id>/problem.txt
    <output>/<job id>/pairs.csv          file_a,file_b,label,notes
    <output>/<job id>/submissions/submission001.py ...

Then:

    python scripts/export_review_holdout.py --job <job id> [--job ...] --output <dir>
    python -m src.backend.benchmark.runners.class_evaluation_runner --student-holdout <dir>

A review records what the instructor *did*, not what was true, so only these
become labels (``label_pair``):

* ``0`` (clean): the latest review is ``no_action`` and no viva on either
  student found a problem, or both students' vivas confirmed authorship.
* ``1`` (copy): the latest review is ``step_up_verification`` or
  ``formal_escalation`` and a viva on either student identified a breach.

Every other reviewed pair is left out and counted. Every submission of the
analysis is exported, labelled or not, because the runner scores the whole
class.

Limits:

* Only pairs the product flagged get reviewed, so copies it missed never appear
  here. Recall measured on this export is recall among flagged pairs only.
* File names are replaced by ``submissionNNN``, and the review rationale and
  viva notes are not exported. **The code itself is not scrubbed**: names,
  student numbers and emails in comments stay. Work through the anonymisation
  checklist in ``docs/STUDENT_DATA_REQUEST_PACK.md`` before the export leaves
  the server.

The export is student work. Run it only once the data steward has approved the
holdout, and keep the output off the repository: the script refuses an output
folder git would track, and one that already has files in it.

Read-only against the database: it only runs SELECTs.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

#: Dispositions that say the instructor saw nothing to act on.
CLEAR_DISPOSITIONS = frozenset({"no_action"})
#: Dispositions that say the instructor took the pair further.
ESCALATED_DISPOSITIONS = frozenset({"step_up_verification", "formal_escalation"})
#: Viva outcomes that mean the interview found a problem.
CONCERN_OUTCOMES = frozenset({"breach_identified", "concerns_unresolved"})
BREACH_OUTCOME = "breach_identified"
CONFIRMED_OUTCOME = "authorship_confirmed"
#: Used when a submission name has no extension, so the file still gets one.
FALLBACK_SUFFIX = ".txt"
PAIRS_HEADER = ("file_a", "file_b", "label", "notes")


@dataclass
class PairReviewRow:
    """The latest review of one pair, as the export needs it."""

    submission_a: str
    submission_b: str
    disposition: str


@dataclass
class ExportedClass:
    """One analysis, ready to write: pseudonymised files and labelled pairs."""

    name: str
    files: dict[str, str]
    rows: list[tuple[str, str, int, str]]
    skipped: Counter[str] = field(default_factory=Counter)


def label_pair(
    disposition: str, viva_a: str | None, viva_b: str | None
) -> tuple[int | None, str]:
    """Turn a pair's latest review and the two students' vivas into a label.

    Args:
        disposition: The pair's latest review disposition.
        viva_a: Viva outcome recorded for the first submission, if any.
        viva_b: Viva outcome recorded for the second submission, if any.

    Returns:
        ``(label, reason)``: ``label`` is ``1``, ``0`` or ``None`` (left out),
        and ``reason`` names the evidence (written to ``notes``) or why the
        pair was left out.
    """
    outcomes = {viva_a, viva_b} - {None}
    evidence = f"review:{disposition}"
    if outcomes:
        evidence += ";viva:" + ",".join(sorted(outcomes))
    if disposition in ESCALATED_DISPOSITIONS and BREACH_OUTCOME in outcomes:
        return 1, evidence
    if viva_a == CONFIRMED_OUTCOME and viva_b == CONFIRMED_OUTCOME:
        return 0, evidence
    if disposition in CLEAR_DISPOSITIONS:
        if outcomes & CONCERN_OUTCOMES:
            return None, "review cleared it but a viva found a problem"
        return 0, evidence
    if disposition in ESCALATED_DISPOSITIONS:
        return None, "escalated without a viva that identified a breach"
    return None, f"disposition {disposition} is not a verdict"


def pseudonymise(names: list[str]) -> dict[str, str]:
    """Map each submission name to ``submissionNNN`` plus its extension.

    Args:
        names: Submission names as stored (often the student's name).

    Returns:
        Mapping of original name to pseudonymous file name, numbered in sorted
        name order so a rerun gives the same names.
    """
    width = max(3, len(str(len(names))))
    mapping: dict[str, str] = {}
    for index, name in enumerate(sorted(set(names)), start=1):
        suffix = PurePosixPath(name).suffix.lower() or FALLBACK_SUFFIX
        mapping[name] = f"submission{index:0{width}d}{suffix}"
    return mapping


def build_class(
    name: str,
    sources: dict[str, str],
    reviews: list[PairReviewRow],
    vivas: dict[str, str],
) -> ExportedClass:
    """Build one assignment folder's contents from an analysis.

    Args:
        name: Folder and ``problem.txt`` id (the job id).
        sources: Submission name to its code.
        reviews: The latest review of each reviewed pair.
        vivas: Submission name to its recorded viva outcome.

    Returns:
        The pseudonymised files, the labelled ``pairs.csv`` rows, and counts of
        the pairs left out, by reason.
    """
    present = {sub: code for sub, code in sources.items() if code.strip()}
    mapping = pseudonymise(list(present))
    exported = ExportedClass(
        name=name, files={mapping[sub]: code for sub, code in present.items()}, rows=[]
    )
    for review in reviews:
        a, b = review.submission_a, review.submission_b
        if a not in present or b not in present:
            exported.skipped["submission code not found"] += 1
            continue
        label, reason = label_pair(review.disposition, vivas.get(a), vivas.get(b))
        if label is None:
            exported.skipped[reason] += 1
            continue
        exported.rows.append((mapping[a], mapping[b], label, reason))
    exported.rows.sort()
    return exported


def latest_reviews(rows: list[tuple[str, str, str]]) -> list[PairReviewRow]:
    """Keep the newest review of each pair, whichever way round it was stored.

    Args:
        rows: ``(submission_a, submission_b, disposition)`` in ``reviewed_at``
            order, oldest first.

    Returns:
        One row per unordered pair: its latest review.
    """
    latest: dict[tuple[str, str], PairReviewRow] = {}
    for a, b, disposition in rows:
        latest[(min(a, b), max(a, b))] = PairReviewRow(a, b, disposition)
    return list(latest.values())


def write_class(output: Path, exported: ExportedClass) -> None:
    """Write one assignment folder in the student-holdout layout.

    Args:
        output: The export root.
        exported: The analysis to write.
    """
    folder = output / exported.name
    submissions = folder / "submissions"
    submissions.mkdir(parents=True)
    (folder / "problem.txt").write_text(exported.name + "\n")
    for file_name, code in exported.files.items():
        (submissions / file_name).write_text(code, encoding="utf-8")
    with open(folder / "pairs.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(PAIRS_HEADER)
        writer.writerows(exported.rows)


def output_problem(output: Path) -> str | None:
    """Say why *output* must not be used, or ``None`` when it is safe.

    Args:
        output: The requested export folder.

    Returns:
        A reason to refuse, or ``None``.
    """
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        return f"{output} already exists and is not an empty folder"
    resolved = output.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        probe = resolved / "pairs.csv"
        ignored = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(probe)],
            check=False,
        )
        if ignored.returncode != 0:
            return f"{output} is inside the repository and git would track it"
    return None


def load_class(db: object, job_id: str) -> ExportedClass | None:
    """Read one analysis's code, reviews and vivas and build its folder.

    Args:
        db: Database session.
        job_id: The analysis (job) id.

    Returns:
        The class to write, or ``None`` when the analysis does not exist.
    """
    from src.backend.api.server import _read_job_submission_sources
    from src.backend.models.database import Job, PairReview, Submission, VivaOutcome

    if db.query(Job.id).filter(Job.id == job_id).first() is None:
        return None
    subs = db.query(Submission).filter(Submission.job_id == job_id).all()
    sources = _read_job_submission_sources(job_id, subs)
    review_rows = (
        db.query(
            PairReview.submission_a, PairReview.submission_b, PairReview.disposition
        )
        .filter(PairReview.job_id == job_id)
        .order_by(PairReview.reviewed_at, PairReview.created_at)
        .all()
    )
    vivas = dict(
        db.query(VivaOutcome.submission_name, VivaOutcome.outcome)
        .filter(VivaOutcome.job_id == job_id)
        .all()
    )
    return build_class(
        job_id, sources, latest_reviews([tuple(r) for r in review_rows]), vivas
    )


def main() -> int:
    """Export the given analyses; exit 1 if nothing could be written."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--job",
        action="append",
        required=True,
        help="analysis (job) id; repeat for more",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="new or empty folder"
    )
    args = parser.parse_args()

    problem = output_problem(args.output)
    if problem:
        print(f"Refusing: {problem}.", file=sys.stderr)
        return 1

    from src.backend.config.database import SessionLocal

    exported: list[ExportedClass] = []
    with SessionLocal() as db:
        for job_id in dict.fromkeys(args.job):
            loaded = load_class(db, job_id)
            if loaded is None:
                print(f"{job_id}: not found, skipped")
            else:
                exported.append(loaded)

    written = 0
    for item in exported:
        labels = Counter(label for _, _, label, _ in item.rows)
        print(
            f"{item.name}: {len(item.files)} submissions, "
            f"{labels[1]} copies, {labels[0]} clean pairs"
        )
        for reason, count in sorted(item.skipped.items()):
            print(f"  left out {count}: {reason}")
        if not item.rows:
            print("  no labelled pairs, folder not written")
            continue
        write_class(args.output, item)
        written += 1

    if not written:
        print("Nothing written.")
        return 1
    print(
        f"Wrote {written} assignment folder(s) to {args.output}. The code is not scrubbed: "
        "check it against the anonymisation checklist before it leaves this server."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
