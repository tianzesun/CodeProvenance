"""Layer 1: Deterministic Detection — "Hard" plagiarism (exact copy, renamed, structural).

High-precision layer that never relies on semantic interpretation.
Every signal has a clear, auditable provenance.

Engines:
  - token:          Token-sequence overlap (Jaccard, LCS)
  - winnowing:      Local k-gram fingerprinting (MOSS-style)
  - ngram:          N-gram sequence similarity
  - ast:            AST subtree matching (structural clones)
  - static_rules:   Pattern-based rule violations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Layer1Result:
    """Structured output from the deterministic detection layer."""

    exact_match_score: float = 0.0
    structural_similarity: float = 0.0
    token_overlap: float = 0.0
    winnowing_overlap: float = 0.0
    ngram_overlap: float = 0.0
    ast_subtree_overlap: float = 0.0
    ast_node_match: float = 0.0
    rule_violation_flags: List[str] = field(default_factory=list)
    rule_violation_count: int = 0
    matching_line_count: int = 0
    total_line_count_a: int = 0
    total_line_count_b: int = 0
    has_exact_file_match: bool = False
    engine_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def max_signal(self) -> float:
        """Highest single signal in this layer."""
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float))]
        return max(values) if values else 0.0

    @property
    def mean_signal(self) -> float:
        """Mean of non-zero signals in this layer."""
        values = [
            v
            for v in self.engine_scores.values()
            if isinstance(v, (int, float)) and v > 0
        ]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exact_match_score": round(self.exact_match_score, 4),
            "structural_similarity": round(self.structural_similarity, 4),
            "token_overlap": round(self.token_overlap, 4),
            "winnowing_overlap": round(self.winnowing_overlap, 4),
            "ngram_overlap": round(self.ngram_overlap, 4),
            "ast_subtree_overlap": round(self.ast_subtree_overlap, 4),
            "ast_node_match": round(self.ast_node_match, 4),
            "rule_violation_count": self.rule_violation_count,
            "rule_violation_flags": self.rule_violation_flags,
            "matching_line_count": self.matching_line_count,
            "has_exact_file_match": self.has_exact_file_match,
            "max_signal": round(self.max_signal, 4),
            "mean_signal": round(self.mean_signal, 4),
            "engine_scores": {k: round(v, 4) for k, v in self.engine_scores.items()},
        }


class Layer1Deterministic:
    """Deterministic detection layer using existing engine infrastructure.

    Wraps the existing token, winnowing, n-gram, AST, and static rules
    similarity engines into a single layer with interpretable outputs.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._ast_threshold = float(self.config.get("ast_subtree_threshold", 0.30))
        self._token_threshold = float(self.config.get("token_overlap_threshold", 0.25))
        self._winnowing_threshold = float(self.config.get("winnowing_threshold", 0.20))
        self._exact_match_threshold = float(
            self.config.get("exact_match_threshold", 0.85)
        )

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Optional[Dict[str, float]] = None,
        engine_details: Optional[Dict[str, Any]] = None,
    ) -> Layer1Result:
        """Run deterministic detection on a pair of code files.

        Args:
            code_a: Source code of first file.
            code_b: Source code of second file.
            engine_scores: Pre-computed engine scores dict (keys: token, winnowing,
                ngram, ast, static_rules).
            engine_details: Optional full engine output for rich evidence extraction.

        Returns:
            Layer1Result with deterministic signals.
        """
        scores = engine_scores or {}
        details = engine_details or {}

        # --- Token overlap ---
        token_score = float(scores.get("token", scores.get("fingerprint", 0.0)))
        token_written = max(0.0, token_score - 0.12) / 0.88  # baseline-corrected

        # --- Winnowing overlap ---
        winnowing_score = float(scores.get("winnowing", 0.0))
        winnowing_written = (
            max(0.0, winnowing_score - 0.16) / 0.84
        )  # baseline-corrected

        # --- N-gram overlap ---
        ngram_score = float(scores.get("ngram", scores.get("gst", 0.0)))

        # --- AST subtree overlap ---
        ast_score = float(scores.get("ast", 0.0))

        # --- Static rules ---
        static_rules_score = float(scores.get("static_rules", 0.0))
        rule_violations = details.get("rule_violations", [])
        if isinstance(rule_violations, list):
            rule_violation_flags = [str(v) for v in rule_violations]
        elif isinstance(rule_violations, str):
            rule_violation_flags = [rule_violations]
        else:
            rule_violation_flags = []

        # --- Exact file match check ---
        a_normalized = code_a.strip() if code_a else ""
        b_normalized = code_b.strip() if code_b else ""
        has_exact_match = (
            (a_normalized == b_normalized) if a_normalized and b_normalized else False
        )
        if has_exact_match:
            exact_match_score = 1.0
        else:
            # Estimate exact-match score from token
            exact_match_score = (
                token_score if token_score > self._exact_match_threshold else 0.0
            )

        # --- Line-level matching (quick approximate) ---
        lines_a = code_a.split("\n") if code_a else []
        lines_b = code_b.split("\n") if code_b else []
        total_a = len(lines_a)
        total_b = len(lines_b)

        set_a = {
            line.strip()
            for line in lines_a
            if line.strip() and not line.strip().startswith(("//", "#", "/*"))
        }
        set_b = {
            line.strip()
            for line in lines_b
            if line.strip() and not line.strip().startswith(("//", "#", "/*"))
        }
        matching_lines = len(set_a & set_b)
        matching_line_count = matching_lines

        # --- Structural similarity (aggregate of structural engines) ---
        # AST is the strongest structural signal
        structural = max(
            ast_score,
            token_written * 0.6,  # token overlap after baseline correction
            winnowing_written * 0.5,
        )

        # --- Build engine_scores dict ---
        engine_scores_out = {
            "token": token_score,
            "winnowing": winnowing_score,
            "ngram": ngram_score,
            "ast": ast_score,
            "static_rules": static_rules_score,
        }

        # --- AST node match (structural AST signal) ---
        ast_node_match = float(details.get("ast_node_match", ast_score))
        ast_subtree = float(details.get("ast_subtree_overlap", ast_score))

        return Layer1Result(
            exact_match_score=round(exact_match_score, 4),
            structural_similarity=round(structural, 4),
            token_overlap=round(token_score, 4),
            winnowing_overlap=round(winnowing_score, 4),
            ngram_overlap=round(ngram_score, 4),
            ast_subtree_overlap=round(ast_subtree, 4),
            ast_node_match=round(ast_node_match, 4),
            rule_violation_flags=rule_violation_flags,
            rule_violation_count=len(rule_violation_flags),
            matching_line_count=matching_line_count,
            total_line_count_a=total_a,
            total_line_count_b=total_b,
            has_exact_file_match=has_exact_match,
            engine_scores=engine_scores_out,
        )
