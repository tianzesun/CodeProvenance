"""Diff Generator - Matched blocks detection for plagiarism reports.

Takes AST matches, token matches, and similarity alignments,
outputs structured matched blocks for UI rendering.
"""
import difflib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class MatchedBlock:
    """A block of matching code between two files."""
    a_start: int
    a_end: int
    b_start: int
    b_end: int
    match_type: str  # identical, renamed, logic_similar
    confidence: float
    a_snippet: str = ""
    b_snippet: str = ""
    tokens_matched: int = 0
    features: Dict[str, float] = field(default_factory=dict)


class DiffGenerator:
    """Generates structured match blocks for plagiarism reports."""
    
    @staticmethod
    def compute_matched_blocks(
        code_a: str, code_b: str,
        features: Optional[Dict[str, float]] = None
    ) -> List[MatchedBlock]:
        """
        Compute matched code blocks between two code samples.
        
        Uses difflib.SequenceMatcher for line-level matching,
        enhanced with token-level analysis for confidence scoring.
        
        Args:
            code_a: First code sample
            code_b: Second code sample
            features: Optional feature dict with engine scores
            
        Returns:
            List of MatchedBlock objects
        """
        lines_a = code_a.splitlines(keepends=True)
        lines_b = code_b.splitlines(keepends=True)
        
        # Use unified diff matcher
        matcher = difflib.SequenceMatcher(
            lambda x: x.strip() in ('', '#', '//', '/*'),
            lines_a, lines_b
        )
        
        blocks = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                confidence = min(1.0, (i2 - i1) / 5.0)  # Scale by block size
                blocks.append(MatchedBlock(
                    a_start=i1 + 1, a_end=i2,
                    b_start=j1 + 1, b_end=j2,
                    match_type='identical',
                    confidence=confidence,
                    a_snippet=''.join(lines_a[i1:i2]),
                    b_snippet=''.join(lines_b[j1:j2]),
                ))
            elif tag == 'replace':
                # Check if it's a rename/logic match
                block_a = ''.join(lines_a[i1:i2])
                block_b = ''.join(lines_b[j1:j2])
                sub_match = difflib.SequenceMatcher(None, block_a, block_b).ratio()
                if sub_match > 0.3:
                    blocks.append(MatchedBlock(
                        a_start=i1 + 1, a_end=i2,
                        b_start=j1 + 1, b_end=j2,
                        match_type='logic_similar' if sub_match < 0.7 else 'renamed',
                        confidence=round(sub_match, 3),
                        a_snippet=block_a,
                        b_snippet=block_b,
                    ))
        
        return blocks
    
    @staticmethod
    def generate_diff_summary(blocks: List[MatchedBlock], 
                              total_lines_a: int, total_lines_b: int) -> Dict[str, Any]:
        """Generate summary statistics for matched blocks."""
        matched_a = sum(b.a_end - b.a_start for b in blocks)
        matched_b = sum(b.b_end - b.b_start for b in blocks)
        
        return {
            'total_blocks': len(blocks),
            'matched_lines_a': matched_a,
            'matched_lines_b': matched_b,
            'coverage_a': round(matched_a / max(total_lines_a, 1), 3),
            'coverage_b': round(matched_b / max(total_lines_b, 1), 3),
            'blocks': [
                {
                    'a_start': b.a_start, 'a_end': b.a_end,
                    'b_start': b.b_start, 'b_end': b.b_end,
                    'type': b.match_type, 'confidence': b.confidence,
                }
                for b in blocks
            ]
        }