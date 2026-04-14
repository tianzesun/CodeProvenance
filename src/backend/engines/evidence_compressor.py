"""
Evidence Compression Layer - selects minimal proof set for explainable reports.

Instead of showing 200+ matches, extracts only the top 3-8 most explanatory
evidence bundles to keep reports concise and actionable.
"""
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class EvidenceBundle:
    """Single evidence bundle combining GST and AST support."""
    gst_block: Dict[str, Any]
    ast_support: List[Tuple[str, str]]
    score: float
    confidence: float
    explanation: str


class EvidenceCompressor:
    """
    Compresses full evidence into minimal proof set.
    
    Selects only the strongest, most explanatory evidence bundles
    to keep reports concise and actionable.
    """
    
    def __init__(self, max_bundles: int = 5):
        self.max_bundles = max_bundles
    
    def compress(self,
                 ast_matches: List[Tuple[str, str]],
                 gst_blocks: List[Dict[str, Any]],
                 engine_scores: Dict[str, float]) -> List[EvidenceBundle]:
        """
        Compress raw evidence into minimal proof set.
        
        Args:
            ast_matches: List of (a_node, b_node) AST matches
            gst_blocks: List of GST match blocks
            engine_scores: Dictionary of engine scores
        
        Returns:
            List of top evidence bundles (max 5)
        """
        if not gst_blocks and not ast_matches:
            return []
        
        bundles = []
        
        # Build evidence bundles by linking GST blocks to AST support
        for gst in gst_blocks:
            # Find AST matches that overlap with this GST block
            support = self._find_ast_support(gst, ast_matches)
            
            # Calculate bundle score: GST strength * AST support
            gst_strength = gst.get("match_strength", gst.get("match_percent", 0.0) / 100.0)
            support_weight = min(1.0, len(support) / 3.0)
            
            bundle_score = gst_strength * (0.6 + 0.4 * support_weight)
            
            # Generate explanation
            explanation = self._generate_explanation(gst, support, gst_strength)
            
            bundles.append(EvidenceBundle(
                gst_block=gst,
                ast_support=support,
                score=bundle_score,
                confidence=gst_strength,
                explanation=explanation
            ))
        
        # If no GST blocks but strong AST matches, create virtual bundles
        if not bundles and engine_scores.get("ast", 0.0) > 0.7:
            for i, (a_node, b_node) in enumerate(ast_matches[:3]):
                bundles.append(EvidenceBundle(
                    gst_block={},
                    ast_support=[(a_node, b_node)],
                    score=0.7,
                    confidence=0.7,
                    explanation=f"Structural match: {a_node} ↔ {b_node}"
                ))
        
        # Sort by score descending and take top N
        bundles.sort(key=lambda x: x.score, reverse=True)
        selected = bundles[:self.max_bundles]
        
        # Deduplicate similar bundles
        return self._deduplicate(selected)
    
    def _find_ast_support(self,
                          gst_block: Dict[str, Any],
                          ast_matches: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Find AST matches that provide supporting evidence for a GST block."""
        support = []
        
        # Simple heuristic: AST matches containing keywords from GST snippet
        snippet = gst_block.get("a_snippet", "").lower()
        
        for a_node, b_node in ast_matches:
            node_type = a_node.split(":")[0].lower()
            
            # Match common construct types
            if ("function" in node_type and "def" in snippet) or \
               ("call" in node_type and "(" in snippet) or \
               ("loop" in node_type and ("for" in snippet or "while" in snippet)) or \
               ("if" in node_type and "if" in snippet) or \
               ("return" in node_type and "return" in snippet):
                support.append((a_node, b_node))
        
        return support[:3]  # Max 3 AST matches per bundle
    
    def _generate_explanation(self,
                              gst: Dict[str, Any],
                              support: List[Tuple[str, str]],
                              strength: float) -> str:
        """Generate human-readable explanation for evidence bundle."""
        if strength >= 0.95:
            quality = "Exact match"
        elif strength >= 0.8:
            quality = "Strong match"
        elif strength >= 0.6:
            quality = "Partial match"
        else:
            quality = "Weak match"
        
        parts = [f"{quality}"]
        
        if gst.get("length", 0) > 0:
            parts.append(f"({gst['length']} tokens)")
        
        if support:
            parts.append(f"- supported by {len(support)} structural matches")
        
        return " ".join(parts)
    
    def _deduplicate(self, bundles: List[EvidenceBundle]) -> List[EvidenceBundle]:
        """Remove similar overlapping bundles."""
        seen = set()
        unique = []
        
        for bundle in bundles:
            # Create signature for deduplication
            sig = (
                bundle.gst_block.get("a_start", -1),
                bundle.gst_block.get("b_start", -1),
                len(bundle.ast_support)
            )
            
            if sig not in seen:
                seen.add(sig)
                unique.append(bundle)
        
        return unique
    
    def format_report(self, bundles: List[EvidenceBundle]) -> str:
        """Format compressed evidence into concise human-readable report."""
        if not bundles:
            return "No strong evidence detected."
        
        lines = ["📋 EVIDENCE SUMMARY", "=" * 40, ""]
        
        for i, bundle in enumerate(bundles, 1):
            lines.append(f"Bundle {i}: {bundle.explanation}")
            lines.append(f"  Score: {bundle.score:.2f} | Confidence: {bundle.confidence:.1%}")
            
            if bundle.gst_block:
                a_start = bundle.gst_block.get("a_start", 0)
                a_end = bundle.gst_block.get("a_end", 0)
                lines.append(f"  Code: lines {a_start}-{a_end}")
                if "a_snippet" in bundle.gst_block:
                    lines.append(f"  '{bundle.gst_block['a_snippet']}'")
            
            if bundle.ast_support:
                lines.append("  Structural support:")
                for a, b in bundle.ast_support[:2]:
                    lines.append(f"    ✔ {a} ↔ {b}")
            
            lines.append("")
        
        return "\n".join(lines)


class CompressedReportGenerator:
    """
    Full pipeline generating compressed explainable reports.
    
    Combines:
    1. Full engine scoring
    2. Conflict resolution
    3. Evidence compression
    4. Calibrated scoring
    """
    
    def __init__(self):
        from src.backend.engines.report_generator import ReportGenerator
        from src.backend.engines.conflict_resolver import ConflictResolutionPipeline
        from src.backend.engines.score_calibration import CalibratedScoringPipeline
        
        self.base_report = ReportGenerator()
        self.conflict_resolver = ConflictResolutionPipeline()
        self.scorer = CalibratedScoringPipeline()
        self.compressor = EvidenceCompressor(max_bundles=5)
    
    def generate(self, code_a: str, code_b: str) -> Dict[str, Any]:
        """Generate full compressed report."""
        # Base analysis
        score_result = self.scorer.score(code_a, code_b)
        conflict_result = self.conflict_resolver.analyze(code_a, code_b)
        full_report = self.base_report.generate_report(
            code_a, code_b,
            score_result.get("engine_scores", {}),
            score_result["calibrated_score"]
        )
        
        # Compress evidence
        evidence_bundles = self.compressor.compress(
            full_report.ast_matches,
            full_report.gst_blocks,
            score_result.get("engine_scores", {})
        )
        
        return {
            "score": score_result["calibrated_score"],
            "confidence": conflict_result["confidence_value"],
            "confidence_label": conflict_result["confidence"],
            "agreement": conflict_result["agreement"],
            "detected_strategies": full_report.detected_strategies,
            "evidence_bundles": [
                {
                    "score": round(b.score, 2),
                    "confidence": round(b.confidence, 2),
                    "explanation": b.explanation,
                    "code_range": [b.gst_block.get("a_start", 0), b.gst_block.get("a_end", 0)],
                    "snippet": b.gst_block.get("a_snippet", ""),
                    "structural_support": [{"a": a, "b": b} for a, b in b.ast_support]
                }
                for b in evidence_bundles
            ],
            "recommended_action": conflict_result["recommended_action"],
            "verdict": full_report.final_verdict
        }
