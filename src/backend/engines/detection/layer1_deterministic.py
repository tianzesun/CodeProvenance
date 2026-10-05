"""Layer 1: Deterministic Detection - "hard" plagiarism (exact copy, renamed, structural).

High-precision layer that never relies on semantic interpretation. Every signal has a clear,
auditable provenance.

Engines:
  - token:          Token-sequence overlap (Jaccard, LCS)
  - winnowing:      Local k-gram fingerprinting (MOSS-style)
  - ngram:          N-gram sequence similarity
  - ast:            AST subtree matching (structural clones)
  - static_rules:   Pattern-based rule violations

Changes: engine scores are read defensively (None / NaN / strings no longer crash or become a
perfect score); "exact match" tolerates line-ending and trailing-whitespace differences; two files
that are both identical to the instructor's starter code are NOT reported as an exact copy; the
matching-line count ignores trivial lines (``}``, ``else:``, ``return``); the baselines are
configurable and the dead thresholds were removed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ._text import first_score, normalize_text

logger = logging.getLogger(__name__)

_COMMENT_PREFIXES = ("//", "#", "/*", "*", "--")
_TRIVIAL_LINE = re.compile(
    r"^(?:[{}()\[\];,:]*|(?:else|try|finally|do|end|begin|pass|break|continue|return|"
    r"break;|continue;|return;|else:|try:|finally:|\}\s*else\s*\{?|\}\s*\)?;?)\s*)$"
)


def _meaningful_lines(code: str) -> set[str]:
    """Stripped, non-comment, non-trivial lines (at least 4 characters)."""
    out: set[str] = set()
    for line in (code or "").splitlines():
        text = line.strip()
        if len(text) < 4 or text.startswith(_COMMENT_PREFIXES) or _TRIVIAL_LINE.match(text):
            continue
        out.add(text)
    return out


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
    rule_violation_flags: list[str] = field(default_factory=list)
    rule_violation_count: int = 0
    matching_line_count: int = 0
    total_line_count_a: int = 0
    total_line_count_b: int = 0
    has_exact_file_match: bool = False
    #: Both files equal the instructor-provided starter code: no evidence of copying.
    identical_to_template: bool = False
    engine_scores: dict[str, float] = field(default_factory=dict)

    @property
    def max_signal(self) -> float:
        """Highest single signal in this layer."""
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float))]
        return max(values) if values else 0.0

    @property
    def mean_signal(self) -> float:
        """Mean of non-zero signals in this layer."""
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float)) and v > 0]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> dict[str, Any]:
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
            "total_line_count_a": self.total_line_count_a,
            "total_line_count_b": self.total_line_count_b,
            "has_exact_file_match": self.has_exact_file_match,
            "identical_to_template": self.identical_to_template,
            "max_signal": round(self.max_signal, 4),
            "mean_signal": round(self.mean_signal, 4),
            "engine_scores": {k: round(v, 4) for k, v in self.engine_scores.items()},
        }


class Layer1Deterministic:
    """Deterministic detection layer using the existing engine infrastructure."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._exact_match_threshold = float(self.config.get("exact_match_threshold", 0.85))
        #: Noise floor of unrelated files (same values as detection_policy.yaml ``baselines``).
        self._token_baseline = min(0.99, max(0.0, float(self.config.get("token_baseline", 0.12))))
        self._winnowing_baseline = min(0.99, max(0.0, float(self.config.get("winnowing_baseline", 0.16))))

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: dict[str, float] | None = None,
        engine_details: dict[str, Any] | None = None,
        template_code: str | None = None,
    ) -> Layer1Result:
        """Run deterministic detection on a pair of code files.

        Args:
            code_a, code_b: Source code of the two files.
            engine_scores: Pre-computed scores (token, winnowing, ngram, ast, static_rules).
            engine_details: Optional full engine output (rule_violations, ast_node_match, ...).
            template_code: Optional instructor starter code. Files that are both identical to it
                are not reported as an exact copy.
        """
        scores = engine_scores or {}
        details = engine_details or {}

        token_score = first_score(scores, "token", "fingerprint") or 0.0
        token_written = max(0.0, token_score - self._token_baseline) / (1.0 - self._token_baseline)
        winnowing_score = first_score(scores, "winnowing") or 0.0
        winnowing_written = max(0.0, winnowing_score - self._winnowing_baseline) / (1.0 - self._winnowing_baseline)
        ngram_score = first_score(scores, "ngram", "gst") or 0.0
        ast_score = first_score(scores, "ast") or 0.0
        static_rules_score = first_score(scores, "static_rules") or 0.0

        rule_violations = details.get("rule_violations", [])
        if isinstance(rule_violations, (list, tuple)):
            rule_violation_flags = [str(v) for v in rule_violations]
        elif isinstance(rule_violations, str):
            rule_violation_flags = [rule_violations]
        else:
            rule_violation_flags = []

        # --- Exact file match (line endings / trailing whitespace do not matter) ---
        norm_a, norm_b = normalize_text(code_a), normalize_text(code_b)
        files_equal = bool(norm_a) and norm_a == norm_b
        identical_to_template = False
        if files_equal and template_code is not None and normalize_text(template_code) == norm_a:
            identical_to_template = True  # untouched starter code: nothing was copied
        has_exact_match = files_equal and not identical_to_template

        if has_exact_match:
            exact_match_score = 1.0
        else:  # estimated from token similarity (documented: not a proof of identity)
            exact_match_score = token_score if token_score > self._exact_match_threshold else 0.0

        lines_a = code_a.split("\n") if code_a else []
        lines_b = code_b.split("\n") if code_b else []
        matching_line_count = len(_meaningful_lines(code_a) & _meaningful_lines(code_b))

        # AST is the strongest structural signal
        structural = max(ast_score, token_written * 0.6, winnowing_written * 0.5)

        engine_scores_out = {
            "token": token_score,
            "winnowing": winnowing_score,
            "ngram": ngram_score,
            "ast": ast_score,
            "static_rules": static_rules_score,
        }
        ast_node_match = first_score(details, "ast_node_match")
        ast_subtree = first_score(details, "ast_subtree_overlap")

        return Layer1Result(
            exact_match_score=round(exact_match_score, 4),
            structural_similarity=round(structural, 4),
            token_overlap=round(token_score, 4),
            winnowing_overlap=round(winnowing_score, 4),
            ngram_overlap=round(ngram_score, 4),
            ast_subtree_overlap=round(ast_score if ast_subtree is None else ast_subtree, 4),
            ast_node_match=round(ast_score if ast_node_match is None else ast_node_match, 4),
            rule_violation_flags=rule_violation_flags,
            rule_violation_count=len(rule_violation_flags),
            matching_line_count=matching_line_count,
            total_line_count_a=len(lines_a),
            total_line_count_b=len(lines_b),
            has_exact_file_match=has_exact_match,
            identical_to_template=identical_to_template,
            engine_scores=engine_scores_out,
        )
