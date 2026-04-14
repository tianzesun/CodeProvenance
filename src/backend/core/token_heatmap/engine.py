"""Token Heatmap Engine - Build token-level precision heatmaps.

Orchestrates all components to transform match blocks into
character-span heatmap data for inline UI rendering.

Pipeline:
    MatchBlocks → TokenHeatmapEngine.build_heatmap() → List[TokenSpan]
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

from .models import (
    TokenSpan,
    MatchType,
    HeatmapResult,
    CharacterMap,
    confidence_to_intensity,
)
from .extractor import ASTTokenExtractor
from .intensity import HeatIntensityCalculator

logger = logging.getLogger(__name__)


class TokenHeatmapEngine:
    """Builds token-level precision heatmaps from code comparison results.
    
    Transforms match blocks (from DiffGenerator or similar) into
    character-span heatmap data that enables inline highlighting
    with pixel-perfect precision.
    
    Usage:
        engine = TokenHeatmapEngine()
        result = engine.build_heatmap(
            code_a=code_a,
            code_b=code_b,
            matches=match_blocks
        )
        
    The result contains spans for both code A and code B, which can be
    passed directly to the React TokenHeatmapRenderer component.
    
    Attributes:
        extractor: AST token extractor for structure-aware extraction
        intensity_calc: Heat intensity calculator
        min_confidence: Minimum confidence threshold for highlighting
    """
    
    def __init__(
        self,
        language: str = "auto",
        min_confidence: float = 0.3,
        enable_ast_extraction: bool = True,
    ):
        """Initialize heatmap engine.
        
        Args:
            language: Programming language for AST extraction
            min_confidence: Minimum confidence for spans to be included
            enable_ast_extraction: Whether to use AST-aware extraction
        """
        self.extractor = ASTTokenExtractor(language=language)
        self.intensity_calc = HeatIntensityCalculator()
        self.min_confidence = min_confidence
        self.enable_ast_extraction = enable_ast_extraction
    
    def build_heatmap(
        self,
        code_a: str,
        code_b: str,
        matches: Optional[List[Dict[str, Any]]] = None,
        source_id: str = "A",
        target_id: str = "B",
    ) -> HeatmapResult:
        """Build token-level heatmap from code samples and matches.
        
        This is the main entry point. It converts match blocks into
        character-span TokenSpan objects for precise UI rendering.
        
        Args:
            code_a: Source code sample A
            code_b: Source code sample B
            matches: List of match blocks from DiffGenerator.
                     Each match should have:
                         - a_start, a_end: Line range in code A (1-indexed)
                         - b_start, b_end: Line range in code B (1-indexed)
                         - confidence: Similarity confidence [0, 1]
                         - match_type: "ast", "token", "semantic", or "fused"
                         - a_snippet, b_snippet: Code snippets (optional)
            source_id: Identifier for source A
            target_id: Identifier for source B
            
        Returns:
            HeatmapResult with spans for both code samples
        """
        if not code_a or not code_b:
            return HeatmapResult.empty(source_id, target_id)
        
        # Convert line-based matches to character-span based tokens
        spans_a, spans_b = self._matches_to_spans(
            code_a, code_b, matches or []
        )
        
        # Extract additional AST-level spans if enabled
        if self.enable_ast_extraction:
            ast_spans_a = self._extract_ast_match_spans(code_a, code_b, matches or [])
            ast_spans_b = self._extract_ast_match_spans_code_b(code_a, code_b, matches or [])
            spans_a.extend(ast_spans_a)
            spans_b.extend(ast_spans_b)
        
        # Apply intensity calculation
        spans_a = self.intensity_calc.calculate_batch(spans_a)
        spans_b = self.intensity_calc.calculate_batch(spans_b)
        
        # Merge overlapping spans
        spans_a = self.intensity_calc.merge_overlapping(spans_a)
        spans_b = self.intensity_calc.merge_overlapping(spans_b)
        
        # Filter by minimum confidence
        spans_a = [s for s in spans_a if s.confidence >= self.min_confidence]
        spans_b = [s for s in spans_b if s.confidence >= self.min_confidence]
        
        # Calculate coverage stats
        total_chars_a = sum(s.length for s in spans_a)
        total_chars_b = sum(s.length for s in spans_b)
        overall_conf = self._calculate_overall_confidence(spans_a, spans_b, matches or [])
        
        return HeatmapResult(
            source_id=source_id,
            target_id=target_id,
            spans_a=spans_a,
            spans_b=spans_b,
            overall_confidence=overall_conf,
            match_count=len(spans_a) + len(spans_b),
            total_chars_highlighted_a=total_chars_a,
            total_chars_highlighted_b=total_chars_b,
            metadata={
                "code_length_a": len(code_a),
                "code_length_b": len(code_b),
                "coverage_ratio_a": total_chars_a / len(code_a) if code_a else 0,
                "coverage_ratio_b": total_chars_b / len(code_b) if code_b else 0,
            }
        )
    
    def build_heatmap_for_single(
        self,
        code: str,
        spans: List[Dict[str, Any]],
        source_id: str = "code",
    ) -> List[TokenSpan]:
        """Build token spans for a single code sample.
        
        Useful when you already have character offsets and just need
        TokenSpan objects for UI rendering.
        
        Args:
            code: Source code
            spans: List of {"start": int, "end": int, "confidence": float, "match_type": str}
            source_id: Identifier for the code
            
        Returns:
            List of TokenSpan objects ready for rendering
        """
        result_spans = []
        
        for span_data in spans:
            # Map match_type string to enum
            match_type_str = span_data.get("match_type", "token")
            try:
                match_type = MatchType(match_type_str)
            except ValueError:
                match_type = MatchType.TOKEN
            
            token_span = TokenSpan(
                start=span_data.get("start", 0),
                end=span_data.get("end", 0),
                confidence=span_data.get("confidence", 0.5),
                match_type=match_type,
                token_type=span_data.get("token_type", ""),
                matched_value=span_data.get("text", code[span_data.get("start", 0):span_data.get("end", 0)]),
                explanation=span_data.get("explanation", ""),
            )
            result_spans.append(token_span)
        
        # Apply intensity and merge
        result_spans = self.intensity_calc.calculate_batch(result_spans)
        result_spans = self.intensity_calc.merge_overlapping(result_spans)
        result_spans = [s for s in result_spans if s.confidence >= self.min_confidence]
        
        return result_spans
    
    def _matches_to_spans(
        self,
        code_a: str,
        code_b: str,
        matches: List[Dict[str, Any]],
    ) -> Tuple[List[TokenSpan], List[TokenSpan]]:
        """Convert line-based match blocks to character-span tokens.
        
        Uses snippet information when available for more precise matching.
        Falls back to line-based conversion when snippets aren't available.
        
        Args:
            code_a: Source code A
            code_b: Source code B
            matches: List of match blocks
            
        Returns:
            (spans_a, spans_b) - TokenSpans for each code sample
        """
        spans_a: List[TokenSpan] = []
        spans_b: List[TokenSpan] = []
        
        for match in matches:
            # Extract match metadata
            confidence = match.get("confidence", 0.5)
            match_type_str = match.get("match_type", "token")
            
            try:
                match_type = MatchType(match_type_str)
            except ValueError:
                match_type = MatchType.TOKEN
            
            # Try to use character offsets directly if available
            if "a_start_offset" in match and "a_end_offset" in match:
                spans_a.append(TokenSpan(
                    start=match["a_start_offset"],
                    end=match["a_end_offset"],
                    confidence=confidence,
                    match_type=match_type,
                    matched_value=code_a[match["a_start_offset"]:match["a_end_offset"]],
                    explanation=match.get("explanation", ""),
                ))
                spans_b.append(TokenSpan(
                    start=match["b_start_offset"],
                    end=match["b_end_offset"],
                    confidence=confidence,
                    match_type=match_type,
                    matched_value=code_b[match["b_start_offset"]:match["b_end_offset"]],
                    explanation=match.get("explanation", ""),
                ))
                continue
            
            # Fall back to line-based conversion
            a_start_line = match.get("a_start", 1)
            a_end_line = match.get("a_end", a_start_line)
            b_start_line = match.get("b_start", 1)
            b_end_line = match.get("b_end", b_start_line)
            
            # Convert lines to character offsets
            a_start_offset = self._line_to_offset(code_a, a_start_line)
            a_end_offset = self._line_to_offset(code_a, a_end_line)
            b_start_offset = self._line_to_offset(code_b, b_start_line)
            b_end_offset = self._line_to_offset(code_b, b_end_line)
            
            # Try to refine using snippets if available
            a_snippet = match.get("a_snippet", "")
            b_snippet = match.get("b_snippet", "")
            
            if a_snippet:
                # Find more precise span within the line range
                refined = self._refine_span_with_snippet(
                    code_a, a_snippet, a_start_offset, a_end_offset
                )
                if refined:
                    a_start_offset, a_end_offset = refined
            
            if b_snippet:
                refined = self._refine_span_with_snippet(
                    code_b, b_snippet, b_start_offset, b_end_offset
                )
                if refined:
                    b_start_offset, b_end_offset = refined
            
            spans_a.append(TokenSpan(
                start=a_start_offset,
                end=a_end_offset,
                confidence=confidence,
                match_type=match_type,
                matched_value=code_a[a_start_offset:a_end_offset],
                explanation=match.get("explanation", ""),
            ))
            spans_b.append(TokenSpan(
                start=b_start_offset,
                end=b_end_offset,
                confidence=confidence,
                match_type=match_type,
                matched_value=code_b[b_start_offset:b_end_offset],
                explanation=match.get("explanation", ""),
            ))
        
        return spans_a, spans_b
    
    def _refine_span_with_snippet(
        self,
        code: str,
        snippet: str,
        start_offset: int,
        end_offset: int,
    ) -> Optional[Tuple[int, int]]:
        """Refine a character span by finding the exact snippet location.
        
        Args:
            code: Full source code
            snippet: Code snippet to find
            start_offset: Start of search region
            end_offset: End of search region
            
        Returns:
            (start, end) tuple of refined span, or None if not found
        """
        if not snippet:
            return None
        
        # Search for snippet in the region
        region = code[start_offset:end_offset]
        
        # Try to find the longest continuous non-whitespace match
        snippet_clean = snippet.strip()
        pos = region.find(snippet_clean)
        if pos >= 0:
            return (start_offset + pos, start_offset + pos + len(snippet_clean))
        
        # Try each line of the snippet
        snippet_lines = snippet.strip().split('\n')
        for line in snippet_lines:
            line = line.strip()
            if line:
                pos = region.find(line)
                if pos >= 0:
                    return (start_offset + pos, start_offset + pos + len(line))
        
        # Try token-level matching
        from .extractor import ASTTokenExtractor
        extractor = ASTTokenExtractor()
        code_tokens = extractor.extract(region)
        snippet_tokens = extractor.extract(snippet_clean)
        
        if snippet_tokens and code_tokens:
            # Find first and last matching token positions
            first_match = None
            last_match = None
            
            for snippet_tok in snippet_tokens[:5]:  # Check first 5 tokens
                for i, code_tok in enumerate(code_tokens):
                    if code_tok.get("text") == snippet_tok.get("text"):
                        if first_match is None:
                            first_match = code_tok.get("start", 0) + start_offset
                        last_match = code_tok.get("end", 0) + start_offset
            
            if first_match is not None and last_match is not None:
                return (first_match, last_match)
        
        return None
    
    def _line_to_offset(self, code: str, line: int) -> int:
        """Convert line number (1-indexed) to character offset.
        
        Args:
            code: Source code
            line: Line number (1-indexed), clamped to valid range
            
        Returns:
            Character offset (0-indexed) at the start of the line
        """
        if line <= 1:
            return 0
        
        lines = code.split('\n')
        line = min(line, len(lines))
        
        offset = 0
        for i in range(line - 1):
            offset += len(lines[i]) + 1  # +1 for newline
        
        return min(offset, len(code))
    
    def _extract_ast_match_spans(
        self,
        code_a: str,
        code_b: str,
        matches: List[Dict[str, Any]],
    ) -> List[TokenSpan]:
        """Extract AST-level token spans for code A.
        
        Provides additional precision by identifying specific AST nodes
        that contribute to the match.
        
        Args:
            code_a: Source code A
            code_b: Source code B (for context)
            matches: Match blocks for identifying regions of interest
            
        Returns:
            List of TokenSpan objects
        """
        spans: List[TokenSpan] = []
        
        # Extract all tokens from code A
        try:
            tokens_a = self.extractor.extract(code_a)
        except Exception as e:
            logger.warning(f"Failed to extract AST tokens: {e}")
            return spans
        
        # For each match that has high AST confidence, extract token spans
        for match in matches:
            if match.get("match_type") not in ("ast", "fused"):
                continue
            
            # Get the matched region
            start_line = match.get("a_start", 1)
            end_line = match.get("a_end", start_line)
            start_offset = self._line_to_offset(code_a, start_line)
            end_offset = self._line_to_offset(code_a, end_line)
            
            # Find tokens in this region
            for token in tokens_a:
                tok_start = token.get("start", 0)
                tok_end = token.get("end", 0)
                
                if start_offset <= tok_start < end_offset:
                    # This token is in the matched region
                    match_type = MatchType.AST
                    if match.get("match_type") == "fused":
                        match_type = MatchType.FUSED
                    
                    spans.append(TokenSpan(
                        start=tok_start,
                        end=tok_end,
                        confidence=match.get("confidence", 0.7),
                        match_type=match_type,
                        token_type=token.get("type", ""),
                        matched_value=token.get("text", ""),
                        explanation=f"AST-level {token.get('type', 'node')} match",
                    ))
        
        return spans
    
    def _extract_ast_match_spans_code_b(
        self,
        code_a: str,
        code_b: str,
        matches: List[Dict[str, Any]],
    ) -> List[TokenSpan]:
        """Extract AST-level token spans for code B.
        
        Same as _extract_ast_match_spans but for code B.
        
        Args:
            code_a: Source code A
            code_b: Source code B
            matches: Match blocks
            
        Returns:
            List of TokenSpan objects
        """
        spans: List[TokenSpan] = []
        
        try:
            tokens_b = self.extractor.extract(code_b)
        except Exception as e:
            logger.warning(f"Failed to extract AST tokens for code B: {e}")
            return spans
        
        for match in matches:
            if match.get("match_type") not in ("ast", "fused"):
                continue
            
            start_line = match.get("b_start", 1)
            end_line = match.get("b_end", start_line)
            start_offset = self._line_to_offset(code_b, start_line)
            end_offset = self._line_to_offset(code_b, end_line)
            
            for token in tokens_b:
                tok_start = token.get("start", 0)
                tok_end = token.get("end", 0)
                
                if start_offset <= tok_start < end_offset:
                    match_type = MatchType.AST
                    if match.get("match_type") == "fused":
                        match_type = MatchType.FUSED
                    
                    spans.append(TokenSpan(
                        start=tok_start,
                        end=tok_end,
                        confidence=match.get("confidence", 0.7),
                        match_type=match_type,
                        token_type=token.get("type", ""),
                        matched_value=token.get("text", ""),
                        explanation=f"AST-level {token.get('type', 'node')} match",
                    ))
        
        return spans
    
    def _calculate_overall_confidence(
        self,
        spans_a: List[TokenSpan],
        spans_b: List[TokenSpan],
        matches: List[Dict[str, Any]],
    ) -> float:
        """Calculate overall confidence from spans and matches.
        
        Args:
            spans_a: Token spans for code A
            spans_b: Token spans for code B
            matches: Original match blocks
            
        Returns:
            Overall confidence score [0, 1]
        """
        if not spans_a and not spans_b:
            return 0.0
        
        # Weighted average of span confidences
        all_spans = spans_a + spans_b
        if all_spans:
            total_weight = sum(s.length for s in all_spans)
            if total_weight > 0:
                return sum(s.confidence * s.length for s in all_spans) / total_weight
        
        # Fall back to average match confidence
        if matches:
            return sum(m.get("confidence", 0) for m in matches) / len(matches)
        
        return 0.0