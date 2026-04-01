"""Heat Intensity Calculator - Compute heat levels for token spans.

Converts confidence scores to visual heat intensity levels for UI rendering.
Handles overlapping spans with max-confidence resolution.
"""
from typing import List, Dict, Any

from .models import (
    TokenSpan,
    MatchType,
    HeatIntensity,
    confidence_to_intensity,
)


class HeatIntensityCalculator:
    """Calculates heat intensity for token-level spans.
    
    Provides configurable intensity calculation based on:
    - Match confidence score
    - Match type (AST > fused > token > semantic)
    - Overlap handling with max-confidence resolution
    
    Attributes:
        ast_bonus: Bonus for AST-level matches
        token_bonus: Bonus for token-level matches
        fused_bonus: Bonus for multi-engine agreement
        semantic_bonus: Bonus for semantic matches
    """
    
    def __init__(
        self,
        ast_bonus: float = 0.15,
        token_bonus: float = 0.05,
        fused_bonus: float = 0.10,
        semantic_bonus: float = 0.08,
    ):
        """Initialize calculator with configurable bonuses.
        
        Args:
            ast_bonus: Bonus for AST-level structural matches
            token_bonus: Bonus for token-level lexical matches
            fused_bonus: Bonus for multi-engine agreement
            semantic_bonus: Bonus for semantic similarity
        """
        self.ast_bonus = ast_bonus
        self.token_bonus = token_bonus
        self.fused_bonus = fused_bonus
        self.semantic_bonus = semantic_bonus
        self.type_bonuses = {
            MatchType.AST: ast_bonus,
            MatchType.TOKEN: token_bonus,
            MatchType.FUSED: fused_bonus,
            MatchType.SEMANTIC: semantic_bonus,
        }
    
    @staticmethod
    def to_intensity(confidence: float) -> HeatIntensity:
        """Convert confidence to heat intensity level.
        
        Args:
            confidence: Confidence score [0.0, 1.0]
            
        Returns:
            HeatIntensity level
        """
        return confidence_to_intensity(confidence)
    
    def calculate_intensity(self, span: TokenSpan) -> TokenSpan:
        """Calculate heat intensity for a single span.
        
        Args:
            span: Input token span
            
        Returns:
            New TokenSpan with adjusted confidence
        """
        bonus = self.type_bonuses.get(span.match_type, 0.0)
        adjusted_confidence = min(span.confidence + bonus, 1.0)
        
        return TokenSpan(
            start=span.start,
            end=span.end,
            confidence=adjusted_confidence,
            match_type=span.match_type,
            token_type=span.token_type,
            matched_value=span.matched_value,
            explanation=span.explanation,
            metadata=span.metadata,
        )
    
    def calculate_batch(self, spans: List[TokenSpan]) -> List[TokenSpan]:
        """Calculate heat intensity for multiple spans.
        
        Args:
            spans: List of input token spans
            
        Returns:
            List of spans with adjusted confidence values
        """
        return [self.calculate_intensity(span) for span in spans]
    
    def merge_overlapping(self, spans: List[TokenSpan]) -> List[TokenSpan]:
        """Merge overlapping spans, keeping maximum confidence.
        
        Args:
            spans: List of token spans
            
        Returns:
            Merged list with no overlapping spans
        """
        if not spans:
            return []
        
        sorted_spans = sorted(spans, key=lambda s: s.start)
        result: List[TokenSpan] = [sorted_spans[0]]
        
        for current in sorted_spans[1:]:
            last = result[-1]
            if last.overlaps(current):
                merged = self._merge_two_spans(last, current)
                result[-1] = merged[0]
                result.extend(merged[1:])
            else:
                result.append(current)
        
        return result
    
    def _merge_two_spans(self, a: TokenSpan, b: TokenSpan) -> List[TokenSpan]:
        """Merge two overlapping spans into non-overlapping segments."""
        result = []
        
        if a.start > b.start:
            a, b = b, a
        
        if a.end >= b.end:
            if b.confidence > a.confidence:
                result.append(TokenSpan(
                    start=a.start, end=a.end,
                    confidence=max(a.confidence, b.confidence),
                    match_type=a.match_type if a.confidence >= b.confidence else b.match_type,
                    token_type=a.token_type or b.token_type,
                    matched_value=a.matched_value or b.matched_value,
                ))
            else:
                result.append(a)
            return result
        
        if b.start < a.end:
            if b.start > a.start:
                result.append(TokenSpan(
                    start=a.start, end=b.start,
                    confidence=a.confidence, match_type=a.match_type,
                    token_type=a.token_type, matched_value=a.matched_value,
                ))
            
            result.append(TokenSpan(
                start=b.start, end=min(a.end, b.end),
                confidence=max(a.confidence, b.confidence),
                match_type=a.match_type if a.confidence >= b.confidence else b.match_type,
                token_type=a.token_type or b.token_type,
            ))
            
            if a.end < b.end:
                result.append(TokenSpan(
                    start=a.end, end=b.end,
                    confidence=b.confidence, match_type=b.match_type,
                    token_type=b.token_type, matched_value=b.matched_value,
                    explanation=b.explanation, metadata=b.metadata,
                ))
        else:
            result.extend([a, b])
        
        return result
    
    def build_heatmap_array(self, spans: List[TokenSpan], code_length: int) -> List[float]:
        """Build a character-level heatmap array from spans."""
        heatmap = [0.0] * code_length
        for span in spans:
            for i in range(span.start, min(span.end, code_length)):
                heatmap[i] = max(heatmap[i], span.confidence)
        return heatmap
    
    def get_coverage_stats(self, spans: List[TokenSpan], code_length: int) -> Dict[str, float]:
        """Calculate coverage statistics for spans."""
        if code_length == 0:
            return {
                "total_highlighted": 0, "coverage_ratio": 0.0,
                "avg_confidence": 0.0, "max_confidence": 0.0,
            }
        
        heatmap = self.build_heatmap_array(spans, code_length)
        highlighted_chars = sum(1 for v in heatmap if v > 0)
        highlighted_confidences = [v for v in heatmap if v > 0]
        
        return {
            "total_highlighted": highlighted_chars,
            "coverage_ratio": highlighted_chars / code_length,
            "avg_confidence": sum(highlighted_confidences) / len(highlighted_confidences) if highlighted_confidences else 0.0,
            "max_confidence": max(heatmap) if heatmap else 0.0,
        }