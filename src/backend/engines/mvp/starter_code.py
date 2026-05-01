"""Starter-code removal for high-precision plagiarism detection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List, Set

from src.backend.engines.mvp.normalization import CodeNormalizer


@dataclass(frozen=True)
class StarterRemovalResult:
    """Result of removing starter-code regions from a submission."""

    filtered_source: str
    removed_line_count: int
    total_line_count: int
    starter_overlap: float


class StarterCodeRemover:
    """Remove instructor-provided starter/template lines before comparison."""

    def __init__(
        self, starter_sources: Iterable[str], language: str = "python"
    ) -> None:
        self.language = language
        self.normalizer = CodeNormalizer()
        self._starter_line_hashes = self._build_starter_line_hashes(starter_sources)

    def remove(self, source: str) -> StarterRemovalResult:
        """Remove normalized lines that match known starter code."""
        lines = (source or "").splitlines()
        if not lines:
            return StarterRemovalResult("", 0, 0, 0.0)

        kept_lines: List[str] = []
        removed = 0
        for line in lines:
            line_hash = self._line_hash(line)
            if line_hash and line_hash in self._starter_line_hashes:
                removed += 1
                continue
            kept_lines.append(line)

        return StarterRemovalResult(
            filtered_source="\n".join(kept_lines),
            removed_line_count=removed,
            total_line_count=len(lines),
            starter_overlap=removed / len(lines),
        )

    def overlap(self, source: str) -> float:
        """Return the fraction of source lines matching starter code."""
        return self.remove(source).starter_overlap

    def _build_starter_line_hashes(self, starter_sources: Iterable[str]) -> Set[str]:
        """Hash non-empty normalized starter lines."""
        hashes: Set[str] = set()
        for source in starter_sources:
            for line in (source or "").splitlines():
                line_hash = self._line_hash(line)
                if line_hash:
                    hashes.add(line_hash)
        return hashes

    def _line_hash(self, line: str) -> str:
        """Hash a normalized line, ignoring comments, whitespace, names, and literals."""
        normalized = self.normalizer.normalize(line, self.language).normalized_code
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
