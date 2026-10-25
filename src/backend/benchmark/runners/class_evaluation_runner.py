"""Class-level evaluation: accuracy measured the way a professor sees it.

The engine evaluation harness scores labelled pairs one at a time, so it never
exercises what a Plagiarism Checker job does with a whole class (removing code
most of the class shares, holding tiny files at review), and its negatives are
often hand-picked hard cases rather than a sample of the class. Its false
positive rate is therefore not the share of a class a professor would see
flagged.

This runner scores *every* pair in each class through the production path
(``BatchDetectionService.compare_all_pairs`` with class inference and the small
file cap) and reports, per threshold:

* ``flag_rate``: share of all pairs in the class that would be flagged,
* ``recall``: labelled copies caught,
* ``hard_negative_rate``: labelled innocent pairs flagged (hard cases),

plus AUC over the labelled pairs and how much class-shared code was removed.

Datasets: ``kaggle_student_code`` (one class, labelled pairs in a CSV) and
``IR-Plag-Dataset`` (each case is a class; the original against each other
file is labelled). Output goes to ``reports/class_evaluation/``.
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

logger = logging.getLogger(__name__)

THRESHOLDS = (0.5, 0.75, 0.85, 0.95)
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


LOADERS = {"kaggle_student_code": load_kaggle, "IR-Plag-Dataset": load_irplag}


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


def score_class(
    class_set: ClassSet, max_workers: int | None = None
) -> tuple[dict, int]:
    """Score every pair in a class the way a Plagiarism Checker job does."""
    from src.backend.application.services.batch_detection_service import (
        MIN_EVIDENCE_TOKENS,
        BatchDetectionService,
    )

    service = BatchDetectionService(
        infer_common_code=True, min_evidence_tokens=MIN_EVIDENCE_TOKENS
    )
    results = service.compare_all_pairs(class_set.files, max_workers=max_workers)
    common = getattr(service.starter_remover, "inferred_common_lines", 0) or 0
    return {_pair(r.file_a, r.file_b): float(r.score) for r in results}, common


def run_class_evaluation(
    datasets: tuple[str, ...] = ("kaggle_student_code", "IR-Plag-Dataset"),
    output_dir: Path = Path("reports/class_evaluation"),
    root: Path = DATASET_ROOT,
    max_workers: int | None = None,
) -> dict:
    """Run the evaluation and write JSON + Markdown reports; returns the report."""
    started = time.time()
    classes: list[ClassResult] = []
    for name in datasets:
        for class_set in LOADERS[name](root):
            scores, common = score_class(class_set, max_workers=max_workers)
            classes.append(evaluate_class(class_set, scores, common))
            logger.info("Scored %s (%d pairs)", class_set.name, len(scores))
    report = {
        "run_id": f"CLASS_EVAL_{datetime.now():%Y%m%d_%H%M%S}",
        "runtime_seconds": round(time.time() - started, 1),
        "classes": [asdict(c) for c in classes],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{report['run_id']}.json").write_text(json.dumps(report, indent=2))
    (output_dir / f"{report['run_id']}.md").write_text(render_markdown(report))
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Class-level evaluation",
        "",
        f"- Run: `{report['run_id']}` ({report['runtime_seconds']}s)",
        "- Every pair in each class scored through the production path.",
        "- Flag rate: share of all pairs flagged. Recall: labelled copies caught. "
        "Hard negatives: labelled innocent pairs flagged (often hand-picked look-alikes).",
        "",
        "| Class | Subs | Pairs | AUC | Flag rate @0.75 | Recall @0.75 | Hard neg. @0.75 "
        "| Flag rate @0.95 | Recall @0.95 | Shared lines removed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for c in report["classes"]:
        mid, high = c["at_threshold"]["0.75"], c["at_threshold"]["0.95"]
        auc = "n/a" if c["auc"] is None else f"{c['auc']:.4f}"
        lines.append(
            f"| {c['name']} | {c['submissions']} | {c['pairs']} | {auc} "
            f"| {mid['flag_rate']:.1%} | {mid['recall']:.1%} | {mid['hard_negative_rate']:.1%} "
            f"| {high['flag_rate']:.1%} | {high['recall']:.1%} | {c['common_code_lines']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - operator command
    logging.basicConfig(level=logging.INFO)
    print(render_markdown(run_class_evaluation()))
