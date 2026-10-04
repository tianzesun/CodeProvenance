#!/usr/bin/env python
"""Evaluate a candidate AI-detection signal against every negative corpus.

This exists because of a measured failure. A "docstring uniformity" signal
(LLM output documents every function; human code is selective) looked
convincing on a hand-written ChatGPT snippet — 6/6 documented vs 0/2 — and was
almost shipped as a fix for modern-AI detection. Measured on the real corpora
it came out at **AUC 0.49 against AIGCodeSet human and 0.49 against Kaggle
students**: human code in those corpora is documented *more* often than AI code.
A single anecdotal snippet is not evidence, and shipping it would have flagged
innocent students.

The design rule this tool enforces is therefore:

    A candidate is only interesting if it separates AI from BOTH negatives.

``ai`` alone is never enough. The AIGCodeSet human set is the paired control;
the Kaggle student set is the product's real false-positive risk, and a signal
that only clears the first bar is worthless.

Usage:
    python scripts/eval_ai_signals.py
    python scripts/eval_ai_signals.py --limit 400 --list
"""

from __future__ import annotations

import argparse
import ast
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DATASETS = REPO_ROOT / "data" / "datasets"


def iter_samples(directory: Path) -> list[tuple[str, str]]:
    """Return ``(name, code)`` for every readable source file under *directory*."""
    if not directory.is_dir():
        return []
    samples: list[tuple[str, str]] = []
    for path in sorted(directory.rglob("*")):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES or not path.is_file():
            continue
        try:
            code = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if code.strip():
            samples.append((str(path.relative_to(directory)), code))
    return samples


def subsample(
    samples: list[tuple[str, str]], limit: int, seed: int
) -> list[tuple[str, str]]:
    """Deterministically subsample so runs stay comparable across invocations."""
    if limit <= 0 or len(samples) <= limit:
        return samples
    rng = random.Random(seed)
    return [samples[i] for i in sorted(rng.sample(range(len(samples)), limit))]


def _roc_auc(positives: list[float], negatives: list[float]) -> float:
    """ROC-AUC via the rank (Mann-Whitney U) identity, ties averaged."""
    if not positives or not negatives:
        return float("nan")
    combined = sorted(
        [(v, 1) for v in positives] + [(v, 0) for v in negatives],
        key=lambda item: item[0],
    )
    ranks = [0.0] * len(combined)
    index = 0
    while index < len(combined):
        end = index
        while end + 1 < len(combined) and combined[end + 1][0] == combined[index][0]:
            end += 1
        average = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            ranks[position] = average
        index = end + 1
    rank_sum = sum(r for r, (_, label) in zip(ranks, combined) if label == 1)
    n_pos, n_neg = len(positives), len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _rate_at(scores: list[float], threshold: float) -> float:
    """Fraction of *scores* at or above *threshold*."""
    if not scores:
        return float("nan")
    return sum(1 for s in scores if s >= threshold) / len(scores)


# ---------------------------------------------------------------------------
# Candidate signals
# ---------------------------------------------------------------------------

SUPPORTED_SUFFIXES = {".py", ".java", ".c", ".cpp", ".h", ".js", ".ts", ".go", ".rs"}


