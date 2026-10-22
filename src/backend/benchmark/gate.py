"""Ship/no-ship gate for a retrained fusion artifact.

A retrain is only worth shipping when it does not trade one corpus for another.
The bar is the currently shipped artifact measured on the same three corpora with
the same harness (2026-10-22, see ``docs/EXTERNAL_TOOL_COMPARISON.md``)::

    IR-Plag-Dataset     0.6184
    conplag             0.8134
    kaggle_student_code 0.8833

Pooled/combined AUC is deliberately not a criterion: it is flattered by the
corpora being separable from each other, and an earlier candidate improved the
pooled number while losing about 0.03 on two of the three corpora.

This module only decides pass/fail from a report; it never fits or edits an
artifact. Promoting a passing candidate is a separate, explicit copy step.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Per-dataset AUC of the currently shipped artifact on the same harness.
SHIPPED_BASELINE: dict[str, float] = {
    "IR-Plag-Dataset": 0.6184,
    "conplag": 0.8134,
    "kaggle_student_code": 0.8833,
}

#: Keys a training report may use for its per-dataset out-of-fold AUC.
_TRAINING_KEYS = ("per_dataset_auc", "logo_per_dataset")


@dataclass(frozen=True)
class GateRow:
    """One corpus in the gate table."""

    dataset: str
    baseline: float
    candidate: float | None

    @property
    def delta(self) -> float | None:
        """Candidate minus baseline, or None when the candidate is missing."""
        if self.candidate is None:
            return None
        return round(self.candidate, 4) - self.baseline

    def passed(self, tolerance: float = 0.0) -> bool:
        """True when this corpus is at least level with the shipped artifact.

        Compared at four decimal places, the precision the bar is quoted at, so
        a candidate equal to the shipped artifact does not fail on float noise
        from a re-run.
        """
        if self.candidate is None:
            return False
        return round(self.candidate, 4) + tolerance >= self.baseline


@dataclass(frozen=True)
class GateResult:
    """Verdict for one candidate across every corpus in the baseline."""

    rows: list[GateRow] = field(default_factory=list)
    tolerance: float = 0.0

    @property
    def missing(self) -> list[str]:
        """Corpora the candidate report does not cover."""
        return [row.dataset for row in self.rows if row.candidate is None]

    @property
    def failed(self) -> list[str]:
        """Corpora that are measurably below the shipped artifact."""
        return [
            row.dataset
            for row in self.rows
            if row.candidate is not None and not row.passed(self.tolerance)
        ]

    @property
    def passed(self) -> bool:
        """True only when every corpus was measured and none regressed."""
        return not self.missing and not self.failed

    def to_dict(self) -> dict[str, Any]:
        """Return the verdict as JSON-safe data."""
        return {
            "passed": self.passed,
            "tolerance": self.tolerance,
            "criteria": "per-dataset AUC only; pooled AUC is not a criterion",
            "rows": [
                {
                    "dataset": row.dataset,
                    "baseline": round(row.baseline, 4),
                    "candidate": (
                        None if row.candidate is None else round(row.candidate, 4)
                    ),
                    "delta": None if row.delta is None else round(row.delta, 4),
                    "passed": row.passed(self.tolerance),
                    "missing": row.candidate is None,
                }
                for row in self.rows
            ],
        }

    def format_table(self) -> str:
        """Render the verdict as a fixed-width table plus a one-line summary."""
        lines = [
            f"{'dataset':22} {'shipped':>8} {'candidate':>10} {'delta':>8}  result",
            "-" * 62,
        ]
        for row in self.rows:
            if row.candidate is None:
                lines.append(
                    f"{row.dataset:22} {row.baseline:>8.4f} {'-':>10} {'-':>8}  MISSING"
                )
                continue
            result = "PASS" if row.passed(self.tolerance) else "FAIL"
            lines.append(
                f"{row.dataset:22} {row.baseline:>8.4f} {row.candidate:>10.4f} "
                f"{row.delta:>+8.4f}  {result}"
            )
        if self.passed:
            verdict = (
                "GATE: PASS - every corpus is at least level with the shipped artifact"
            )
        else:
            reasons = []
            if self.failed:
                reasons.append(
                    f"{len(self.failed)} of {len(self.rows)} corpora below the "
                    f"shipped artifact ({', '.join(self.failed)})"
                )
            if self.missing:
                reasons.append(
                    f"no measurement for {', '.join(self.missing)} "
                    "(cannot prove it did not regress)"
                )
            verdict = "GATE: FAIL - " + "; ".join(reasons)
        lines.extend(
            ["", verdict, "Pooled AUC is not a criterion; compare per corpus."]
        )
        return "\n".join(lines)


def evaluate_gate(
    candidate: Mapping[str, float],
    baselines: Mapping[str, float] | None = None,
    tolerance: float = 0.0,
) -> GateResult:
    """Compare per-dataset AUCs against the shipped artifact.

    Args:
        candidate: Dataset name to measured AUC for the candidate.
        baselines: Bar to clear; defaults to :data:`SHIPPED_BASELINE`.
        tolerance: Allowed shortfall per corpus, for a deliberately accepted
            trade-off. ``0`` requires every corpus to be at least level.

    Returns:
        The verdict, including any corpus the candidate did not measure.
    """
    reference = dict(baselines or SHIPPED_BASELINE)
    rows = []
    for name, bar in reference.items():
        value = candidate.get(name)
        rows.append(
            GateRow(
                dataset=name,
                baseline=float(bar),
                candidate=None if value is None else float(value),
            )
        )
    return GateResult(rows=rows, tolerance=float(tolerance))


def load_report_scores(path: Path, scorer: str = "fused") -> dict[str, float]:
    """Read per-dataset AUCs from a training report or an engine-eval report.

    Two shapes exist in ``reports/``: ``fusion-train-learned`` writes one file
    with ``per_dataset_auc`` for every corpus (older runs: ``logo_per_dataset``),
    while ``engine-eval`` writes one file per corpus with a ``scorers`` list.

    Args:
        path: Report JSON file.
        scorer: Scorer name to read from an engine-eval report.

    Returns:
        Dataset name to AUC. Empty when the file carries neither shape.

    Raises:
        TypeError: If the file is not a JSON object.
        FileNotFoundError: If the path does not exist.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} is not a report object")

    for key in _TRAINING_KEYS:
        values = payload.get(key)
        if isinstance(values, dict) and values:
            return {str(name): float(auc) for name, auc in values.items()}

    dataset_name = payload.get("dataset_name")
    scorers = payload.get("scorers")
    if isinstance(dataset_name, str) and isinstance(scorers, list):
        for entry in scorers:
            if not isinstance(entry, dict) or entry.get("name") != scorer:
                continue
            if not entry.get("available", True):
                return {}
            auc = entry.get("auc_roc")
            if isinstance(auc, (int, float)):
                return {dataset_name: float(auc)}
    return {}


