"""
Code Segment Matching and Clone Detection.

Implements:
1. Side-by-side code segment highlighting for matching regions
2. Clone type classification (Type 1 / Type 2 / Type 3 / Type 4)
3. Token-based matching with winnowing for exact and near matches
"""

import difflib
import html
import re
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

#: ``SequenceMatcher`` with ``autojunk=False`` is quadratic; beyond this many lines
#: per file only the leading part is matched (``MatchResult.truncated`` says so).
MAX_MATCH_LINES = 5000
_TOKEN_CACHE_SIZE = 256


class CloneType(Enum):
    """Code clone types as per standard classification."""

    TYPE_1 = "Type 1"  # Exact copy without modifications
    TYPE_2 = "Type 2"  # Syntactically identical, renamed identifiers/literals
    TYPE_3 = "Type 3"  # Modified with added/removed statements
    TYPE_4 = "Type 4"  # Semantically equivalent, different syntax


class CodeSegment(NamedTuple):
    """Represents a matched code segment."""

    start_line_a: int
    end_line_a: int
    start_line_b: int
    end_line_b: int
    similarity: float
    clone_type: CloneType
    text_a: str
    text_b: str


@dataclass
class MatchResult:
    """Result of code matching between two files."""

    segments: list[CodeSegment]
    overall_similarity: float
    clone_distribution: dict[CloneType, int]
    total_matched_lines_a: int
    total_matched_lines_b: int
    truncated: bool = False


