#!/usr/bin/env python
"""Materialise AIGCodeSet into the labelled-directory format the AI classifier
trainer expects (``data/ai/`` + ``data/human/``), preserving problem-level
grouping metadata so evaluations can avoid cross-problem leakage.

Input: ``data/datasets/aigcodeset/raw/{ai,human}.csv`` (from ``download.sh``).

Output:
    data/datasets/aigcodeset/data/
        ai/      one ``.py`` file per AI-generated sample
        human/   one ``.py`` file per human-written sample
        samples.jsonl   per-sample record with ``problem_id``, ``source``,
                        ``label``, ``language`` and provenance (LLM / status)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.backend.engines.ai.dataset_utils import (
    MIN_CODE_CHARS,
    dedupe_records,
    ensure_problem_ids,
    read_csv_rows,
    safe_stem,
)

logger = logging.getLogger(__name__)

DATASET_DIR = Path(__file__).resolve().parents[4] / "data" / "datasets" / "aigcodeset"
RAW_DIR = DATASET_DIR / "raw"
OUT_DIR = DATASET_DIR / "data"

# Kept for backward compatibility with importers of the old private names.
_safe_stem = safe_stem


def _dedupe_rows(records):
    """Drop duplicate (code) rows (kept for compatibility; see ``dedupe_records``)."""
    rows, _stats = dedupe_records(records)
    return iter(rows)


def _read_labelled_csv(path: Path, label: int, llm_default: str) -> Iterator[dict[str, Any]]:
    """Yield records from one raw CSV (the AI and human files were two copies of this loop)."""
    for row in read_csv_rows(path):
        code = (row.get("code") or "").strip()
        if len(code) < MIN_CODE_CHARS:
            continue
        yield {
            "code": code,
            "label": label,
            "problem_id": row.get("problem_id", ""),
            "llm": "HUMAN" if label == 0 else (row.get("LLM") or llm_default).upper(),
            "status": row.get("status_in_folder", ""),
            "submission_id": row.get("submission_id", ""),
            "language": "python",
        }


def _load_raw() -> list[dict]:
    """Load and merge the two raw CSV files into labelled records."""
    for name in ("ai.csv", "human.csv"):
        if not (RAW_DIR / name).exists():
            raise RuntimeError(
                f"Missing {RAW_DIR / name} - run data/datasets/aigcodeset/download.sh first"
            )
    records = list(_read_labelled_csv(RAW_DIR / "ai.csv", 1, "AI"))
    records += list(_read_labelled_csv(RAW_DIR / "human.csv", 0, "HUMAN"))
    records, stats = dedupe_records(records)
    logger.info(
        "Kept %d samples (%d exact duplicates removed, %d label conflicts dropped)",
        stats.kept,
        stats.duplicates,
        stats.conflicts,
    )
    ensure_problem_ids(records)
    return records


def materialise() -> dict:
    """Write labelled files and a per-sample metadata index."""
    records = _load_raw()
    if not records:
        raise RuntimeError(
            "No records found — run data/datasets/aigcodeset/download.sh first"
        )

    ai_dir = OUT_DIR / "ai"
    human_dir = OUT_DIR / "human"
    ai_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)

    meta_lines = []
    counts = {"ai": 0, "human": 0}
    for idx, row in enumerate(records):
        label_dir = ai_dir if row["label"] == 1 else human_dir
        counts["ai" if row["label"] == 1 else "human"] += 1
        filename = f"{safe_stem(row['problem_id'])}__{safe_stem(row['llm'])}__{idx:05d}.py"
        (label_dir / filename).write_text(row["code"] + "\n", encoding="utf-8")
        meta_lines.append(
            {
                "file": filename,
                "label": row["label"],
                "problem_id": row["problem_id"],
                "llm": row["llm"],
                "status": row["status"],
                "submission_id": row["submission_id"],
                "language": row["language"],
            }
        )

    (OUT_DIR / "samples.jsonl").write_text(
        "\n".join(json.dumps(line, ensure_ascii=True) for line in meta_lines) + "\n",
        encoding="utf-8",
    )
    return {"counts": counts, "total": len(records)}


def main() -> None:
    """Materialise the dataset and print a summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = materialise()
    counts = summary["counts"]
    logger.info(
        "Materialised %d samples (%d AI, %d human) into %s",
        summary["total"],
        counts["ai"],
        counts["human"],
        OUT_DIR,
    )


if __name__ == "__main__":
    main()
