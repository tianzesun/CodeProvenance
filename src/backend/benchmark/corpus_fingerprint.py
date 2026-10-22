"""Identify a labelled corpus by its pairs, not by its directory.

Two hosts can hold the same file count and still disagree on labels, on which
files are paired, or on a single edited submission. A per-pair hash makes that
visible before a measurement is compared across machines.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

#: Characters kept from the hex digest; long enough to collide never in practice.
FINGERPRINT_LENGTH = 16

#: Corpora the fusion work is judged on.
PRODUCT_CORPORA: tuple[str, ...] = (
    "IR-Plag-Dataset",
    "conplag",
    "kaggle_student_code",
)


def pair_fingerprint(pairs: Iterable[Any]) -> str:
    """Hash the labelled pairs, in pair-id order, by label and both code bodies.

    Args:
        pairs: Objects with ``pair_id``, ``label``, ``code_a`` and ``code_b``.

    Returns:
        A short hex digest, stable across machines for identical corpora.
    """
    digest = hashlib.sha256()
    for pair in sorted(pairs, key=lambda item: item.pair_id):
        digest.update(
            f"{pair.pair_id}|{pair.label}|"
            f"{hashlib.sha256(pair.code_a.encode()).hexdigest()[:16]}|"
            f"{hashlib.sha256(pair.code_b.encode()).hexdigest()[:16]}\n".encode()
        )
    return digest.hexdigest()[:FINGERPRINT_LENGTH]


def corpus_fingerprints(
    dataset_roots: Iterable[Path | str],
    names: Iterable[str] = PRODUCT_CORPORA,
    output_dir: Path | str | None = None,
) -> dict[str, str | None]:
    """Fingerprint each corpus, returning ``None`` for one that cannot be loaded.

    Args:
        dataset_roots: Directories searched for a corpus of that name.
        names: Corpus names to fingerprint.
        output_dir: Scratch directory for the loader; defaults to a temp dir.

    Returns:
        Corpus name to fingerprint.
    """
    import tempfile

    from src.backend.benchmark.runners.learned_fusion_training_runner import (
        LearnedFusionTrainingRunner,
    )

    roots = [Path(root) for root in dataset_roots]
    result: dict[str, str | None] = {}
    with tempfile.TemporaryDirectory(prefix="corpus-fingerprint-") as fallback:
        runner = LearnedFusionTrainingRunner(
            output_dir=Path(output_dir) if output_dir is not None else Path(fallback),
            dataset_roots=roots,
        )
        for name in names:
            try:
                pairs = runner.load_pairs([name])
            except (FileNotFoundError, ValueError):
                result[name] = None
                continue
            result[name] = pair_fingerprint(pairs)
    return result
