"""Convert the ConPlag pair corpus into a classroom-style dataset layout."""

from __future__ import annotations

import csv
import json
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONPLAG_ROOT = PROJECT_ROOT / "data" / "datasets" / "conplag"
CONPLAG_ZIP = CONPLAG_ROOT / "conplag.zip"
CONPLAG_LABELS = CONPLAG_ROOT / "versions" / "labels.csv"
CONPLAG_TRAIN = CONPLAG_ROOT / "versions" / "train_pairs.csv"
CONPLAG_TEST = CONPLAG_ROOT / "versions" / "test_pairs.csv"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "datasets" / "conplag_classroom_java"


@dataclass(frozen=True)
class PairLabel:
    """Ground-truth label for a pair of submissions."""

    sub1: str
    sub2: str
    problem: str
    verdict: int
    split: str


def _read_pair_ids(path: Path) -> Set[str]:
    """Read a split file containing one pair id per line."""
    with path.open(encoding="utf-8", newline="") as handle:
        return {row[0].strip() for row in csv.reader(handle) if row and row[0].strip()}


def _read_labels() -> List[PairLabel]:
    """Load labeled pairs and attach the published train/test split."""
    train_pairs = _read_pair_ids(CONPLAG_TRAIN)
    test_pairs = _read_pair_ids(CONPLAG_TEST)

    labels: List[PairLabel] = []
    with CONPLAG_LABELS.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sub1 = str(row["sub1"]).strip()
            sub2 = str(row["sub2"]).strip()
            pair_id = f"{sub1}_{sub2}"
            if pair_id in train_pairs:
                split = "train"
            elif pair_id in test_pairs:
                split = "test"
            else:
                split = "unspecified"

            labels.append(
                PairLabel(
                    sub1=sub1,
                    sub2=sub2,
                    problem=str(row["problem"]).strip(),
                    verdict=int(row["verdict"]),
                    split=split,
                )
            )
    return labels


def _collect_problem_membership(
    labels: Iterable[PairLabel],
) -> Tuple[Dict[str, str], Dict[str, List[PairLabel]]]:
    """Map each submission id to exactly one problem and group labels by problem."""
    submission_to_problem: Dict[str, str] = {}
    labels_by_problem: Dict[str, List[PairLabel]] = defaultdict(list)

    for label in labels:
        labels_by_problem[label.problem].append(label)
        for submission_id in (label.sub1, label.sub2):
            existing = submission_to_problem.get(submission_id)
            if existing is not None and existing != label.problem:
                raise ValueError(
                    f"Submission {submission_id} appears in multiple problems: "
                    f"{existing} and {label.problem}"
                )
            submission_to_problem[submission_id] = label.problem

    return submission_to_problem, labels_by_problem


def _collect_raw_submissions(expected_ids: Set[str]) -> Dict[str, str]:
    """Extract one raw Java source file per submission id from the ConPlag zip."""
    sources: Dict[str, str] = {}

    with zipfile.ZipFile(CONPLAG_ZIP) as archive:
        for member in archive.namelist():
            path = Path(member)
            if (
                len(path.parts) >= 5
                and path.parts[0] == "versions"
                and path.parts[1] == "bplag_version_1"
                and path.suffix == ".java"
            ):
                submission_id = path.stem
                if submission_id not in expected_ids or submission_id in sources:
                    continue
                sources[submission_id] = archive.read(member).decode(
                    "utf-8", errors="ignore"
                )

    missing = expected_ids - set(sources)
    if missing:
        missing_preview = ", ".join(sorted(missing)[:10])
        raise FileNotFoundError(
            f"Missing {len(missing)} ConPlag submissions: {missing_preview}"
        )

    return sources


def _write_assignment_labels(path: Path, labels: Iterable[PairLabel]) -> None:
    """Write a pair label file for one assignment."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file_a", "file_b", "label", "split"])
        for label in labels:
            writer.writerow(
                [
                    f"{label.sub1}.java",
                    f"{label.sub2}.java",
                    "plagiarized" if label.verdict else "independent",
                    label.split,
                ]
            )


def _write_root_labels(path: Path, labels: Iterable[PairLabel]) -> None:
    """Write a global pair label file for the converted dataset."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["assignment_id", "file_a", "file_b", "label", "split"])
        for label in labels:
            assignment_id = f"assignment_{int(label.problem):02d}"
            writer.writerow(
                [
                    assignment_id,
                    f"{label.sub1}.java",
                    f"{label.sub2}.java",
                    "plagiarized" if label.verdict else "independent",
                    label.split,
                ]
            )


def _write_metadata(
    assignment_count: int,
    submission_count: int,
    labels: List[PairLabel],
) -> None:
    """Write dataset metadata for the benchmark UI."""
    metadata = {
        "name": "ConPlag Classroom Java",
        "description": (
            "Classroom-style Java submission corpus derived from the ConPlag contest "
            "plagiarism dataset. Organized as one assignment folder per original problem."
        ),
        "language": "java",
        "size": f"{submission_count} files",
        "files": submission_count,
        "created_by": "System",
        "source": "ConPlag",
        "assignments": assignment_count,
        "labeled_pairs": len(labels),
        "plagiarized_pairs": sum(label.verdict for label in labels),
        "independent_pairs": sum(1 for label in labels if label.verdict == 0),
    }
    (OUTPUT_ROOT / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def convert() -> None:
    """Generate the classroom-style ConPlag dataset."""
    labels = _read_labels()
    submission_to_problem, labels_by_problem = _collect_problem_membership(labels)
    submission_sources = _collect_raw_submissions(set(submission_to_problem))

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    assignments_root = OUTPUT_ROOT / "assignments"
    assignments_root.mkdir(parents=True, exist_ok=True)

    grouped_submission_ids: Dict[str, List[str]] = defaultdict(list)
    for submission_id, problem in submission_to_problem.items():
        grouped_submission_ids[problem].append(submission_id)

    for problem, submission_ids in sorted(
        grouped_submission_ids.items(), key=lambda item: int(item[0])
    ):
        assignment_id = f"assignment_{int(problem):02d}"
        assignment_root = assignments_root / assignment_id
        submissions_dir = assignment_root / "submissions"
        submissions_dir.mkdir(parents=True, exist_ok=True)

        for submission_id in sorted(submission_ids):
            content = submission_sources[submission_id]
            (submissions_dir / f"{submission_id}.java").write_text(
                content, encoding="utf-8"
            )

        _write_assignment_labels(
            assignment_root / "labels.csv", labels_by_problem[problem]
        )

    _write_root_labels(OUTPUT_ROOT / "labels.csv", labels)
    _write_metadata(
        assignment_count=len(grouped_submission_ids),
        submission_count=len(submission_to_problem),
        labels=labels,
    )

    summary = {
        "output": str(OUTPUT_ROOT),
        "assignments": len(grouped_submission_ids),
        "submissions": len(submission_to_problem),
        "pairs": len(labels),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    convert()
