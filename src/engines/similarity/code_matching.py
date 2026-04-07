"""
Code Segment Matching and Clone Detection.

Implements:
1. Side-by-side code segment highlighting for matching regions
2. Clone type classification (Type 1 / Type 2 / Type 3 / Type 4)
3. Token-based matching with winnowing for exact and near matches
"""

import re
import difflib
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional, NamedTuple
from dataclasses import dataclass


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

    segments: List[CodeSegment]
    overall_similarity: float
    clone_distribution: Dict[CloneType, int]
    total_matched_lines_a: int
    total_matched_lines_b: int


class CodeHighlighter:
    """Finds and highlights matching code segments between two files."""

    def __init__(self, min_match_length: int = 4, token_threshold: float = 0.8):
        self.min_match_length = min_match_length
        self.token_threshold = token_threshold
        self._token_cache: Dict[str, List[str]] = {}

    def _tokenize(self, code: str, normalize: bool = False) -> List[str]:
        """Tokenize code with optional normalization for clone detection."""
        cache_key = f"{hash(code)}:{normalize}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]

        if normalize:
            # Normalize identifiers, literals, whitespace for Type 2 detection
            code = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", "IDENT", code)
            code = re.sub(r"\b\d+\.?\d*\b", "LITERAL", code)
            code = re.sub(r'["\'].*?["\']', "STRING", code)

        # Split into tokens
        token_pattern = r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:.]"
        tokens = re.findall(token_pattern, code.lower())

        self._token_cache[cache_key] = tokens
        return tokens

    def _classify_clone_type(
        self, lines_a: List[str], lines_b: List[str]
    ) -> Tuple[CloneType, float]:
        """Classify clone type and calculate similarity between two code segments."""
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

        matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
        matching_blocks = matcher.get_matching_blocks()

        segments: List[CodeSegment] = []
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
        )

    def generate_side_by_side_html(
        self,
        code_a: str,
        code_b: str,
        filename_a: str = "file_a.py",
        filename_b: str = "file_b.py",
    ) -> str:
        """Generate HTML side-by-side view with highlighted matching segments."""
        result = self.find_matching_segments(code_a, code_b)

        lines_a = code_a.splitlines()
        lines_b = code_b.splitlines()

        # Mark matched lines
        matched_a = [False] * len(lines_a)
        matched_b = [False] * len(lines_b)

        for seg in result.segments:
            for i in range(seg.start_line_a - 1, seg.end_line_a):
                matched_a[i] = True
            for i in range(seg.start_line_b - 1, seg.end_line_b):
                matched_b[i] = True

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-family: monospace; }}
        .file-header {{ font-weight: bold; padding: 8px; background: #f0f0f0; margin-bottom: 8px; }}
        .line {{ padding: 2px 8px; }}
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
        Matched lines in {filename_a}: {result.total_matched_lines_a} / {
            len(lines_a)
        }<br>
        Matched lines in {filename_b}: {result.total_matched_lines_b} / {
            len(lines_b)
        }<br>
        Clones: Type 1: {result.clone_distribution[CloneType.TYPE_1]}, 
                Type 2: {result.clone_distribution[CloneType.TYPE_2]}, 
                Type 3: {result.clone_distribution[CloneType.TYPE_3]}, 
                Type 4: {result.clone_distribution[CloneType.TYPE_4]}
    </div>
    <div class="container">
        <div>
            <div class="file-header">{filename_a}</div>
            {
            "".join(
                f'<div class="line {"matched" if matched_a[i] else ""}"><span class="linenum">{i + 1}</span> {line}</div>'
                for i, line in enumerate(lines_a)
            )
        }
        </div>
        <div>
            <div class="file-header">{filename_b}</div>
            {
            "".join(
                f'<div class="line {"matched" if matched_b[i] else ""}"><span class="linenum">{i + 1}</span> {line}</div>'
                for i, line in enumerate(lines_b)
            )
        }
        </div>
    </div>
</body>
</html>
"""
        return html