def _python_defs(code: str) -> list[ast.AST]:
    """Return every function def in Python *code*, or ``[]`` if it does not parse."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return []
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def function_count(code: str) -> float | None:
    """How many function defs the file has; ``None`` for none/unparseable.

    Not a detector. Reported because a signal like docstring uniformity is
    unmeasurable on a corpus whose files contain no functions at all.
    """
    defs = _python_defs(code)
    return float(len(defs)) if defs else None


def _uniformity(defs: list[ast.AST], minimum: int) -> float | None:
    """Fraction of *defs* carrying a docstring, or ``None`` below *minimum*.

    ``None`` (rather than ``0.0``) keeps "too few functions to judge" out of the
    scored population, so a coverage-limited corpus cannot masquerade as a
    signal that simply found nothing.
    """
    if len(defs) < minimum:
        return None
    return sum(1 for d in defs if ast.get_docstring(d)) / len(defs)


def docstring_uniformity(code: str) -> float | None:
    """Fraction of function defs carrying a docstring (needs >= 2 functions).

    Measured: AUC 0.49 against AIGCodeSet human, 0.49 against Kaggle students.
    Human code in these corpora is documented *more* often than AI code, and
    AIGCodeSet files have a median of zero functions, so the signal is both
    inverted and mostly unmeasurable. Rejected - kept so the negative result
    stays reproducible rather than being re-tried from scratch.
    """
    return _uniformity(_python_defs(code), 2)


def short_docstring_uniformity(code: str) -> float | None:
    """Uniformity restricted to terse one-line docstrings.

    The idea was that assistant output favours short summaries while
    documentation-heavy human code uses long NumPy-style blocks. Measured:
    AUC 0.50 / 0.48. Also rejected.
    """
    defs = _python_defs(code)
    if len(defs) < 2:
        return None
    hits = 0
    for node in defs:
        doc = ast.get_docstring(node)
        if not doc:
            continue
        body = doc.strip().splitlines()
        if len(body) == 1 and len(body[0]) <= 120:
            hits += 1
    return hits / len(defs)


def uniform_documentation(code: str) -> float | None:
    """Binary "documents essentially every function" flag.

    A gate on top of :func:`docstring_uniformity` at the 0.9 bar. Measured:
    AUC 0.50 / 0.51 - no better than the ungated version, so the gate buys
    precision nothing.
    """
    value = _uniformity(_python_defs(code), 2)
    if value is None:
        return None
    return 1.0 if value >= 0.9 else 0.0


CANDIDATES = {
    "function_count (diagnostic)": function_count,
    "docstring_uniformity": docstring_uniformity,
    "short_docstring_uniformity": short_docstring_uniformity,
    "uniform_documentation": uniform_documentation,
}

#: AUC a candidate must clear against *both* negatives to be worth shipping.
MIN_USEFUL_AUC = 0.55


def _describe(name: str, fn, ai, human, students) -> dict[str, object]:
    """Score one candidate on all three corpora and summarise it."""
    ai_scores = [s for s in (fn(code) for _, code in ai) if s is not None]
    human_scores = [s for s in (fn(code) for _, code in human) if s is not None]
    student_scores = [s for s in (fn(code) for _, code in students) if s is not None]

    auc_human = _roc_auc(ai_scores, human_scores)
    auc_students = _roc_auc(ai_scores, student_scores)
    return {
        "name": name,
        "coverage_ai": (len(ai_scores), len(ai)),
        "coverage_students": (len(student_scores), len(students)),
        "auc_human": auc_human,
        "auc_students": auc_students,
        "ai_scores": ai_scores,
        "human_scores": human_scores,
        "student_scores": student_scores,
        "useful": min(auc_human, auc_students) >= MIN_USEFUL_AUC,
    }


def _print_report(result: dict[str, object]) -> None:
    """Print one candidate's row, flagging coverage gaps and usefulness."""
    scored_ai, total_ai = result["coverage_ai"]  # type: ignore[misc]
    scored_students, total_students = result["coverage_students"]  # type: ignore[misc]
    print(f"=== {result['name']} ===")
    print(
        f"  coverage: ai {scored_ai}/{total_ai}   "
        f"students {scored_students}/{total_students}"
    )
    ai_scores = result["ai_scores"]  # type: ignore[assignment]
    human_scores = result["human_scores"]  # type: ignore[assignment]
    student_scores = result["student_scores"]  # type: ignore[assignment]
    if not ai_scores or not human_scores:
        print("  insufficient data to score\n")
        return

    print(
        f"  AUC vs AIGCodeSet human : {result['auc_human']:.4f}\n"
        f"  AUC vs Kaggle students  : {result['auc_students']:.4f}"
    )
    for threshold in (0.5, 0.9):
        print(
            f"    >= {threshold:.1f}:  ai={_rate_at(ai_scores, threshold) * 100:5.1f}%"
            f"  human={_rate_at(human_scores, threshold) * 100:5.1f}%"
            f"  students(FP)={_rate_at(student_scores, threshold) * 100:5.1f}%"
        )
    verdict = "USEFUL" if result["useful"] else "reject"
    print(f"  verdict: {verdict} (needs AUC >= {MIN_USEFUL_AUC} vs BOTH)\n")


def main() -> int:
    """Score every registered candidate on all three corpora."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", default=str(DEFAULT_DATASETS))
    parser.add_argument("--limit", type=int, default=400, help="Max samples per class.")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--list", action="store_true", help="List candidate names and exit."
    )
    args = parser.parse_args()

    if args.list:
        for name in CANDIDATES:
            print(name)
        return 0

    root = Path(args.datasets)
    ai = subsample(
        iter_samples(root / "aigcodeset" / "data" / "ai"), args.limit, args.seed
    )
    human = subsample(
        iter_samples(root / "aigcodeset" / "data" / "human"), args.limit, args.seed
    )
    students = iter_samples(root / "kaggle_student_code")
    print(f"ai={len(ai)} human={len(human)} students={len(students)}\n")

    for name, fn in CANDIDATES.items():
        _print_report(_describe(name, fn, ai, human, students))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
