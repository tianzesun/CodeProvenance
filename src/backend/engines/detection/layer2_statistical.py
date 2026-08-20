"""Layer 2: Statistical Detection — Light paraphrase and structural reordering.

Catches "rewritten but structurally similar" code that deterministic engines
may miss, without resorting to semantic interpretation.

Engines:
  - graph:          Control-flow graph similarity (execution structure)
  - logic_flow:     Logic flow token patterns (control + operator sequences)
  - stylometry:     Writing style features (indentation, naming, spacing)
  - sentence_sim:   Line/sentence-level structural similarity
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Layer2Result:
    """Structured output from the statistical detection layer."""

    graph_similarity: float = 0.0
    logic_flow_similarity: float = 0.0
    stylometric_distance: float = 1.0  # 0 = identical style, 1 = very different
    sentence_structure_similarity: float = 0.0
    control_flow_match: float = 0.0
    data_flow_match: float = 0.0
    engine_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def max_signal(self) -> float:
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float))]
        return max(values) if values else 0.0

    @property
    def mean_signal(self) -> float:
        values = [
            v
            for v in self.engine_scores.values()
            if isinstance(v, (int, float)) and v > 0
        ]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_similarity": round(self.graph_similarity, 4),
            "logic_flow_similarity": round(self.logic_flow_similarity, 4),
            "stylometric_distance": round(self.stylometric_distance, 4),
            "sentence_structure_similarity": round(
                self.sentence_structure_similarity, 4
            ),
            "control_flow_match": round(self.control_flow_match, 4),
            "data_flow_match": round(self.data_flow_match, 4),
            "max_signal": round(self.max_signal, 4),
            "mean_signal": round(self.mean_signal, 4),
            "engine_scores": {k: round(v, 4) for k, v in self.engine_scores.items()},
        }


# Control-flow keywords that define program structure
CONTROL_KEYWORDS = {
    "if",
    "else",
    "elif",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "return",
    "throw",
    "try",
    "catch",
    "finally",
    "with",
    "match",
}

# Operator types for logic flow
OPERATOR_PATTERNS = {
    "==",
    "!=",
    "<=",
    ">=",
    "<",
    ">",
    "&&",
    "||",
    "!",
    "&",
    "|",
    "^",
    "~",
    "+",
    "-",
    "*",
    "/",
    "%",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "++",
    "--",
}


def _extract_logic_flow_tokens(code: str) -> List[str]:
    """Extract control-flow and operator tokens from code, ignoring identifiers."""
    tokens = re.findall(
        r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|\S",
        code,
    )
    result = []
    for token in tokens:
        if token in CONTROL_KEYWORDS:
            result.append(f"CTRL:{token}")
        elif token in OPERATOR_PATTERNS:
            result.append(f"OP:{token}")
        elif token in ("{", "}", "(", ")", "[", "]", ";", ":"):
            result.append(f"SYN:{token}")
        elif re.fullmatch(r"\d+", token):
            result.append("NUM")
    return result


def _compute_stylometric_features(code: str) -> Dict[str, float]:
    """Extract writing-style features from source code."""
    lines = code.split("\n") if code else []
    if not lines:
        return {"avg_line_length": 0.0, "indent_ratio": 0.0, "comment_ratio": 0.0}

    total_chars = len(code)
    indent_count = sum(1 for line in lines if line.startswith((" ", "\t")))
    comment_lines = sum(
        1 for line in lines if line.strip().startswith(("//", "#", "/*", "*"))
    )
    blank_lines = sum(1 for line in lines if not line.strip())

    return {
        "avg_line_length": round(total_chars / max(1, len(lines)), 2),
        "indent_ratio": round(indent_count / max(1, len(lines)), 4),
        "comment_ratio": round(comment_lines / max(1, len(lines)), 4),
        "blank_line_ratio": round(blank_lines / max(1, len(lines)), 4),
        "line_count": len(lines),
    }


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    union = len(set_a | set_b)
    return len(set_a & set_b) / union if union > 0 else 0.0


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    all_keys = set(vec_a) | set(vec_b)
    dot = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in all_keys)
    norm_a = sum(v * v for v in vec_a.values()) ** 0.5
    norm_b = sum(v * v for v in vec_b.values()) ** 0.5
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0


class Layer2Statistical:
    """Statistical detection layer — catches light paraphrase and reordering.

    Uses graph similarity, logic flow patterns, and stylometric features
    to detect rewritten code without relying on semantic interpretation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._graph_threshold = float(self.config.get("graph_threshold", 0.25))
        self._logic_flow_threshold = float(
            self.config.get("logic_flow_threshold", 0.20)
        )

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Optional[Dict[str, float]] = None,
        engine_details: Optional[Dict[str, Any]] = None,
    ) -> Layer2Result:
        """Run statistical detection on a pair of code files.

        Args:
            code_a: Source code of first file.
            code_b: Source code of second file.
            engine_scores: Pre-computed engine scores (keys: graph, logic_flow, etc.)
            engine_details: Optional full engine output for rich evidence.

        Returns:
            Layer2Result with statistical signals.
        """
        scores = engine_scores or {}
        details = engine_details or {}

        # --- Graph similarity ---
        graph_score = float(scores.get("graph", scores.get("execution_cfg", 0.0)))

        # --- Logic flow similarity ---
        logic_tokens_a = _extract_logic_flow_tokens(code_a)
        logic_tokens_b = _extract_logic_flow_tokens(code_b)

        if logic_tokens_a and logic_tokens_b:
            set_a = set(logic_tokens_a)
            set_b = set(logic_tokens_b)
            logic_flow_similarity = _jaccard_similarity(set_a, set_b)

            # Also compute sequence-based logic flow
            counter_a = Counter(logic_tokens_a)
            counter_b = Counter(logic_tokens_b)

            # Cosine similarity of logic flow n-gram profile
            logic_flow_cosine = _cosine_similarity(
                {k: float(v) for k, v in counter_a.items()},
                {k: float(v) for k, v in counter_b.items()},
            )
            logic_flow_final = max(logic_flow_similarity, logic_flow_cosine * 0.7)
        else:
            logic_flow_final = 0.0

        # --- Stylometric features ---
        style_a = _compute_stylometric_features(code_a)
        style_b = _compute_stylometric_features(code_b)

        # Compute stylometric distance (0 = identical, 1 = very different)
        style_distances = []
        for key in style_a:
            if key in style_b:
                max_val = max(style_a[key], style_b[key], 1.0)
                style_distances.append(abs(style_a[key] - style_b[key]) / max_val)
        stylometric_distance = sum(style_distances) / max(1, len(style_distances))
        # Normalize: same style → 0.0, different → 1.0

        # --- Sentence structure similarity ---
        # Compare line-bucket profiles (number of lines, function count, etc.)
        lines_a = code_a.split("\n") if code_a else []
        lines_b = code_b.split("\n") if code_b else []

        func_count_a = sum(
            1
            for line in lines_a
            if re.match(
                r"^\s*(def |function |func |sub |public |private |protected )", line
            )
        )
        func_count_b = sum(
            1
            for line in lines_b
            if re.match(
                r"^\s*(def |function |func |sub |public |private |protected )", line
            )
        )
        class_count_a = sum(
            1 for line in lines_a if re.match(r"^\s*(class |struct |interface )", line)
        )
        class_count_b = sum(
            1 for line in lines_b if re.match(r"^\s*(class |struct |interface )", line)
        )

        # Structural profile vector
        profile_a = {
            "total_lines": len(lines_a),
            "func_count": func_count_a,
            "class_count": class_count_a,
            "avg_line_length": style_a.get("avg_line_length", 0),
        }
        profile_b = {
            "total_lines": len(lines_b),
            "func_count": func_count_b,
            "class_count": class_count_b,
            "avg_line_length": style_b.get("avg_line_length", 0),
        }

        # Convert to [0,1] similarity based on ratio closeness
        struct_similarities = []
        for key in profile_a:
            if key in profile_b and max(profile_a[key], profile_b[key]) > 0:
                ratio = min(profile_a[key], profile_b[key]) / max(
                    profile_a[key], profile_b[key]
                )
                struct_similarities.append(ratio)
        sentence_structure_sim = sum(struct_similarities) / max(
            1, len(struct_similarities)
        )

        # --- Control/data flow match from graph engine ---
        control_flow_match = float(details.get("control_flow_match", graph_score * 0.8))
        data_flow_match = float(details.get("data_flow_match", graph_score * 0.6))

        engine_scores_out = {
            "graph": graph_score,
            "logic_flow": logic_flow_final,
            "stylometry": 1.0 - stylometric_distance,
            "sentence_structure": sentence_structure_sim,
        }

        return Layer2Result(
            graph_similarity=round(graph_score, 4),
            logic_flow_similarity=round(logic_flow_final, 4),
            stylometric_distance=round(stylometric_distance, 4),
            sentence_structure_similarity=round(sentence_structure_sim, 4),
            control_flow_match=round(control_flow_match, 4),
            data_flow_match=round(data_flow_match, 4),
            engine_scores=engine_scores_out,
        )
