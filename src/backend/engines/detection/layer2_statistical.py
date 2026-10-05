"""Layer 2: Statistical Detection - light paraphrase and structural reordering.

Catches "rewritten but structurally similar" code without semantic interpretation.

Engines:
  - graph:          Control-flow graph similarity (execution structure)
  - logic_flow:     Control/operator SEQUENCE similarity
  - stylometry:     Writing style closeness (informational)
  - sentence_sim:   Size/shape similarity (informational)

Fixes that matter for verdicts:
- ``logic_flow`` was the Jaccard similarity of the SETS of control/operator token kinds. That
  vocabulary has about 50 members, so two unrelated programs that use the same constructs scored
  0.8-1.0, and a value >= 0.95 meant TRUE ("strong structural equivalence"). It is now a
  multiset Dice over 4-grams of the token SEQUENCE, scaled down for short token streams, and a
  pre-computed ``logic_flow`` engine score is used when supplied.
- Comments and strings no longer contribute tokens ("# if we loop" counted as ``if`` and ``for``).
- Stylometric distance compares ratios by difference and sizes by relative difference
  (everything used to be divided by max(value, 1.0), which made sizes look similar).
- ``control_flow_match`` / ``data_flow_match`` were INVENTED as ``0.8 * graph`` and ``0.6 * graph``;
  they are now reported only when the engine supplies them.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ._text import first_score, tokens

logger = logging.getLogger(__name__)

NGRAM = 4
#: Token streams shorter than this are scaled down (little structure to compare).
FULL_RELIABILITY_TOKENS = 30


@dataclass
class Layer2Result:
    """Structured output from the statistical detection layer."""

    graph_similarity: float = 0.0
    logic_flow_similarity: float = 0.0
    stylometric_distance: float = 1.0  # 0 = identical style, 1 = very different
    sentence_structure_similarity: float = 0.0
    control_flow_match: float = 0.0
    data_flow_match: float = 0.0
    engine_scores: dict[str, float] = field(default_factory=dict)
    #: engines whose score was supplied by the caller (not available -> absent from the dict)
    available_engines: list[str] = field(default_factory=list)

    #: Only these signals are evidence of copying. Style and size similarity are informational.
    EVIDENCE_KEYS = ("graph", "logic_flow")

    @property
    def max_signal(self) -> float:
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float))]
        return max(values) if values else 0.0

    @property
    def evidence_signal(self) -> float:
        """Strongest signal that is actually evidence of copying (graph / logic flow)."""
        return max((self.engine_scores.get(k, 0.0) for k in self.EVIDENCE_KEYS), default=0.0)

    @property
    def mean_signal(self) -> float:
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float)) and v > 0]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_similarity": round(self.graph_similarity, 4),
            "logic_flow_similarity": round(self.logic_flow_similarity, 4),
            "stylometric_distance": round(self.stylometric_distance, 4),
            "sentence_structure_similarity": round(self.sentence_structure_similarity, 4),
            "control_flow_match": round(self.control_flow_match, 4),
            "data_flow_match": round(self.data_flow_match, 4),
            "evidence_signal": round(self.evidence_signal, 4),
            "max_signal": round(self.max_signal, 4),
            "mean_signal": round(self.mean_signal, 4),
            "engine_scores": {k: round(v, 4) for k, v in self.engine_scores.items()},
        }


# Control-flow keywords that define program structure
CONTROL_KEYWORDS = {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "break", "continue",
    "return", "throw", "try", "catch", "finally", "with", "match", "except", "raise", "yield",
}  # fmt: skip

# Operator types for logic flow
OPERATOR_PATTERNS = {
    "==", "!=", "<=", ">=", "<", ">", "&&", "||", "!", "&", "|", "^", "~", "+", "-", "*", "/",
    "%", "+=", "-=", "*=", "/=", "%=", "++", "--",
}  # fmt: skip
_SYNTAX = {"{", "}", "(", ")", "[", "]", ";", ":"}


def _extract_logic_flow_tokens(code: str, language: str | None = None) -> list[str]:
    """Control-flow, operator and syntax tokens in order, ignoring identifiers, comments, strings."""
    result = []
    for kind, text in tokens(code, language):
        if kind == "ident" and text in CONTROL_KEYWORDS:
            result.append(f"CTRL:{text}")
        elif kind == "op" and text in OPERATOR_PATTERNS:
            result.append(f"OP:{text}")
        elif kind == "op" and text in _SYNTAX:
            result.append(f"SYN:{text}")
        elif kind == "number":
            result.append("NUM")
    return result


def _ngram_dice(seq_a: list[str], seq_b: list[str], n: int = NGRAM) -> float:
    """Multiset Dice coefficient of the n-grams of two sequences."""
    if len(seq_a) < n or len(seq_b) < n:
        return 0.0
    grams_a = Counter(tuple(seq_a[i : i + n]) for i in range(len(seq_a) - n + 1))
    grams_b = Counter(tuple(seq_b[i : i + n]) for i in range(len(seq_b) - n + 1))
    shared = sum((grams_a & grams_b).values())
    return 2.0 * shared / (sum(grams_a.values()) + sum(grams_b.values()))


def _logic_flow_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Sequence-based logic-flow similarity in [0, 1], scaled down for short programs."""
    if not tokens_a or not tokens_b:
        return 0.0
    reliability = min(1.0, min(len(tokens_a), len(tokens_b)) / FULL_RELIABILITY_TOKENS)
    return _ngram_dice(tokens_a, tokens_b) * reliability


