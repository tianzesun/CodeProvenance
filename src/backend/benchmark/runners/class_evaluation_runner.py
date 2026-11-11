"""Class-level evaluation: accuracy measured the way a professor sees it.

The engine evaluation harness scores labelled pairs one at a time, so it never
exercises what a Plagiarism Checker job does with a whole class (removing code
most of the class shares, holding tiny files at review), and its negatives are
often hand-picked hard cases rather than a sample of the class. Its false
positive rate is therefore not the share of a class a professor would see
flagged.

This runner scores *every* pair in each class through the production path
(``BatchDetectionService.compare_all_pairs`` with class inference and the small
file cap) and reports, at the default review policy's review and high bands
(what a professor sees) and at the fixed 0.75/0.95 cut-offs of earlier
baselines:

* ``flag_rate``: share of all pairs in the class that would be flagged,
* ``recall``: labelled copies caught,
* ``hard_negative_rate``: labelled innocent pairs flagged (hard cases),

plus AUC over the labelled pairs and how much class-shared code was removed.
Every labelled pair is also written with its per-engine features, fusion
contributions and review hold, so a false flag can be traced to the engines
that produced it.

Datasets: ``kaggle_student_code`` (one class, labelled pairs in a CSV),
``IR-Plag-Dataset`` (each case is a class; the original against each other
file is labelled) and ``conplag`` (each contest problem is a class; its
annotated pairs are labelled). An institution's labelled holdout
(``--student-holdout``, the layout in ``docs/STUDENT_DATA_REQUEST_PACK.md``)
is read the same way, one class per assignment folder. Output goes to
``reports/class_evaluation/``.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from src.backend.engines.scoring.review_policy import BAND_THRESHOLDS

logger = logging.getLogger(__name__)

#: Where the default review policy puts a pair in front of a professor.
REVIEW_MIN = BAND_THRESHOLDS["default"]["review_min"]
HIGH_MIN = BAND_THRESHOLDS["default"]["high_min"]
#: The bands, plus the fixed cut-offs earlier baselines were reported at.
THRESHOLDS = tuple(sorted({REVIEW_MIN, HIGH_MIN, 0.5, 0.75, 0.85, 0.95}))
DATASET_ROOT = Path(__file__).resolve().parents[4] / "data" / "datasets"


@dataclass
class ClassSet:
    """One class: every submission, and the labels known for some pairs."""

    name: str
    files: dict[str, str]
    labels: dict[tuple[str, str], int]


@dataclass
class ClassResult:
    name: str
    submissions: int
    pairs: int
    labelled_pairs: int
    labelled_copies: int
    common_code_lines: int
    auc: float | None
    at_threshold: dict[str, dict[str, float]] = field(default_factory=dict)


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def load_kaggle(root: Path = DATASET_ROOT) -> Iterator[ClassSet]:
    base = root / "kaggle_student_code"
    files = {
        f.name: f.read_text(errors="ignore")
        for f in sorted(base.glob("submission*.py"))
    }
    labels: dict[tuple[str, str], int] = {}
    with open(base / "cheating_dataset.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["File_1"] in files and row["File_2"] in files:
                labels[_pair(row["File_1"], row["File_2"])] = int(row["Label"])
    yield ClassSet("kaggle_student_code", files, labels)


def load_irplag(root: Path = DATASET_ROOT) -> Iterator[ClassSet]:
    for case in sorted((root / "IR-Plag-Dataset").glob("case-*")):
        files = {
            str(f.relative_to(case)): f.read_text(errors="ignore")
            for f in sorted(case.rglob("*.java"))
        }
        original = next((k for k in files if k.startswith("original/")), None)
        if original is None:
            continue
        labels = {
            _pair(original, k): int(k.startswith("plagiarized/"))
            for k in files
            if k != original
        }
        yield ClassSet(f"IR-Plag/{case.name}", files, labels)


def load_conplag(root: Path = DATASET_ROOT) -> Iterator[ClassSet]:
    """Each contest problem is a class: every submission to it, paired.

    Reads the layout the learned-fusion training uses: ``versions/labels.csv``
    (``sub1,sub2,problem,verdict``) and ``versions/version_1/<sub1>_<sub2>/``
    holding ``<sub>.java`` for both submissions.
    """
    versions = root / "conplag" / "versions"
    files: dict[str, dict[str, str]] = {}
    labels: dict[str, dict[tuple[str, str], int]] = {}
    with open(versions / "labels.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            sub1, sub2 = row["sub1"].strip(), row["sub2"].strip()
            problem = row["problem"].strip()
            pair_dir = versions / "version_1" / f"{sub1}_{sub2}"
            paths = {sub: pair_dir / f"{sub}.java" for sub in (sub1, sub2)}
            if not all(path.exists() for path in paths.values()):
                logger.warning("Skipping ConPlag pair %s_%s: missing code", sub1, sub2)
                continue
            class_files = files.setdefault(problem, {})
            for sub, path in paths.items():
                class_files.setdefault(f"{sub}.java", path.read_text(errors="ignore"))
            labels.setdefault(problem, {})[_pair(f"{sub1}.java", f"{sub2}.java")] = int(
                row["verdict"]
            )
    for problem in sorted(files):
        yield ClassSet(f"conplag/{problem}", files[problem], labels[problem])


def load_student_holdout(holdout: Path) -> Iterator[ClassSet]:
    """Each assignment folder of a labelled student holdout is a class.

    The layout is the one ``docs/STUDENT_DATA_REQUEST_PACK.md`` asks for:
    ``<holdout>/<assignment>/`` with ``submissions/``, ``pairs.csv``
    (``file_a,file_b,label,notes``; label ``1`` plagiarism, ``0`` clean) and an
    optional ``problem.txt`` naming the assignment. Every submission is scored,
    not only the labelled ones. Rows naming a missing file or another label are
    skipped with a warning.
    """
    for folder in sorted(p for p in holdout.iterdir() if p.is_dir()):
        submissions = folder / "submissions"
        pairs_csv = folder / "pairs.csv"
        if not (submissions.is_dir() and pairs_csv.exists()):
            logger.warning("Skipping %s: needs submissions/ and pairs.csv", folder)
            continue
        files = {
            f.name: f.read_text(errors="ignore")
            for f in sorted(submissions.iterdir())
            if f.is_file()
        }
        labels: dict[tuple[str, str], int] = {}
        with open(pairs_csv, newline="") as handle:
            for row in csv.DictReader(handle):
                file_a, file_b = row["file_a"].strip(), row["file_b"].strip()
                label = row["label"].strip()
                if (
                    file_a not in files
                    or file_b not in files
                    or label not in ("0", "1")
                ):
                    logger.warning("Skipping %s row %s,%s", pairs_csv, file_a, file_b)
                    continue
                labels[_pair(file_a, file_b)] = int(label)
        problem_txt = folder / "problem.txt"
        problem = problem_txt.read_text().strip() if problem_txt.exists() else ""
        yield ClassSet(f"student/{problem or folder.name}", files, labels)


LOADERS = {
    "kaggle_student_code": load_kaggle,
    "IR-Plag-Dataset": load_irplag,
    "conplag": load_conplag,
}


def _auc(labelled: list[tuple[int, float]]) -> float | None:
    positives = [s for y, s in labelled if y == 1]
    negatives = [s for y, s in labelled if y == 0]
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return round(wins / (len(positives) * len(negatives)), 4)


def evaluate_class(
    class_set: ClassSet,
    scores: dict[tuple[str, str], float],
    common_code_lines: int = 0,
) -> ClassResult:
    """Summarise one class's pair scores against its labels."""
    labelled = [(y, scores[p]) for p, y in class_set.labels.items() if p in scores]
    copies = sum(1 for y, _ in labelled if y == 1)
    innocents = sum(1 for y, _ in labelled if y == 0)
    result = ClassResult(
        name=class_set.name,
        submissions=len(class_set.files),
        pairs=len(scores),
        labelled_pairs=len(labelled),
        labelled_copies=copies,
        common_code_lines=common_code_lines,
        auc=_auc(labelled),
    )
    for threshold in THRESHOLDS:
        flagged = sum(1 for s in scores.values() if s >= threshold)
        caught = sum(1 for y, s in labelled if y == 1 and s >= threshold)
        hard = sum(1 for y, s in labelled if y == 0 and s >= threshold)
        result.at_threshold[f"{threshold:.2f}"] = {
            "flagged": flagged,
            "flag_rate": round(flagged / len(scores), 4) if scores else 0.0,
            "recall": round(caught / copies, 4) if copies else 0.0,
            "hard_negative_rate": round(hard / innocents, 4) if innocents else 0.0,
        }
    return result


