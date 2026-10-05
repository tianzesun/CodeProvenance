#!/usr/bin/env python
"""Materialise a labelled student-code holdout into the dataset format the AI
classifier trainer and benchmark expect.

This is the "bring your own labeled data" path that lets institutions validate
the AI detector on their own student submissions before the ML classifier is
enabled globally. It mirrors ``build_aigcodeset.py``: input becomes
``data/{ai,human}/`` files plus a per-sample ``samples.jsonl`` index carrying
the ``problem_id`` grouping needed for leakage-free grouped holdout evaluation.

Input (choose one):

1. **CSV/JSONL** with columns ``code``, ``label`` (1 = AI, 0 = human; REQUIRED),
   and optional ``problem_id`` / ``llm`` / ``submission_id`` / ``language`` — any
   delimiter autodetected from the filename (``.csv`` or ``.jsonl``).
2. **Folder layout** with an ``ai/`` and ``human/`` directory; every source file
   becomes one sample. ``problem_id`` is derived from a ``problem.txt`` next to
   the file when present, else from the file stem. When the folder already
   carries a materialised ``samples.jsonl`` index (the output layout of this
   tool, or AIGCodeSet itself), its ``problem_id`` / ``llm`` / ``submission_id``
   are reused so re-ingesting a dataset round-trips exactly; the folder
   position stays the label authority.

Without a ``problem_id`` a sample cannot be grouped, and the benchmark's
"grouped holdout" degrades to a random split that overstates accuracy; the
ingest warns when that happens.

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
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.backend.engines.ai.dataset_utils import (
    MIN_CODE_CHARS,
    dedupe_records,
    ensure_problem_ids,
    language_for_suffix,
    parse_label,
    raise_csv_field_limit,
    read_csv_rows,
    safe_stem,
    suffix_for_language,
)

logger = logging.getLogger(__name__)

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

# Kept for backward compatibility with importers of the old private names.
_safe_stem = safe_stem


def _coerce_label(value: Any) -> Any:
    """Return 0/1, or None when missing/invalid (see ``parse_label``)."""
    return parse_label(value)


def _default_llm(label: int) -> str:
    """Generator name for a record that does not give one.

    A missing ``llm`` used to default to "STUDENT" for AI-labelled rows too.
    """
    return "UNKNOWN_AI" if label == 1 else "STUDENT"


def _record_from_row(row: dict[str, Any], origin: str, skipped: dict[str, int]) -> dict[str, Any] | None:
    code = (row.get("code") or "").strip()
    if len(code) < MIN_CODE_CHARS:
        skipped["too_short"] += 1
        return None
    # The label column is REQUIRED. ``row.get("label", 0)`` silently labelled every
    # row human when the column was missing or misnamed, producing a one-class
    # dataset that looked valid.
    label = parse_label(row.get("label"))
    if label is None:
        skipped["bad_label"] += 1
        logger.warning("%s: skipping row with missing/invalid label %r (must be 0 or 1)", origin, row.get("label"))
        return None
    return {
        "code": code,
        "label": label,
        "problem_id": str(row.get("problem_id") or ""),
        "llm": (row.get("llm") or _default_llm(label)).upper(),
        "submission_id": str(row.get("submission_id") or ""),
        "language": str(row.get("language") or "python").lower(),
    }


def _new_skip_counter() -> dict[str, int]:
    return {"too_short": 0, "bad_label": 0, "malformed": 0}


def _records_from_csv(path: Path) -> dict[str, Any]:
    """Parse a labelled records file (CSV) into the schema list-of-dicts."""
    skipped = _new_skip_counter()
    records = [r for row in read_csv_rows(path) if (r := _record_from_row(row, path.name, skipped))]
    return {"source": path.name, "records": records, "skipped": skipped}


def _iter_jsonl(path: Path, skipped: dict[str, int]) -> Iterator[dict[str, Any]]:
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # One bad line used to abort the whole ingest.
            skipped["malformed"] += 1
            logger.warning("%s:%d: skipping malformed JSON line", path.name, number)
            continue
        if isinstance(row, dict):
            yield row
        else:
            skipped["malformed"] += 1


def _records_from_jsonl(path: Path) -> dict[str, Any]:
    """Parse a labelled records file (JSONL) into the schema list-of-dicts."""
    skipped = _new_skip_counter()
    records = [
        r for row in _iter_jsonl(path, skipped) if (r := _record_from_row(row, path.name, skipped))
    ]
    return {"source": path.name, "records": records, "skipped": skipped}


def _problem_id_for_file(path: Path) -> str:
    """Derive a problem id from a ``problem.txt`` sibling or the file stem."""
    problem = path.parent / "problem.txt"
    if problem.exists():
        value = problem.read_text(encoding="utf-8").strip()
        if value:
            return value
    return path.stem


def _load_folder_index(path: Path) -> dict[str, dict[str, Any]]:
    """Map source file basename → metadata from a sibling ``samples.jsonl``.

    A folder that already carries a materialised index (the output layout of
    this tool, or AIGCodeSet itself) keeps its canonical ``problem_id`` /
    ``llm`` / ``submission_id`` this way instead of having them re-derived
    from file stems, so re-ingesting a dataset round-trips exactly. The
    ai/ vs human/ folder position remains the label authority.
    """
    index_path = path / "samples.jsonl"
    if not index_path.exists():
        return {}
    index: dict[str, dict[str, Any]] = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed index row in %s", index_path)
            continue
        name = row.get("file")
        if name:
            index[Path(str(name)).name] = row
    return index


def _records_from_folder(path: Path) -> dict[str, Any]:
    """Ingest an ``ai/`` + ``human/`` folder layout into labelled records."""
    skipped = _new_skip_counter()
    records = []
    label_map = {"ai": 1, "human": 0}
    index = _load_folder_index(path)
    for label_dir, label in label_map.items():
        root = path / label_dir
        if not root.is_dir():
            continue
        for source in sorted(root.rglob("*")):
            # Suffix compared case-insensitively (".PY" files were ignored).
            if not source.is_file() or source.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            code = source.read_text(encoding="utf-8", errors="replace").strip()
            if len(code) < MIN_CODE_CHARS:
                skipped["too_short"] += 1
                continue
            relative = source.relative_to(path)
            meta = index.get(source.name, {})
            records.append(
                {
                    "code": code,
                    "label": label,
                    "problem_id": str(meta.get("problem_id") or _problem_id_for_file(source)),
                    "llm": (meta.get("llm") or _default_llm(label)).upper(),
                    "submission_id": str(meta.get("submission_id") or relative),
                    "language": str(meta.get("language") or language_for_suffix(source.suffix)),
                }
            )
    return {"source": f"folder:{path}", "records": records, "skipped": skipped}


def _load_records(input_path: Path) -> dict[str, Any]:
    """Load records from CSV, JSONL or a folder layout."""
    if input_path.is_dir():
        return _records_from_folder(input_path)
    if input_path.suffix.lower() == ".jsonl":
        return _records_from_jsonl(input_path)
    return _records_from_csv(input_path)


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate code, and code with conflicting labels (see ``dedupe_records``)."""
    return dedupe_records(records)[0]