def _compute_stylometric_features(code: str) -> dict[str, float]:
    """Extract writing-style features from source code."""
    lines = code.split("\n") if code else []
    if not lines:
        return {"avg_line_length": 0.0, "indent_ratio": 0.0, "comment_ratio": 0.0}

    total_chars = len(code)
    indent_count = sum(1 for line in lines if line.startswith((" ", "\t")))
    comment_lines = sum(1 for line in lines if line.strip().startswith(("//", "#", "/*", "*")))
    blank_lines = sum(1 for line in lines if not line.strip())

    return {
        "avg_line_length": round(total_chars / max(1, len(lines)), 2),
        "indent_ratio": round(indent_count / max(1, len(lines)), 4),
        "comment_ratio": round(comment_lines / max(1, len(lines)), 4),
        "blank_line_ratio": round(blank_lines / max(1, len(lines)), 4),
        "line_count": len(lines),
    }


_RATIO_FEATURES = {"indent_ratio", "comment_ratio", "blank_line_ratio"}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    union = len(set_a | set_b)
    return len(set_a & set_b) / union if union > 0 else 0.0


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    all_keys = set(vec_a) | set(vec_b)
    dot = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in all_keys)
    norm_a = sum(v * v for v in vec_a.values()) ** 0.5
    norm_b = sum(v * v for v in vec_b.values()) ** 0.5
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0


_FUNC_LINE = re.compile(r"^\s*(def |function |func |sub |fn )")
_CLASS_LINE = re.compile(r"^\s*(class |struct |interface )")


class Layer2Statistical:
    """Statistical detection layer - catches light paraphrase and reordering."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: dict[str, float] | None = None,
        engine_details: dict[str, Any] | None = None,
        language: str | None = None,
    ) -> Layer2Result:
        """Run statistical detection on a pair of code files.

        ``engine_scores`` may contain ``graph`` (or ``execution_cfg``) and ``logic_flow``;
        a supplied ``logic_flow`` is used instead of the built-in estimate.
        """
        scores = engine_scores or {}
        details = engine_details or {}
        has_code = bool(code_a and code_b and code_a.strip() and code_b.strip())

        graph_supplied = first_score(scores, "graph", "execution_cfg")
        graph_score = graph_supplied or 0.0

        flow_supplied = first_score(scores, "logic_flow")
        if flow_supplied is not None:
            logic_flow = flow_supplied
        elif has_code:
            logic_flow = _logic_flow_similarity(
                _extract_logic_flow_tokens(code_a, language), _extract_logic_flow_tokens(code_b, language)
            )
        else:
            logic_flow = 0.0

        # --- Stylometry (informational) ---
        style_a, style_b = _compute_stylometric_features(code_a), _compute_stylometric_features(code_b)
        distances = []
        for key, value_a in style_a.items():
            if key not in style_b:
                continue
            value_b = style_b[key]
            if key in _RATIO_FEATURES:
                distances.append(min(1.0, abs(value_a - value_b)))
            else:
                distances.append(abs(value_a - value_b) / max(value_a, value_b, 1e-9))
        stylometric_distance = sum(distances) / len(distances) if (has_code and distances) else 1.0

        # --- Size / shape similarity (informational) ---
        lines_a = code_a.split("\n") if code_a else []
        lines_b = code_b.split("\n") if code_b else []
        profile_a = {
            "total_lines": len(lines_a),
            "func_count": sum(1 for line in lines_a if _FUNC_LINE.match(line)),
            "class_count": sum(1 for line in lines_a if _CLASS_LINE.match(line)),
            "avg_line_length": style_a.get("avg_line_length", 0),
        }
        profile_b = {
            "total_lines": len(lines_b),
            "func_count": sum(1 for line in lines_b if _FUNC_LINE.match(line)),
            "class_count": sum(1 for line in lines_b if _CLASS_LINE.match(line)),
            "avg_line_length": style_b.get("avg_line_length", 0),
        }
        ratios = [
            min(profile_a[k], profile_b[k]) / max(profile_a[k], profile_b[k])
            for k in profile_a
            if max(profile_a[k], profile_b[k]) > 0
        ]
        sentence_structure_sim = sum(ratios) / len(ratios) if (has_code and ratios) else 0.0

        # Reported only when the graph engine supplies them (they used to be 0.8*graph / 0.6*graph)
        control_flow_match = first_score(details, "control_flow_match") or 0.0
        data_flow_match = first_score(details, "data_flow_match") or 0.0

        engine_scores_out = {
            "graph": graph_score,
            "logic_flow": logic_flow,
            "stylometry": 1.0 - stylometric_distance,
            "sentence_structure": sentence_structure_sim,
        }
        available = ["logic_flow"] if has_code or flow_supplied is not None else []
        if graph_supplied is not None:
            available.append("graph")

        return Layer2Result(
            graph_similarity=round(graph_score, 4),
            logic_flow_similarity=round(logic_flow, 4),
            stylometric_distance=round(stylometric_distance, 4),
            sentence_structure_similarity=round(sentence_structure_sim, 4),
            control_flow_match=round(control_flow_match, 4),
            data_flow_match=round(data_flow_match, 4),
            engine_scores=engine_scores_out,
            available_engines=available,
        )
