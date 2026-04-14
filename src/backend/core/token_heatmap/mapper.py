"""Character Offset Mapper - Convert between different position representations.

Provides utilities for converting between:
- Absolute character offsets (0-indexed from start of file)
- Line:column pairs (1-indexed line, 0-indexed column)
- Token positions from various parsers
"""
from typing import List, Dict, Any, Tuple
import bisect


class CharacterOffsetMapper:
    """Maps between absolute character offsets and line:column positions.
    
    Built once per source file, reused for all character position conversions.
    O(log n) lookup using binary search.
    
    Attributes:
        code: The source code string
        line_offsets: List of character offsets for each line start
    """
    
    def __init__(self):
        """Initialize mapper. Call build() to set up with code."""
        self.code = ""
        self.line_offsets: List[int] = [0]
    
    def build(self, code: str) -> "CharacterOffsetMapper":
        """Build index from source code.
        
        Args:
            code: Source code string
            
        Returns:
            Self for chaining
        """
        self.code = code
        self.line_offsets = [0]
        
        for i, char in enumerate(code):
            if char == '\n':
                self.line_offsets.append(i + 1)
        
        return self
    
    @property
    def total_lines(self) -> int:
        """Total number of lines in the source code."""
        return len(self.line_offsets)
    
    @property
    def total_chars(self) -> int:
        """Total number of characters in the source code."""
        return len(self.code)
    
    def offset_to_line_column(self, offset: int) -> Tuple[int, int]:
        """Convert absolute character offset to (line, column).
        
        Args:
            offset: Absolute character offset (0-indexed)
            
        Returns:
            (line, column) where line is 1-indexed, column is 0-indexed
        """
        if not self.line_offsets:
            return (1, 0)
        
        # Clamp offset to valid range
        offset = max(0, min(offset, len(self.code)))
        
        # Binary search for the line
        idx = bisect.bisect_right(self.line_offsets, offset) - 1
        idx = max(0, min(idx, len(self.line_offsets) - 1))
        
        line = idx + 1  # 1-indexed
        column = offset - self.line_offsets[idx]
        
        return (line, column)
    
    def line_column_to_offset(self, line: int, column: int) -> int:
        """Convert (line, column) to absolute character offset.
        
        Args:
            line: Line number (1-indexed)
            column: Column number (0-indexed)
            
        Returns:
            Absolute character offset (0-indexed)
        """
        if not self.line_offsets:
            return 0
        
        # Clamp line to valid range
        line_idx = max(0, min(line - 1, len(self.line_offsets) - 1))
        
        offset = self.line_offsets[line_idx] + column
        return max(0, min(offset, len(self.code)))
    
    def span_to_dict(self, start_offset: int, end_offset: int) -> Dict[str, Any]:
        """Convert character span to dictionary with line/column info.
        
        Args:
            start_offset: Start character offset
            end_offset: End character offset (exclusive)
            
        Returns:
            Dictionary with start/end line:column and offsets
        """
        start_line, start_col = self.offset_to_line_column(start_offset)
        end_line, end_col = self.offset_to_line_column(max(0, end_offset - 1))
        
        return {
            "start_offset": start_offset,
            "end_offset": end_offset,
            "start_line": start_line,
            "start_column": start_col,
            "end_line": end_line,
            "end_column": end_col,
            "text": self.code[start_offset:end_offset],
        }
    
    def get_line_text(self, line: int) -> str:
        """Get the full text of a line.
        
        Args:
            line: Line number (1-indexed)
            
        Returns:
            Line text (without newline character)
        """
        if not self.line_offsets or line < 1:
            return ""
        
        line_idx = line - 1
        if line_idx >= len(self.line_offsets):
            return ""
        
        start = self.line_offsets[line_idx]
        if line_idx + 1 < len(self.line_offsets):
            end = self.line_offsets[line_idx + 1] - 1  # Exclude newline
        else:
            end = len(self.code)
        
        return self.code[start:end]
    
    def get_line_range_offsets(self, line: int) -> Tuple[int, int]:
        """Get start and end offsets for a line.
        
        Args:
            line: Line number (1-indexed)
            
        Returns:
            (start_offset, end_offset) where end is exclusive
        """
        if not self.line_offsets or line < 1:
            return (0, 0)
        
        line_idx = line - 1
        if line_idx >= len(self.line_offsets):
            return (len(self.code), len(self.code))
        
        start = self.line_offsets[line_idx]
        if line_idx + 1 < len(self.line_offsets):
            end = self.line_offsets[line_idx + 1]
        else:
            end = len(self.code)
        
        return (start, end)
    
    def merge_spans(self, spans: List[Dict[str, int]]) -> List[Dict[str, int]]:
        """Merge overlapping spans.
        
        Args:
            spans: List of {"start": int, "end": int} dictionaries
            
        Returns:
            Merged list of non-overlapping spans
        """
        if not spans:
            return []
        
        # Sort by start position
        sorted_spans = sorted(spans, key=lambda s: s["start"])
        merged = [sorted_spans[0].copy()]
        
        for current in sorted_spans[1:]:
            last = merged[-1]
            if current["start"] <= last["end"]:
                # Overlapping, extend the last span
                last["end"] = max(last["end"], current["end"])
            else:
                # Non-overlapping, add new span
                merged.append(current.copy())
        
        return merged