"""Data models for token-level heatmap system."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class HeatIntensity(str, Enum):
    """Heat intensity levels for UI rendering."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatchType(str, Enum):
    """Types of code matches."""
    AST = "ast"
    TOKEN = "token"
    SEMANTIC = "semantic"
    FUSED = "fused"


def confidence_to_intensity(confidence: float) -> HeatIntensity:
    """Convert confidence score to heat intensity level.
    
    Args:
        confidence: Confidence score between 0.0 and 1.0
        
    Returns:
        HeatIntensity level for UI rendering
    """
    if confidence > 0.85:
        return HeatIntensity.CRITICAL
    elif confidence > 0.7:
        return HeatIntensity.HIGH
    elif confidence > 0.5:
        return HeatIntensity.MEDIUM
    elif confidence > 0.3:
        return HeatIntensity.LOW
    return HeatIntensity.NONE


@dataclass
class TokenSpan:
    """
    Represents a character span of a token or matched region.
    
    Uses absolute character offsets for precise UI rendering.
    This eliminates false positives from line-based highlighting.
    
    Attributes:
        start: Absolute character offset in source code (0-indexed)
        end: Absolute character offset in source code (exclusive)
        confidence: Similarity confidence score [0.0, 1.0]
        match_type: Type of match (ast, token, semantic, fused)
        token_type: AST node type (e.g., 'function_call', 'identifier')
        matched_value: The actual code text covered by this span
        explanation: Human-readable explanation of why this span matched
    """
    start: int
    end: int
    confidence: float
    match_type: MatchType
    token_type: str = ""
    matched_value: str = ""
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        """Number of characters in this span."""
        return self.end - self.start
    
    @property
    def intensity(self) -> HeatIntensity:
        """Get heat intensity level for this span."""
        return confidence_to_intensity(self.confidence)
    
    def overlaps(self, other: "TokenSpan") -> bool:
        """Check if this span overlaps with another."""
        return not (self.end <= other.start or other.end <= self.start)
    
    def contains_offset(self, offset: int) -> bool:
        """Check if this span contains a specific character offset."""
        return self.start <= offset < self.end
    
    def intersect(self, other: "TokenSpan") -> Optional["TokenSpan"]:
        """Return the intersection of two spans, or None if they don't overlap."""
        if not self.overlaps(other):
            return None
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        confidence = max(self.confidence, other.confidence)
        return TokenSpan(
            start=start,
            end=end,
            confidence=confidence,
            match_type=self.match_type if self.confidence >= other.confidence else other.match_type,
            token_type=self.token_type or other.token_type,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start": self.start,
            "end": self.end,
            "confidence": round(self.confidence, 4),
            "match_type": self.match_type.value if isinstance(self.match_type, MatchType) else self.match_type,
            "token_type": self.token_type,
            "matched_value": self.matched_value,
            "explanation": self.explanation,
            "intensity": self.intensity.value,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenSpan":
        """Create TokenSpan from dictionary."""
        return cls(
            start=data["start"],
            end=data["end"],
            confidence=data["confidence"],
            match_type=MatchType(data["match_type"]),
            token_type=data.get("token_type", ""),
            matched_value=data.get("matched_value", ""),
            explanation=data.get("explanation", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CharacterMap:
    """
    Maps character positions to line/column for UI fallback.
    
    Precomputed index for fast offset → line/column conversion.
    Built once per source file, reused for all spans.
    """
    line_offsets: List[int] = field(default_factory=list)
    
    def build(self, code: str) -> "CharacterMap":
        """Build character map from source code.
        
        Args:
            code: Source code string
            
        Returns:
            Self for chaining
        """
        self.line_offsets = [0]
        for i, ch in enumerate(code):
            if ch == '\n':
                self.line_offsets.append(i + 1)
        return self
    
    def offset_to_line_column(self, offset: int) -> tuple:
        """Convert absolute character offset to (line, column).
        
        Args:
            offset: Absolute character offset (0-indexed)
            
        Returns:
            (line, column) where line is 1-indexed, column is 0-indexed
        """
        if not self.line_offsets:
            return (1, 0)
        
        # Binary search for the line
        lo, hi = 0, len(self.line_offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_offsets[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        line = lo + 1  # 1-indexed
        column = offset - self.line_offsets[lo]
        return (line, column)
    
    def span_to_line_range(self, span: TokenSpan) -> tuple:
        """Convert a TokenSpan to line range (start_line, end_line).
        
        Args:
            span: TokenSpan with character offsets
            
        Returns:
            (start_line, end_line) both 1-indexed
        """
        start_line, _ = self.offset_to_line_column(span.start)
        if span.end > span.start:
            end_offset = span.end - 1  # Last character in span
            end_line, _ = self.offset_to_line_column(end_offset)
        else:
            end_line = start_line
        return (start_line, end_line)


@dataclass
class HeatmapResult:
    """
    Complete token-level heatmap result for a code comparison.
    
    Contains all token spans needed for inline React rendering.
    """
    source_id: str  # Identifier for source A
    target_id: str  # Identifier for source B
    spans_a: List[TokenSpan] = field(default_factory=list)  # Spans for code A
    spans_b: List[TokenSpan] = field(default_factory=list)  # Spans for code B
    overall_confidence: float = 0.0
    match_count: int = 0
    total_chars_highlighted_a: int = 0
    total_chars_highlighted_b: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def empty(cls, source_id: str = "A", target_id: str = "B") -> "HeatmapResult":
        """Create an empty heatmap result."""
        return cls(source_id=source_id, target_id=target_id)
    
    @property
    def has_results(self) -> bool:
        """Check if there are any spans."""
        return bool(self.spans_a or self.spans_b)
    
    def compute_intensity_distribution(self, spans: List[TokenSpan]) -> Dict[str, float]:
        """Compute how much code is highlighted at each intensity level.
        
        Args:
            spans: List of token spans
            
        Returns:
            Dictionary mapping intensity levels to fraction of highlighted code
        """
        if not spans:
            return {}
        
        total_chars = sum(s.length for s in spans)
        if total_chars == 0:
            return {}
        
        distribution: Dict[str, int] = {
            HeatIntensity.LOW: 0,
            HeatIntensity.MEDIUM: 0,
            HeatIntensity.HIGH: 0,
            HeatIntensity.CRITICAL: 0,
        }
        
        for span in spans:
            level = span.intensity
            if level in distribution:
                distribution[level] += span.length
        
        return {k.value: v / total_chars for k, v in distribution.items()}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "spans_a": [s.to_dict() for s in self.spans_a],
            "spans_b": [s.to_dict() for s in self.spans_b],
            "overall_confidence": round(self.overall_confidence, 4),
            "match_count": self.match_count,
            "total_chars_highlighted_a": self.total_chars_highlighted_a,
            "total_chars_highlighted_b": self.total_chars_highlighted_b,
            "intensity_distribution_a": self.compute_intensity_distribution(self.spans_a),
            "intensity_distribution_b": self.compute_intensity_distribution(self.spans_b),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeatmapResult":
        """Create HeatmapResult from dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            spans_a=[TokenSpan.from_dict(s) for s in data.get("spans_a", [])],
            spans_b=[TokenSpan.from_dict(s) for s in data.get("spans_b", [])],
            overall_confidence=data.get("overall_confidence", 0.0),
            match_count=data.get("match_count", 0),
            total_chars_highlighted_a=data.get("total_chars_highlighted_a", 0),
            total_chars_highlighted_b=data.get("total_chars_highlighted_b", 0),
            metadata=data.get("metadata", {}),
        )