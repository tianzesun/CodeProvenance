"""Intelligent code chunking for large file analysis.

Handles submissions >10k lines by splitting into semantic chunks that preserve
code structure and enable parallel analysis without memory exhaustion.

Strategy:
1. Split at natural boundaries (class/function definitions)
2. Maintain overlap for context continuity
3. Track chunk metadata for result aggregation
4. Support incremental processing for massive files
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Chunking thresholds
MAX_LINES_PER_CHUNK = 5000  # Target chunk size
MIN_LINES_PER_CHUNK = 1000  # Don't create tiny chunks
OVERLAP_LINES = 100  # Context overlap between chunks


@dataclass
class CodeChunk:
    """A semantic chunk of code with metadata."""

    chunk_id: int
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed (inclusive)
    content: str
    line_count: int
    hash: str
    is_complete_unit: bool  # True if chunk contains complete functions/classes
    parent_context: str | None = (
        None  # Class/function name if chunk is part of larger unit
    )


@dataclass
class ChunkingResult:
    """Result of chunking a large file."""

    original_size: int  # Total lines in original file
    chunk_count: int
    chunks: list[CodeChunk]
    strategy: str  # "ast" | "heuristic" | "simple"
    metadata: dict[str, Any]


class CodeChunker:
    """Split large code files into manageable chunks."""

    def __init__(
        self,
        max_lines: int = MAX_LINES_PER_CHUNK,
        min_lines: int = MIN_LINES_PER_CHUNK,
        overlap: int = OVERLAP_LINES,
    ):
        """Initialize chunker with size parameters.

        Args:
            max_lines: Target maximum lines per chunk
            min_lines: Minimum lines per chunk (avoid tiny chunks)
            overlap: Lines of overlap between chunks for context
        """
        self.max_lines = max_lines
        self.min_lines = min_lines
        self.overlap = overlap

    def chunk_code(
        self, code: str, language: str = "python", filename: str = ""
    ) -> ChunkingResult:
        """Chunk code intelligently based on language and structure.

        Args:
            code: Source code to chunk
            language: Programming language (python, java, javascript, etc)
            filename: Optional filename for logging

        Returns:
            ChunkingResult with chunks and metadata
        """
        lines = code.split("\n")
        total_lines = len(lines)

        # No chunking needed for small files
        if total_lines <= self.max_lines:
            return ChunkingResult(
                original_size=total_lines,
                chunk_count=1,
                chunks=[
                    CodeChunk(
                        chunk_id=0,
                        start_line=1,
                        end_line=total_lines,
                        content=code,
                        line_count=total_lines,
                        hash=self._hash_content(code),
                        is_complete_unit=True,
                    )
                ],
                strategy="no_chunking",
                metadata={"reason": "file under threshold"},
            )

        logger.info(
            f"Chunking large file: {filename} ({total_lines} lines, {language})"
        )

        # Try AST-based chunking for supported languages
        if language == "python":
            result = self._chunk_python_ast(code, lines)
            if result:
                logger.info(f"Used AST chunking: {result.chunk_count} chunks")
                return result

        # Fall back to heuristic chunking
        result = self._chunk_heuristic(code, lines, language)
        logger.info(f"Used heuristic chunking: {result.chunk_count} chunks")
        return result

    def _chunk_python_ast(self, code: str, lines: list[str]) -> ChunkingResult | None:
        """Chunk Python code using AST to find natural boundaries.

        Creates chunks at class/function boundaries to preserve semantic units.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            logger.debug("AST parse failed, falling back to heuristic")
            return None

        # Find top-level definitions (classes, functions)
        boundaries: list[tuple[int, int, str]] = []  # (start, end, name)

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only top-level or immediate class members
                if not isinstance(node, ast.Module):
                    start = node.lineno
                    end = node.end_lineno if node.end_lineno else start + 50
                    name = f"{node.__class__.__name__}: {node.name}"
                    boundaries.append((start, end, name))

        if not boundaries:
            return None

        # Sort by start line
        boundaries.sort(key=lambda x: x[0])

        # Group boundaries into chunks
        chunks: list[CodeChunk] = []
        current_chunk_start = 1
        current_chunk_boundaries: list[tuple[int, int, str]] = []

        for start, end, name in boundaries:
            chunk_size = end - current_chunk_start + 1

            if chunk_size > self.max_lines and current_chunk_boundaries:
                # Emit current chunk
                chunk_end = current_chunk_boundaries[-1][1]
                chunks.append(
                    self._create_chunk(
                        chunk_id=len(chunks),
                        start_line=current_chunk_start,
                        end_line=chunk_end,
                        lines=lines,
                        is_complete=True,
                        context=None,
                    )
                )
                # Start new chunk with overlap
                current_chunk_start = max(1, chunk_end - self.overlap)
                current_chunk_boundaries = []

            current_chunk_boundaries.append((start, end, name))

        # Emit final chunk
        if current_chunk_boundaries:
            chunk_end = min(len(lines), current_chunk_boundaries[-1][1])
            chunks.append(
                self._create_chunk(
                    chunk_id=len(chunks),
                    start_line=current_chunk_start,
                    end_line=chunk_end,
                    lines=lines,
                    is_complete=True,
                    context=None,
                )
            )

        # Handle any remaining lines after last boundary
        if chunks and chunks[-1].end_line < len(lines):
            remaining_start = chunks[-1].end_line - self.overlap
            chunks.append(
                self._create_chunk(
                    chunk_id=len(chunks),
                    start_line=remaining_start,
                    end_line=len(lines),
                    lines=lines,
                    is_complete=False,
                    context="tail",
                )
            )

        return ChunkingResult(
            original_size=len(lines),
            chunk_count=len(chunks),
            chunks=chunks,
            strategy="ast",
            metadata={
                "boundaries_found": len(boundaries),
                "language": "python",
            },
        )

    def _chunk_heuristic(
        self, code: str, lines: list[str], language: str
    ) -> ChunkingResult:
        """Chunk code using heuristic patterns for any language.

        Looks for common patterns:
        - Empty lines (natural breaks)
        - Function/class signatures
        - Comment blocks
        - Indentation changes
        """
        # Find potential split points (prefer empty lines or comment blocks)
        split_points: list[int] = [0]

        for i in range(0, len(lines), self.max_lines):
            # Look for good split point in next window
            window_start = i
            window_end = min(len(lines), i + self.max_lines)

            # Search backwards from max_lines for natural break
            best_split = window_end
            for j in range(window_end - 1, window_start, -1):
                line = lines[j].strip()

                # Empty line (best)
                if not line:
                    best_split = j
                    break

                # Comment block end
                if language == "python" and (line.startswith("#") or '"""' in line):
                    best_split = j
                    break

                # Function/class definition
                if self._is_definition_line(line, language):
                    best_split = j
                    break

            if best_split > split_points[-1]:
                split_points.append(best_split)

        # Ensure we cover entire file
        if split_points[-1] < len(lines):
            split_points.append(len(lines))

        # Create chunks with overlap
        chunks: list[CodeChunk] = []
        for i in range(len(split_points) - 1):
            start = max(0, split_points[i] - self.overlap if i > 0 else 0)
            end = split_points[i + 1]

            chunks.append(
                self._create_chunk(
                    chunk_id=i,
                    start_line=start + 1,  # 1-indexed
                    end_line=end,
                    lines=lines,
                    is_complete=False,
                    context=None,
                )
            )

        return ChunkingResult(
            original_size=len(lines),
            chunk_count=len(chunks),
            chunks=chunks,
            strategy="heuristic",
            metadata={
                "language": language,
                "split_points": len(split_points),
            },
        )

    def _is_definition_line(self, line: str, language: str) -> bool:
        """Check if line is a function/class definition."""
        if language == "python":
            return line.startswith("def ") or line.startswith("class ")
        elif language == "java":
            return (
                "class " in line
                or "interface " in line
                or "public " in line
                or "private " in line
            )
        elif language == "javascript":
            return (
                line.startswith("function ")
                or line.startswith("class ")
                or "=> {" in line
            )
        return False

    def _create_chunk(
        self,
        chunk_id: int,
        start_line: int,
        end_line: int,
        lines: list[str],
        is_complete: bool,
        context: str | None,
    ) -> CodeChunk:
        """Create a CodeChunk from line range."""
        content = "\n".join(lines[start_line - 1 : end_line])
        return CodeChunk(
            chunk_id=chunk_id,
            start_line=start_line,
            end_line=end_line,
            content=content,
            line_count=end_line - start_line + 1,
            hash=self._hash_content(content),
            is_complete_unit=is_complete,
            parent_context=context,
        )

    def _hash_content(self, content: str) -> str:
        """Generate hash for chunk deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def merge_chunk_results(
        self, chunk_results: list[dict[str, Any]], chunking_result: ChunkingResult
    ) -> dict[str, Any]:
        """Merge analysis results from multiple chunks into single result.

        Args:
            chunk_results: List of analysis results, one per chunk
            chunking_result: Original chunking metadata

        Returns:
            Merged result representing entire file
        """
        if len(chunk_results) == 1:
            return chunk_results[0]

        # Aggregate scores (weighted by chunk size)
        total_lines = sum(r.get("line_count", 0) for r in chunk_results)
        merged = {
            "chunked": True,
            "original_lines": chunking_result.original_size,
            "chunk_count": chunking_result.chunk_count,
            "strategy": chunking_result.strategy,
        }

        # Weighted average for numeric scores
        numeric_keys = [
            "similarity_score",
            "ai_probability",
            "perplexity",
            "complexity",
        ]
        for key in numeric_keys:
            values = [r.get(key, 0) for r in chunk_results if key in r]
            if values:
                weights = [r.get("line_count", 1) for r in chunk_results if key in r]
                merged[key] = sum(v * w for v, w in zip(values, weights)) / sum(weights)

        # Union for lists/sets
        list_keys = ["matching_blocks", "flagged_lines", "indicators"]
        for key in list_keys:
            items = []
            for r in chunk_results:
                if key in r and isinstance(r[key], list):
                    items.extend(r[key])
            if items:
                merged[key] = items

        # Dict merge for nested data
        dict_keys = ["features", "signals", "algorithm_scores"]
        for key in dict_keys:
            merged_dict = {}
            for r in chunk_results:
                if key in r and isinstance(r[key], dict):
                    for k, v in r[key].items():
                        if k in merged_dict:
                            # Average numeric values
                            if isinstance(v, (int, float)):
                                merged_dict[k] = (merged_dict[k] + v) / 2
                        else:
                            merged_dict[k] = v
            if merged_dict:
                merged[key] = merged_dict

        return merged


# Global instance
_chunker = CodeChunker()


def chunk_large_file(
    code: str, language: str = "python", filename: str = ""
) -> ChunkingResult:
    """Convenience function to chunk a large file."""
    return _chunker.chunk_code(code, language, filename)


def should_chunk(code: str, threshold: int = MAX_LINES_PER_CHUNK) -> bool:
    """Check if code exceeds chunking threshold."""
    return code.count("\n") > threshold


def merge_results(
    chunk_results: list[dict[str, Any]], chunking_result: ChunkingResult
) -> dict[str, Any]:
    """Convenience function to merge chunk results."""
    return _chunker.merge_chunk_results(chunk_results, chunking_result)
