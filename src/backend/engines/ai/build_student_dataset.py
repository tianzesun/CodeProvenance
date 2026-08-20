#!/usr/bin/env python
"""Materialise a labelled student-code holdout into the dataset format the AI
classifier trainer and benchmark expect.

This is the "bring your own labeled data" path that lets institutions validate
the AI detector on their own student submissions before the ML classifier is
enabled globally. It mirrors ``build_aigcodeset.py``: input becomes
``data/{ai,human}/`` files plus a per-sample ``samples.jsonl`` index carrying
the ``problem_id`` grouping needed for leakage-free grouped holdout evaluation.

Input (choose one):

1. **CSV/JSONL** with columns ``code``, ``label`` (1 = AI, 0 = human), and
   optional ``problem_id`` / ``llm`` / ``submission_id`` — any delimiter
   autodetected from the filename (``.csv`` or ``.jsonl``).
2. **Folder layout** with an ``ai/`` and ``human/`` directory; every source file
   becomes one sample. ``problem_id`` is derived from a ``problem.txt`` next to
   the file when present, else from the file stem.

Output: a new dataset directory (``--output``) laid out exactly like the
AIGCodeSet build so the benchmark consumes it with identical grouped-holdout
methodology:

    python -m src.backend.engines.ai.build_student_dataset \
        --input path/to/labelled --output data/datasets/student
    python -m src.backend.engines.ai.benchmark_classifier \
        --dataset-dir data/datasets/student
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MIN_CODE_CHARS = 20

# Supported source file extensions when ingesting a folder layout.
_SOURCE_SUFFIXES = {
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".kt",
    ".swift",
}


def _safe_stem(value: str, fallback: str = "sample") -> str:
    """Sanitise an identifier for use in a file name."""
    stem = re.sub(r"[^0-9A-Za-z_]+", "_", str(value)).strip("_")
    return stem or fallback


def _coerce_label(value: Any) -> Any:
    """Coerce a record field to int, or None when missing/unparsable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _records_from_csv(path: Path) -> dict[str, Any]:
    """Parse a labelled records file (CSV) into the schema list-of-dicts."""
    records = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = (row.get("code") or "").strip()
            if len(code) < MIN_CODE_CHARS:
                continue
            label = _coerce_label(row.get("label", 0))
            if label is None:
                logger.warning(
                    "Skipping row with non-integer label: %r", row.get("label")
                )
                continue
            records.append(
                {
                    "code": code,
                    "label": label,
                    "problem_id": row.get("problem_id", ""),
                    "llm": (row.get("llm") or "STUDENT").upper(),
                    "submission_id": row.get("submission_id", ""),
                }
            )
    return {"source": path.name, "records": records}


def _records_from_jsonl(path: Path) -> dict[str, Any]:
    """Parse a labelled records file (JSONL) into the schema list-of-dicts."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        code = (row.get("code") or "").strip()
        if len(code) < MIN_CODE_CHARS:
            continue
        label = _coerce_label(row.get("label", 0))
        if label is None:
            logger.warning("Skipping row with non-integer label: %r", row.get("label"))
            continue
        records.append(
            {
                "code": code,
                "label": label,
                "problem_id": row.get("problem_id", ""),
                "llm": (row.get("llm") or "STUDENT").upper(),
                "submission_id": row.get("submission_id", ""),
            }
        )
    return {"source": path.name, "records": records}


def _problem_id_for_file(path: Path) -> str:
    """Derive a problem id from a ``problem.txt`` sibling or the file stem."""
    problem = path.parent / "problem.txt"
    if problem.exists():
        value = problem.read_text(encoding="utf-8").strip()
        if value:
            return value
    return path.stem


def _records_from_folder(path: Path) -> dict[str, Any]:
    """Ingest an ``ai/`` + ``human/`` folder layout into labelled records."""
    records = []
    label_map = {"ai": 1, "human": 0}
    for label_dir, label in label_map.items():
        root = path / label_dir
        if not root.is_dir():
            continue
        for source in sorted(root.rglob("*")):
            if not source.is_file() or source.suffix not in _SOURCE_SUFFIXES:
                continue
            code = source.read_text(encoding="utf-8", errors="replace").strip()
            if len(code) < MIN_CODE_CHARS:
                continue
            relative = source.relative_to(path)
            records.append(
                {
                    "code": code,
                    "label": label,
                    "problem_id": _problem_id_for_file(source),
                    "llm": "STUDENT",
                    "submission_id": str(relative),
                }
            )
    return {"source": f"folder:{path}", "records": records}


def _load_records(input_path: Path) -> dict[str, Any]:
    """Load records from CSV, JSONL or a folder layout."""
    if input_path.is_dir():
        return _records_from_folder(input_path)
    if input_path.suffix.lower() == ".jsonl":
        return _records_from_jsonl(input_path)
    return _records_from_csv(input_path)


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate (code) rows, keeping the first occurrence."""
    seen = set()
    for row in records:
        if row["code"] in seen:
            continue
        seen.add(row["code"])
        yield row


def materialise(input_path: Path, out_dir: Path) -> dict[str, int]:
    """Write labelled files and a per-sample metadata index.

    Files go under ``<output>/data/{ai,human}/`` with ``samples.jsonl`` — the
    exact layout the classifier benchmark expects (see ``benchmark_classifier``).
    """
    if not input_path.exists():
        raise RuntimeError(f"Input path does not exist: {input_path}")

    loaded = _load_records(input_path)
    records = list(_dedupe_records(loaded["records"]))
    if not records:
        raise RuntimeError("No valid records found in the input.")

    data_dir = out_dir / "data"
    ai_dir = data_dir / "ai"
    human_dir = data_dir / "human"
    ai_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)

    meta_lines = []
    counts = {"ai": 0, "human": 0, "skipped": 0}
    seen_stems: dict = {}
    for idx, row in enumerate(records):
        label_dir = ai_dir if row["label"] == 1 else human_dir
        counts["ai" if row["label"] == 1 else "human"] += 1
        stem = _safe_stem(row["problem_id"] or f"sample_{idx}")
        seen_stems[stem] = seen_stems.get(stem, 0) + 1
        filename = f"{stem}__{seen_stems[stem]:03d}__{idx:05d}.py"
        (label_dir / filename).write_text(row["code"] + "\n", encoding="utf-8")
        meta_lines.append(
            {
                "file": filename,
                "label": row["label"],
                "problem_id": row["problem_id"],
                "llm": row["llm"],
                "status": "",
                "submission_id": row["submission_id"],
            }
        )

    (data_dir / "samples.jsonl").write_text(
        "\n".join(json.dumps(line, ensure_ascii=True) for line in meta_lines) + "\n",
        encoding="utf-8",
    )
    logger.info("Ingested from %s", loaded["source"])
    return counts


def main() -> None:
    """Ingest a labelled student-code holdout and print a summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Materialise a labelled student-code holdout for AI-detector validation."
    )
    parser.add_argument(
        "--input", required=True, help="CSV/JSONL records or ai/ human/ folder"
    )
    parser.add_argument("--output", required=True, help="output dataset directory")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = materialise(Path(args.input), out_dir)
    logger.info(
        "Materialised %d samples (%d AI, %d human) into %s",
        counts["ai"] + counts["human"],
        counts["ai"],
        counts["human"],
        out_dir,
    )


if __name__ == "__main__":
    main()
