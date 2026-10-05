"""Starter-code removal for high-precision plagiarism detection.

What changed:
- Lines were hashed after FULL normalisation (identifiers -> ID_n, literals -> LIT_*) one line at a
  time. A starter line ``for i in range(n):`` then removed every student line of the shape
  ``for ID in ID(ID):`` and ``return result`` removed every ``return <anything>``: the student's own
  work was deleted and the "starter overlap" inflated (and the ranker discounts by that overlap).
  Matching now keeps names and literals (comments and whitespace are ignored): starter code is
  copied verbatim.
- Short generic lines are only starter code as part of a RUN of at least ``min_run_lines``
  consecutive meaningful lines that also run consecutively in a starter file, or when the line is
  long (at least ``min_line_tokens`` tokens). A student's own ``x = 0`` next to unrelated code is
  not removed because the starter happens to contain ``x = 0``.
- Lines are computed from tokens, so multi-line strings, brackets and docstrings are handled
  once, and comments / blank lines / lone ``}`` / ``else:`` do not count as lines at all.
- ``starter_overlap`` is the fraction of the MEANINGFUL lines removed (blank lines and comments
  used to dilute it: half the file blank meant half the overlap).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.backend.engines.mvp.normalization import CodeNormalizer

MAX_LINES = 5000


@dataclass(frozen=True)
class StarterRemovalResult:
    """Result of removing starter-code regions from a submission."""

    filtered_source: str
    removed_line_count: int  # meaningful lines removed
    total_line_count: int  # ALL lines of the submission
    starter_overlap: float  # removed / meaningful lines
    meaningful_line_count: int = 0
    removed_lines: tuple[int, ...] = field(default_factory=tuple)  # 1-based line numbers


class StarterCodeRemover:
    """Remove instructor-provided starter/template lines before comparison."""

    def __init__(
        self,
        starter_sources: Iterable[str],
        language: str = "python",
        *,
        min_run_lines: int = 3,
        min_line_tokens: int = 6,
    ) -> None:
        if min_run_lines < 1 or min_line_tokens < 1:
            raise ValueError("min_run_lines and min_line_tokens must be positive")
        self.language = language
        self.min_run_lines = min_run_lines
        self.min_line_tokens = min_line_tokens
        self.normalizer = CodeNormalizer()
        self._starter_sequences: list[list[str]] = []
        self._long_line_keys: set[str] = set()
        for source in starter_sources:
            keys = [key for _, key, tokens in self._meaningful_lines(source) if key]
            if keys:
                self._starter_sequences.append(keys[:MAX_LINES])
            self._long_line_keys.update(
                key for _, key, tokens in self._meaningful_lines(source) if len(tokens) >= min_line_tokens
            )

    @property
    def has_starter(self) -> bool:
        return bool(self._starter_sequences)

    def remove(self, source: str) -> StarterRemovalResult:
        """Remove the lines that are starter code."""
        text = source or ""
        lines = text.splitlines()
        if not lines:
            return StarterRemovalResult("", 0, 0, 0.0, 0, ())

        meaningful = self._meaningful_lines(text)[:MAX_LINES]
        marked: set[int] = set()
        if self._starter_sequences and meaningful:
            keys = [key for _, key, _ in meaningful]
            for starter_keys in self._starter_sequences:
                for block in SequenceMatcher(None, starter_keys, keys, autojunk=False).get_matching_blocks():
                    if block.size >= self.min_run_lines:
                        marked.update(range(block.b, block.b + block.size))
            for index, (_, key, tokens) in enumerate(meaningful):
                if len(tokens) >= self.min_line_tokens and key in self._long_line_keys:
                    marked.add(index)

        removed_numbers = {meaningful[i][0] for i in marked}
        kept = [line for number, line in enumerate(lines, 1) if number not in removed_numbers]
        return StarterRemovalResult(
            filtered_source="\n".join(kept),
            removed_line_count=len(removed_numbers),
            total_line_count=len(lines),
            starter_overlap=len(removed_numbers) / len(meaningful) if meaningful else 0.0,
            meaningful_line_count=len(meaningful),
            removed_lines=tuple(sorted(removed_numbers)),
        )

    def overlap(self, source: str) -> float:
        """Return the fraction of meaningful source lines that are starter code."""
        return self.remove(source).starter_overlap

    def _meaningful_lines(self, source: str) -> list[tuple[int, str, list[str]]]:
        """``[(line_number, key, tokens)]`` for lines with real content.

        The key keeps identifiers and literals as written (comments and layout ignored).
        """
        normalized = self.normalizer.normalize(source or "", self.language)
        by_line: dict[int, list[str]] = defaultdict(list)
        for original, number in zip(normalized.original_tokens, normalized.line_numbers):
            by_line[number].append(original)
        out = []
        for number in sorted(by_line):
            tokens = by_line[number]
            if self.normalizer.is_trivial_line(tokens):
                continue
            out.append((number, " ".join(tokens), tokens))
        return out
