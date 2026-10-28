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

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.backend.engines.mvp.normalization import CodeNormalizer

MAX_LINES = 5000
#: A line in at least this share of a cohort's submissions is shared code. Set
#: high so a copying group of under half the class is never suppressed.
COMMON_CODE_MIN_SHARE = 0.5
#: Fewer submissions than this cannot separate shared code from copying.
COMMON_CODE_MIN_SUBMISSIONS = 4
#: Distinct common-line sequences kept; each one is matched against every file.
COMMON_CODE_MAX_SEQUENCES = 20


@dataclass(frozen=True)
class StarterRemovalResult:
    """Result of removing starter-code regions from a submission."""

    filtered_source: str
    removed_line_count: int  # meaningful lines removed
    total_line_count: int  # ALL lines of the submission
    starter_overlap: float  # removed / meaningful lines
    meaningful_line_count: int = 0
    removed_lines: tuple[int, ...] = field(
        default_factory=tuple
    )  # 1-based line numbers


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
        #: Distinct lines inferred as shared by ``from_cohort`` (0 = none).
        self.inferred_common_lines = 0
        for source in starter_sources:
            keys = [key for _, key, tokens in self._meaningful_lines(source) if key]
            if keys:
                self._starter_sequences.append(keys[:MAX_LINES])
            self._long_line_keys.update(
                key
                for _, key, tokens in self._meaningful_lines(source)
                if len(tokens) >= min_line_tokens
            )

    @classmethod
    def from_cohort(
        cls,
        submissions: Iterable[str],
        starter_sources: Iterable[str] = (),
        language: str = "python",
        *,
        min_share: float = COMMON_CODE_MIN_SHARE,
        min_submissions: int = COMMON_CODE_MIN_SUBMISSIONS,
    ) -> StarterCodeRemover:
        """Remover for the given starter code plus code most of the class shares.

        Without uploaded starter code, a handout every student builds on makes
        every pair look similar. As MOSS does, a line found in at least
        ``min_share`` of the submissions is treated as shared code; it is then
        removed under the usual rules (a run of ``min_run_lines`` such lines,
        or one long line), so a common short line on its own stays.

        A cohort smaller than ``min_submissions`` is too small to tell shared
        code from copying, so only ``starter_sources`` are used.
        """
        remover = cls(starter_sources, language)
        sources = [source or "" for source in submissions]
        if len(sources) < min_submissions:
            return remover
        per_source = [
            [key for _, key, _ in remover._meaningful_lines(source)][:MAX_LINES]
            for source in sources
        ]
        frequency: Counter[str] = Counter()
        for keys in per_source:
            frequency.update(set(keys))
        needed = max(min_submissions, math.ceil(min_share * len(sources)))
        common = {key for key, count in frequency.items() if count >= needed}
        if not common:
            return remover

        # Each submission's common lines, in its own order, act as one starter
        # file: a handout block stays contiguous, a student's own code breaks it.
        sequences = {tuple(key for key in keys if key in common) for keys in per_source}
        for sequence in sorted(sequences, key=len, reverse=True)[
            :COMMON_CODE_MAX_SEQUENCES
        ]:
            if len(sequence) >= remover.min_run_lines:
                remover._starter_sequences.append(list(sequence))
        remover._long_line_keys.update(
            key for key in common if len(key.split()) >= remover.min_line_tokens
        )
        remover.inferred_common_lines = len(common)
        return remover

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
                for block in SequenceMatcher(
                    None, starter_keys, keys, autojunk=False
                ).get_matching_blocks():
                    if block.size >= self.min_run_lines:
                        marked.update(range(block.b, block.b + block.size))
            for index, (_, key, tokens) in enumerate(meaningful):
                if len(tokens) >= self.min_line_tokens and key in self._long_line_keys:
                    marked.add(index)

        removed_numbers = {meaningful[i][0] for i in marked}
        # Docstrings and comments are not meaningful lines, so they were never
        # matched and a starter docstring stayed in every submission. Drop what
        # sits between two consecutive removed lines; counts stay meaningful-only.
        dropped = set(removed_numbers)
        for i in marked:
            if i + 1 in marked:
                dropped.update(range(meaningful[i][0] + 1, meaningful[i + 1][0]))
        kept = [
            line
            for number, line in enumerate(lines, 1)
            if number not in dropped
        ]
        return StarterRemovalResult(
            filtered_source="\n".join(kept),
            removed_line_count=len(removed_numbers),
            total_line_count=len(lines),
            starter_overlap=(
                len(removed_numbers) / len(meaningful) if meaningful else 0.0
            ),
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
        for original, number in zip(
            normalized.original_tokens, normalized.line_numbers
        ):
            by_line[number].append(original)
        out = []
        for number in sorted(by_line):
            tokens = by_line[number]
            if self.normalizer.is_trivial_line(tokens):
                continue
            out.append((number, " ".join(tokens), tokens))
        return out