def collect_scores(
    paths: Iterable[Path], scorer: str = "fused"
) -> tuple[dict[str, float], list[Path]]:
    """Merge scores from report files and directories.

    A directory is searched recursively; when it holds several runs of the same
    corpus (``engine-eval`` timestamps each file), the newest file wins. That
    keeps a re-run of one corpus from being masked by an older file.

    Args:
        paths: Report files or directories.
        scorer: Scorer name to read from engine-eval reports.

    Returns:
        ``(scores, used_files)`` — dataset to AUC, and the files that supplied
        them, so the caller can show which run a verdict is based on.
    """
    newest: dict[str, tuple[tuple[float, str], Path, float]] = {}
    for path in paths:
        path = Path(path)
        candidates = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for candidate_path in candidates:
            if not candidate_path.is_file():
                continue
            try:
                scores = load_report_scores(candidate_path, scorer=scorer)
                # Reports are named with the run timestamp, so the name breaks
                # mtime ties. Without it, copying a directory (which rewrites
                # mtimes) could make an older run look newest.
                key = (candidate_path.stat().st_mtime, candidate_path.name)
            except (OSError, ValueError, TypeError):
                continue
            for dataset, auc in scores.items():
                previous = newest.get(dataset)
                if previous is None or key > previous[0]:
                    newest[dataset] = (key, candidate_path, auc)
    used = sorted({path for _, path, _ in newest.values()})
    return {dataset: value[2] for dataset, value in newest.items()}, used
