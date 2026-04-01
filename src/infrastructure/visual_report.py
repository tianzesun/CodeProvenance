"""
Visual Report Generator – Teacher-friendly plagiarism reports.

Produces:
1. Highlighted similar code segments (line-by-line diff)
2. Plagiarism type hints ("Variable Renaming + Control Flow Equivalence")
3. AI probability with key stylometry contribution features
4. Summary score with HIGH/MEDIUM/LOW/SUSPICIOUS risk levels
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import difflib
import re
from collections import defaultdict


# =============================================================================
# Plagiarism Type Classifier
# =============================================================================

@dataclass
class PlagiarismType:
    """Detected plagiarism type with evidence."""
    type_code: str  # T1, T2, T3, T4, NONE
    type_name: str
    confidence: float
    evidence: List[str] = field(default_factory=list)


PLAGIARISM_TYPES = {
    "T1": "Identical Copy",
    "T2": "Variable/Function Renaming",
    "T3": "Restructured Code",
    "T4": "Semantic Clone",
    "T5": "Independent Implementation",
}


class PlagiarismTypeClassifier:
    """
    Detects the type of plagiarism based on similarity scores.

    Logic:
    - T1 (Identical): token similarity > 0.95 AND AST similarity > 0.95
    - T2 (Renaming): AST similarity > 0.85 AND token similarity < 0.95
    - T3 (Restructured): CFG similarity > 0.7 AND AST similarity 0.5-0.85
    - T4 (Semantic): AST similarity > 0.4 AND token similarity < 0.5
    - T5 (Independent): all similarities < 0.4
    """

    def classify(self, scores: Dict[str, float]) -> PlagiarismType:
        """
        Classify plagiarism type from similarity scores.

        Args:
            scores: {
                "token_sim": float,     # Token-level similarity
                "ast_sim": float,       # AST structure similarity
                "cfg_sim": float,       # Control flow similarity
                "pdg_sim": float,       # Dependency graph similarity
                "overall_sim": float,   # Overall combined similarity
            }

        Returns:
            PlagiarismType with classification result
        """
        token_sim = scores.get("token_sim", scores.get("similarity", 0))
        ast_sim = scores.get("ast_sim", 0)
        cfg_sim = scores.get("cfg_sim", 0)
        pdg_sim = scores.get("pdg_sim", 0)
        overall_sim = scores.get("overall_sim", scores.get("similarity", 0))

        # T1: Identical Copy (near-exact match)
        if token_sim > 0.90 and ast_sim > 0.95:
            evidence = [
                "Code structure is nearly identical (AST > 95%)",
                "Token-level match is very high",
                "Likely direct copy with minimal changes",
            ]
            return PlagiarismType(
                type_code="T1", type_name="Identical Copy",
                confidence=min(1.0, (token_sim + ast_sim) / 2),
                evidence=evidence,
            )

        # T2: Variable/Function Renaming
        if ast_sim > 0.80 and token_sim < 0.90:
            token_delta = ast_sim - token_sim
            evidence = [
                f"AST structure highly similar ({ast_sim:.0%}) despite renamed identifiers",
                f"Token similarity ({token_sim:.0%}) lower due to name changes",
                f"Name difference of {token_delta:.0%} suggests deliberate obfuscation",
            ]
            if cfg_sim > 0.5:
                evidence.append(f"Control flow is equivalent (CFG {cfg_sim:.0%})")
            return PlagiarismType(
                type_code="T2", type_name="Variable/Function Renaming",
                confidence=min(1.0, ast_sim),
                evidence=evidence,
            )

        # T3: Restructured Code
        if cfg_sim > 0.6 and ast_sim > 0.35:
            evidence = [
                f"Control flow graphs are similar ({cfg_sim:.0%})",
                f"AST structure partially matches ({ast_sim:.0%})",
                "Loop/recursion patterns are equivalent",
            ]
            if token_sim < 0.5:
                evidence.append(f"Token similarity low ({token_sim:.0%}) despite structural match")
            if pdg_sim > 0.3:
                evidence.append(f"Data dependencies are preserved (PDG {pdg_sim:.0%})")
            return PlagiarismType(
                type_code="T3", type_name="Restructured Code",
                confidence=min(1.0, (cfg_sim + ast_sim) / 2),
                evidence=evidence,
            )

        # T4: Semantic Clone
        if ast_sim > 0.3 and overall_sim > 0.25:
            evidence = [
                f"AST structure shows similarity ({ast_sim:.0%})",
                "Algorithm logic appears equivalent",
                "Different implementation but same semantics",
            ]
            return PlagiarismType(
                type_code="T4", type_name="Semantic Clone",
                confidence=overall_sim,
                evidence=evidence,
            )

        # T5: Independent Implementation
        default_evidence = [
            f"Overall similarity is low ({overall_sim:.0%})",
            f"AST structure differs significantly ({ast_sim:.0%})" if ast_sim < 0.4 else "Some structural overlap detected",
            "Likely independently written",
        ]
        return PlagiarismType(
            type_code="T5", type_name="Independent Implementation",
            confidence=1.0 - overall_sim,
            evidence=default_evidence,
        )


# =============================================================================
# Code Highlighter / Diff Generator
# =============================================================================

@dataclass
class SimilarBlock:
    """A block of similar code between two files."""
    line_start_a: int
    line_end_a: int
    line_start_b: int
    line_end_b: int
    similarity: float
    similarity_type: str  # "exact", "near-exact", "structural"
    code_a_lines: List[str] = field(default_factory=list)
    code_b_lines: List[str] = field(default_factory=list)
    diff_hunks: List[str] = field(default_factory=list)


class CodeDiffGenerator:
    """
    Generates highlighted similar code segments for teacher review.

    Uses:
    1. Token-level matching (exact/near matches)
    2.