class CodeHighlighter:
    """Finds and highlights matching code segments between two files."""

    def __init__(self, min_match_length: int = 4, token_threshold: float = 0.8):
        self.min_match_length = min_match_length
        self.token_threshold = token_threshold
        # LRU keyed by the code itself. It was a plain dict keyed by ``hash(code)``:
        # unbounded, and a hash collision returned another file's tokens.
        self._token_cache: OrderedDict[tuple[str, bool], list[str]] = OrderedDict()

    def _normalize_identifiers(self, line: str) -> str:
        """Normalize identifiers, literals, strings and whitespace in a line.

        Used for clone matching so renamed identifiers still register as
        matching blocks (Type-2 clone detection). Whitespace is collapsed so
        indent-reformatted clones (e.g. tabs replaced by spaces) still match;
        without this, difflib finds no blocks for tidy-but-renamed code and
        coverage collapses to 0.0, which the fusion hard-gate then vetoes.
        """
        line = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", "IDENT", line)
        line = re.sub(r"\b\d+\.?\d*\b", "LITERAL", line)
        line = re.sub(r'["\'].*?["\']', "STRING", line)
        return " ".join(line.split())

    def _tokenize(self, code: str, normalize: bool = False) -> list[str]:
        """Tokenize code with optional normalization for clone detection."""
        cache_key = (code, normalize)
        cached = self._token_cache.get(cache_key)
        if cached is not None:
            self._token_cache.move_to_end(cache_key)
            return cached

        if normalize:
            # Normalize identifiers, literals, whitespace for Type 2 detection
            code = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", "IDENT", code)
            code = re.sub(r"\b\d+\.?\d*\b", "LITERAL", code)
            code = re.sub(r'["\'].*?["\']', "STRING", code)

        # Split into tokens
        token_pattern = r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:.]"
        tokens = re.findall(token_pattern, code.lower())

        self._token_cache[cache_key] = tokens
        while len(self._token_cache) > _TOKEN_CACHE_SIZE:
            self._token_cache.popitem(last=False)
        return tokens

    def _classify_clone_type(
        self, lines_a: list[str], lines_b: list[str]
    ) -> tuple[CloneType | None, float]:
        """Classify clone type and calculate similarity between two code segments.

        Returns ``(None, similarity)`` when the segments are not a clone.
        """
        # Exact match check (Type 1)
        if lines_a == lines_b:
            return CloneType.TYPE_1, 1.0

        # Token normalized match (Type 2)
        tokens_a = self._tokenize("\n".join(lines_a), normalize=True)
        tokens_b = self._tokenize("\n".join(lines_b), normalize=True)

        if tokens_a == tokens_b:
            return CloneType.TYPE_2, 0.95

        # Sequence matching for Type 3
        sequence_matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        similarity = sequence_matcher.ratio()

        if similarity >= 0.7:
            return CloneType.TYPE_3, similarity
        elif similarity >= 0.5:
            return CloneType.TYPE_4, similarity

        # Not considered a clone
        return None, similarity

    def find_matching_segments(self, code_a: str, code_b: str) -> MatchResult:
        """Find all matching code segments between two code files."""
        lines_a = [line.rstrip() for line in code_a.splitlines()]
        lines_b = [line.rstrip() for line in code_b.splitlines()]
        truncated = len(lines_a) > MAX_MATCH_LINES or len(lines_b) > MAX_MATCH_LINES
        lines_a, lines_b = lines_a[:MAX_MATCH_LINES], lines_b[:MAX_MATCH_LINES]

        # Match on identifier/literal-normalized lines so Type-2 (renamed)
        # clones register as matching blocks. Without this, difflib finds no
        # blocks for renamed code and coverage collapses to 0.0, which the
        # fusion hard-gate interprets as "no structural evidence" and vetoes.
        normalized_a = [self._normalize_identifiers(line) for line in lines_a]
        normalized_b = [self._normalize_identifiers(line) for line in lines_b]

        matcher = difflib.SequenceMatcher(
            None, normalized_a, normalized_b, autojunk=False
        )
        matching_blocks = matcher.get_matching_blocks()

        segments: list[CodeSegment] = []
        clone_counts = {t: 0 for t in CloneType}
        matched_a = set()
        matched_b = set()

        for block in matching_blocks:
            if block.size < self.min_match_length:
                continue

            start_a, start_b, length = block
            end_a = start_a + length - 1
            end_b = start_b + length - 1

            segment_a = lines_a[start_a : end_a + 1]
            segment_b = lines_b[start_b : end_b + 1]

            clone_type, similarity = self._classify_clone_type(segment_a, segment_b)

            if clone_type is not None:
                segments.append(
                    CodeSegment(
                        start_line_a=start_a + 1,
                        end_line_a=end_a + 1,
                        start_line_b=start_b + 1,
                        end_line_b=end_b + 1,
                        similarity=similarity,
                        clone_type=clone_type,
                        text_a="\n".join(segment_a),
                        text_b="\n".join(segment_b),
                    )
                )

                clone_counts[clone_type] += 1
                matched_a.update(range(start_a, end_a + 1))
                matched_b.update(range(start_b, end_b + 1))

        # Calculate overall statistics
        overall_similarity = matcher.ratio()
        total_matched_a = len(matched_a)
        total_matched_b = len(matched_b)

        return MatchResult(
            segments=segments,
            overall_similarity=overall_similarity,
            clone_distribution=clone_counts,
            total_matched_lines_a=total_matched_a,
            total_matched_lines_b=total_matched_b,
            truncated=truncated,
        )

    def generate_side_by_side_html(
        self,
        code_a: str,
        code_b: str,
        filename_a: str = "file_a.py",
        filename_b: str = "file_b.py",
    ) -> str:
        """Generate HTML side-by-side view with highlighted matching segments.

        Everything that originates from submissions (source lines, file names) is
        HTML-escaped. It was interpolated raw, so a submission containing
        ``<script>`` ran in the instructor's browser when the report was opened.
        The document also carries a ``Content-Security-Policy`` that forbids scripts.
        """
        result = self.find_matching_segments(code_a, code_b)

        lines_a = code_a.splitlines()
        lines_b = code_b.splitlines()

        matched_a = [False] * len(lines_a)
        matched_b = [False] * len(lines_b)

        for seg in result.segments:
            for i in range(seg.start_line_a - 1, min(seg.end_line_a, len(lines_a))):
                matched_a[i] = True
            for i in range(seg.start_line_b - 1, min(seg.end_line_b, len(lines_b))):
                matched_b[i] = True

        def render(lines: list[str], matched: list[bool]) -> str:
            return "".join(
                f'<div class="line{" matched" if matched[i] else ""}">'
                f'<span class="linenum">{i + 1}</span> {html.escape(line)}</div>'
                for i, line in enumerate(lines)
            )

        name_a, name_b = html.escape(filename_a), html.escape(filename_b)
        dist = result.clone_distribution
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <style>
        .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-family: monospace; }}
        .file-header {{ font-weight: bold; padding: 8px; background: #f0f0f0; margin-bottom: 8px; }}
        .line {{ padding: 2px 8px; white-space: pre-wrap; }}
        .matched {{ background-color: #fff3cd; }}
        .linenum {{ display: inline-block; width: 40px; color: #999; user-select: none; }}
        h1 {{ font-family: sans-serif; }}
        .stats {{ margin: 16px 0; font-family: sans-serif; }}
    </style>
    <title>Code Similarity Report</title>
</head>
<body>
    <h1>Code Similarity Analysis</h1>
    <div class="stats">
        Overall similarity: {result.overall_similarity:.1%}<br>
        Matched lines in {name_a}: {result.total_matched_lines_a} / {len(lines_a)}<br>
        Matched lines in {name_b}: {result.total_matched_lines_b} / {len(lines_b)}<br>
        Clones: Type 1: {dist[CloneType.TYPE_1]}, Type 2: {dist[CloneType.TYPE_2]},
                Type 3: {dist[CloneType.TYPE_3]}, Type 4: {dist[CloneType.TYPE_4]}
        {"<br><em>Large files: only the first %d lines were matched.</em>" % MAX_MATCH_LINES if result.truncated else ""}
    </div>
    <div class="container">
        <div>
            <div class="file-header">{name_a}</div>
            {render(lines_a, matched_a)}
        </div>
        <div>
            <div class="file-header">{name_b}</div>
            {render(lines_b, matched_b)}
        </div>
    </div>
</body>
</html>
"""
