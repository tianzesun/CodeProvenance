"""Shared helpers for building labelled AI/human code datasets.

Used by ``build_aigcodeset`` and ``build_student_dataset`` (they each carried
their own copy of these functions).
"""

from __future__ import annotations

import csv
import logging
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MIN_CODE_CHARS = 20

_SUFFIX_LANGUAGES = {
    ".py": "python",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".kt": "kotlin",
    ".swift": "swift",
}


_LANGUAGE_SUFFIXES = {}
for _suffix, _language in _SUFFIX_LANGUAGES.items():
    _LANGUAGE_SUFFIXES.setdefault(_language, _suffix)


def suffix_for_language(language: str) -> str:
    """File suffix for a language name (``.py`` when unknown)."""
    return _LANGUAGE_SUFFIXES.get(str(language).strip().lower(), ".py")


def safe_stem(value: Any, fallback: str = "sample", max_len: int = 60) -> str:
    """Sanitise an identifier for use in a file name.

    Truncated to ``max_len``: a problem statement used as an id could exceed the
    file-system name limit.
    """
    stem = re.sub(r"[^0-9A-Za-z_]+", "_", str(value)).strip("_")[:max_len].strip("_")
    return stem or fallback


def language_for_suffix(suffix: str) -> str:
    """Language name for a file suffix (case-insensitive), ``python`` when unknown."""
    return _SUFFIX_LANGUAGES.get(suffix.lower(), "python")


def raise_csv_field_limit() -> None:
    """Allow very large CSV cells.

    The default limit is 131,072 characters per field, so one long source file
    aborted the whole ingest with ``_csv.Error: field larger than field limit``.
    """
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def read_csv_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield CSV rows as dicts (UTF-8 with or without BOM, large fields allowed)."""
    raise_csv_field_limit()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


@dataclass
class DedupeStats:
    """What :func:`dedupe_records` removed."""

    kept: int = 0
    duplicates: int = 0  #: identical code with the same label (first kept)
    conflicts: int = 0  #: identical code under BOTH labels (all copies dropped)


def dedupe_records(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], DedupeStats]:
    """Drop duplicate code, and drop code that carries conflicting labels.

    Duplicates with the same label keep their first occurrence. The same source
    text labelled both AI and human is not a duplicate but a labelling problem:
    keeping whichever came first silently chose a label at random (and made the
    result depend on file order), so every copy is dropped and counted.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for row in records:
        code = row["code"]
        if code not in groups:
            order.append(code)
        groups[code].append(row)

    stats = DedupeStats()
    kept: list[dict[str, Any]] = []
    for code in order:
        rows = groups[code]
        if len({r["label"] for r in rows}) > 1:
            stats.conflicts += 1
            stats.duplicates += 0
            continue
        kept.append(rows[0])
        stats.duplicates += len(rows) - 1
    stats.kept = len(kept)
    if stats.conflicts:
        logger.warning(
            "Dropped %d code samples that appear under both AI and human labels", stats.conflicts
        )
    return kept, stats


def parse_label(value: Any) -> int | None:
    """Return 0 or 1, or None when the value is missing or not a valid label.

    ``int(value)`` accepted anything (``2``, ``-1``) and the callers then treated
    every non-1 as human.
    """
    try:
        label = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return label if label in (0, 1) else None


def ensure_problem_ids(records: list[dict[str, Any]]) -> int:
    """Give every record a ``problem_id``; return how many had none.

    A blank id put ALL such samples into one group, so a grouped holdout split
    either sent everything to train or everything to test. Each sample without an
    id becomes its own group, which makes the split effectively random: the
    caller is warned, because that overstates accuracy (see ``benchmark_classifier``).
    """
    missing = 0
    for index, row in enumerate(records):
        if not str(row.get("problem_id") or "").strip():
            row["problem_id"] = f"ungrouped_{index:06d}"
            missing += 1
    if missing:
        logger.warning(
            "%d of %d samples have no problem_id. They are treated as separate groups, so "
            "a grouped holdout is no longer leakage-free for them and accuracy may be "
            "overstated. Provide a problem_id column to get an honest evaluation.",
            missing,
            len(records),
        )
    return missing
