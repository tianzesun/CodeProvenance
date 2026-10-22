"""Tests for the per-pair corpus fingerprint used to compare hosts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.backend.benchmark.corpus_fingerprint import (
    FINGERPRINT_LENGTH,
    corpus_fingerprints,
    pair_fingerprint,
)


def _pair(pair_id: str, label: int, code_a: str, code_b: str) -> SimpleNamespace:
    """Build the minimal pair shape the fingerprint reads."""
    return SimpleNamespace(pair_id=pair_id, label=label, code_a=code_a, code_b=code_b)


def test_fingerprint_is_stable_and_ignores_pair_order() -> None:
    """The same corpus must hash the same however the pairs are listed."""
    pairs = [_pair("b", 1, "x = 1", "x = 2"), _pair("a", 0, "y = 1", "y = 2")]
    assert pair_fingerprint(pairs) == pair_fingerprint(list(reversed(pairs)))
    assert len(pair_fingerprint(pairs)) == FINGERPRINT_LENGTH


def test_fingerprint_changes_with_a_label_or_a_code_body() -> None:
    """A flipped label or an edited submission is a different corpus."""
    base = [_pair("a", 1, "x = 1", "x = 2")]
    relabelled = [_pair("a", 0, "x = 1", "x = 2")]
    edited = [_pair("a", 1, "x = 1", "x = 3")]
    assert pair_fingerprint(base) != pair_fingerprint(relabelled)
    assert pair_fingerprint(base) != pair_fingerprint(edited)


def test_fingerprint_distinguishes_which_side_changed() -> None:
    """Swapping the two bodies is a different pair, not the same one."""
    forward = [_pair("a", 1, "x = 1", "x = 2")]
    swapped = [_pair("a", 1, "x = 2", "x = 1")]
    assert pair_fingerprint(forward) != pair_fingerprint(swapped)


def test_a_missing_corpus_fingerprints_as_none(tmp_path: Path) -> None:
    """A host without the corpus reports it rather than failing the probe."""
    fingerprints = corpus_fingerprints([tmp_path], ["does-not-exist"])
    assert fingerprints == {"does-not-exist": None}