def materialise(input_path: Path, out_dir: Path) -> dict[str, int]:
    """Write labelled files and a per-sample metadata index.

    Files go under ``<output>/data/{ai,human}/`` with ``samples.jsonl`` — the
    exact layout the classifier benchmark expects (see ``benchmark_classifier``).
    """
    raise_csv_field_limit()
    if not input_path.exists():
        raise RuntimeError(f"Input path does not exist: {input_path}")

    loaded = _load_records(input_path)
    records, stats = dedupe_records(loaded["records"])
    if not records:
        raise RuntimeError("No valid records found in the input.")

    labels = {r["label"] for r in records}
    if labels != {0, 1}:
        raise RuntimeError(
            "The input contains only %s samples; both AI (1) and human (0) are needed."
            % ("AI" if labels == {1} else "human")
        )
    ungrouped = ensure_problem_ids(records)

    data_dir = out_dir / "data"
    ai_dir = data_dir / "ai"
    human_dir = data_dir / "human"
    ai_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)

    meta_lines = []
    counts = {"ai": 0, "human": 0, "skipped": sum(loaded["skipped"].values())}
    seen_stems: dict = {}
    for idx, row in enumerate(records):
        label_dir = ai_dir if row["label"] == 1 else human_dir
        counts["ai" if row["label"] == 1 else "human"] += 1
        stem = safe_stem(row["problem_id"] or f"sample_{idx}")
        seen_stems[stem] = seen_stems.get(stem, 0) + 1
        # The extension follows the sample's language (everything used to be ``.py``).
        filename = f"{stem}__{seen_stems[stem]:03d}__{idx:05d}{suffix_for_language(row['language'])}"
        (label_dir / filename).write_text(row["code"] + "\n", encoding="utf-8")
        meta_lines.append(
            {
                "file": filename,
                "label": row["label"],
                "problem_id": row["problem_id"],
                "llm": row["llm"],
                "status": "",
                "submission_id": row["submission_id"],
                "language": row["language"],
            }
        )

    (data_dir / "samples.jsonl").write_text(
        "\n".join(json.dumps(line, ensure_ascii=True) for line in meta_lines) + "\n",
        encoding="utf-8",
    )
    counts.update(duplicates=stats.duplicates, conflicts=stats.conflicts, ungrouped=ungrouped)
    logger.info(
        "Ingested from %s (skipped %s; %d duplicates removed, %d label conflicts dropped)",
        loaded["source"],
        loaded["skipped"],
        stats.duplicates,
        stats.conflicts,
    )
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