def labelled_pair_rows(
    class_set: ClassSet,
    scores: dict[tuple[str, str], float],
    details: dict[tuple[str, str], dict],
) -> list[dict]:
    """One row per scored labelled pair: label, score and its engine breakdown."""
    return [
        {
            "class": class_set.name,
            "file_a": pair[0],
            "file_b": pair[1],
            "label": label,
            "score": scores[pair],
            **details.get(pair, {}),
        }
        for pair, label in sorted(class_set.labels.items())
        if pair in scores
    ]


def score_class(
    class_set: ClassSet, max_workers: int | None = None
) -> tuple[dict, int, dict]:
    """Score every pair in a class the way a Plagiarism Checker job does.

    Returns the pair scores, the class-shared lines removed, and each labelled
    pair's features, contributions and review hold.
    """
    from src.backend.application.services.batch_detection_service import (
        MIN_EVIDENCE_TOKENS,
        BatchDetectionService,
    )

    service = BatchDetectionService(
        infer_common_code=True, min_evidence_tokens=MIN_EVIDENCE_TOKENS
    )
    results = service.compare_all_pairs(class_set.files, max_workers=max_workers)
    common = getattr(service.starter_remover, "inferred_common_lines", 0) or 0
    scores = {_pair(r.file_a, r.file_b): float(r.score) for r in results}
    details = {
        _pair(r.file_a, r.file_b): {
            "features": r.features,
            "contributions": r.contributions,
            "review_hold": r.review_hold,
        }
        for r in results
        if _pair(r.file_a, r.file_b) in class_set.labels
    }
    return scores, common, details


