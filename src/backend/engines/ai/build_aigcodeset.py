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
                        ``label`` and provenance (LLM / status)
"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DATASET_DIR = Path(__file__).resolve().parents[4] / "data" / "datasets" / "aigcodeset"
RAW_DIR = DATASET_DIR / "raw"
OUT_DIR = DATASET_DIR / "data"

MIN_CODE_CHARS = 20


def _safe_stem(value: str, fallback: str = "sample") -> str:
    """Sanitise an identifier for use in a file name."""
    stem = re.sub(r"[^0-9A-Za-z_]+", "_", str(value)).strip("_")
    return stem or fallback


def _dedupe_rows(records):
    """Drop duplicate (code) rows, keeping the first occurrence."""
    seen = set()
    for row in records:
        if row["code"] in seen:
            continue
        seen.add(row["code"])
        yield row


def _load_raw() -> list[dict]:
    """Load and merge the two raw CSV files into labelled records."""
    records = []
    with (RAW_DIR / "ai.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = (row.get("code") or "").strip()
            if len(code) < MIN_CODE_CHARS:
                continue
            records.append(
                {
                    "code": code,
                    "label": 1,
                    "problem_id": row.get("problem_id", ""),
                    "llm": (row.get("LLM") or "AI").upper(),
                    "status": row.get("status_in_folder", ""),
                    "submission_id": row.get("submission_id", ""),
                }
            )
    with (RAW_DIR / "human.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = (row.get("code") or "").strip()
            if len(code) < MIN_CODE_CHARS:
                continue
            records.append(
                {
                    "code": code,
                    "label": 0,
                    "problem_id": row.get("problem_id", ""),
                    "llm": "HUMAN",
                    "status": row.get("status_in_folder", ""),
                    "submission_id": row.get("submission_id", ""),
                }
            )
    return list(_dedupe_rows(records))


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
        filename = (
            f"{_safe_stem(row['problem_id'])}__{_safe_stem(row['llm'])}__{idx:05d}.py"
        )
        (label_dir / filename).write_text(row["code"] + "\n", encoding="utf-8")
        meta_lines.append(
            {
                "file": filename,
                "label": row["label"],
                "problem_id": row["problem_id"],
                "llm": row["llm"],
                "status": row["status"],
                "submission_id": row["submission_id"],
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