def run_class_evaluation(
    datasets: tuple[str, ...] = ("kaggle_student_code", "IR-Plag-Dataset", "conplag"),
    output_dir: Path = Path("reports/class_evaluation"),
    root: Path = DATASET_ROOT,
    max_workers: int | None = None,
    student_holdout: Path | None = None,
) -> dict:
    """Run the evaluation and write JSON + Markdown reports; returns the report."""
    started = time.time()
    classes: list[ClassResult] = []
    pair_rows: list[dict] = []
    class_sets = [class_set for name in datasets for class_set in LOADERS[name](root)]
    if student_holdout is not None:
        class_sets.extend(load_student_holdout(student_holdout))
    for class_set in class_sets:
        scores, common, details = score_class(class_set, max_workers=max_workers)
        classes.append(evaluate_class(class_set, scores, common))
        pair_rows.extend(labelled_pair_rows(class_set, scores, details))
        logger.info("Scored %s (%d pairs)", class_set.name, len(scores))
    report = {
        "run_id": f"CLASS_EVAL_{datetime.now():%Y%m%d_%H%M%S}",
        "runtime_seconds": round(time.time() - started, 1),
        "classes": [asdict(c) for c in classes],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{report['run_id']}.json").write_text(json.dumps(report, indent=2))
    (output_dir / f"{report['run_id']}.md").write_text(render_markdown(report))
    with open(output_dir / f"{report['run_id']}_labelled_pairs.jsonl", "w") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in pair_rows)
    return report


def render_markdown(report: dict) -> str:
    """Render the per-class table at the default review and high bands."""
    review, high = f"{REVIEW_MIN:.2f}", f"{HIGH_MIN:.2f}"
    lines = [
        "# Class-level evaluation",
        "",
        f"- Run: `{report['run_id']}` ({report['runtime_seconds']}s)",
        "- Every pair in each class scored through the production path.",
        (
            f"- Bands are the default review policy's: review from {review}, "
            f"high from {high}. The JSON also has 0.75 and 0.95 for earlier baselines."
        ),
        (
            "- Shown: share of all pairs in the band. Recall: labelled copies in the band. "
            "Hard neg.: labelled innocent pairs in the band (often hand-picked look-alikes)."
        ),
        "",
        (
            f"| Class | Subs | Pairs | AUC | Shown @{review} | Recall @{review} "
            f"| Hard neg. @{review} | Shown @{high} | Recall @{high} | Hard neg. @{high} "
            "| Shared lines removed |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for c in report["classes"]:
        low, top = c["at_threshold"][review], c["at_threshold"][high]
        auc = "n/a" if c["auc"] is None else f"{c['auc']:.4f}"
        lines.append(
            f"| {c['name']} | {c['submissions']} | {c['pairs']} | {auc} "
            f"| {low['flag_rate']:.1%} | {low['recall']:.1%} "
            f"| {low['hard_negative_rate']:.1%} "
            f"| {top['flag_rate']:.1%} | {top['recall']:.1%} "
            f"| {top['hard_negative_rate']:.1%} | {c['common_code_lines']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - operator command
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--datasets", nargs="+", choices=sorted(LOADERS))
    parser.add_argument(
        "--student-holdout",
        type=Path,
        help="labelled holdout folder (docs/STUDENT_DATA_REQUEST_PACK.md, Part 2)",
    )
    args = parser.parse_args()
    # With only a holdout given, score just the holdout; otherwise every corpus.
    datasets = args.datasets or ([] if args.student_holdout else sorted(LOADERS))
    logging.basicConfig(level=logging.INFO)
    report = run_class_evaluation(tuple(datasets), student_holdout=args.student_holdout)
    print(render_markdown(report))
