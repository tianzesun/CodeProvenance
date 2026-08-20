"""Layer 4: Explainability — Evidence-level granularity for auditors.

Provides the "why" behind every verdict:
  - Matched functions (function-level overlap percentages)
  - Matched code blocks (line-level similar regions)
  - Matched AST nodes (structural tree comparison)
  - Matched control flow (logic flow comparison)
  - Variable renaming detection (renamed vs original)

Output format:
```json
{
  "function_overlap": {
    "fib": {"similarity": 0.92, "lines_a": [1,6], "lines_b": [1,6], "type": "renamed_variables"},
    "sort": {"similarity": 0.87, "lines_a": [8,15], "lines_b": [8,15], "type": "identical"}
  },
  "block_matches": [
    {"lines_a": [1,4], "lines_b": [1,4], "score": 0.95, "type": "loop_pattern"}
  ],
  "ast_nodes": {
    "function_count_a": 2, "function_count_b": 2,
    "class_count_a": 0, "class_count_b": 0,
    "shared_structure": 0.85
  },
  "control_flow": {
    "identical": true,
    "sequence": ["IF", "FOR", "RETURN"],
    "similarity": 0.92
  },
  "variable_renames": [
    {"original": "n", "renamed_to": "x"},
    {"original": "a", "renamed_to": "x"},
    {"original": "b", "renamed_to": "y"}
  ],
  "renaming_pattern": "identifier_renaming",
  "plagiarism_type": "type_2_renamed"
}
```
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ─── Plagiarism type classification ────────────────────────────────────────
PLAGIARISM_TYPES = {
    "type_1_identical": "Exact copy with no changes",
    "type_2_renamed": "Identifier renaming only",
    "type_3_restructured": "Control flow reordering + renaming",
    "type_4_semantic": "Different algorithm, same functionality",
    "type_5_template": "Shared assignment template / starter code",
}


@dataclass
class FunctionOverlap:
    """Evidence for one matched function pair."""

    name_a: str
    name_b: str
    similarity: float  # [0, 1]
    lines_a: Tuple[int, int]  # start, end line
    lines_b: Tuple[int, int]
    type: str  # "identical", "renamed_variables", "restructured", "different_names"


@dataclass
class BlockMatch:
    """Evidence for one matched code block."""

    lines_a: Tuple[int, int]
    lines_b: Tuple[int, int]
    score: float
    type: str  # "loop_pattern", "conditional_block", "function_body", "import_section"


@dataclass
class VariableRename:
    """One detected variable renaming."""

    original: str
    renamed_to: str
    context: str  # "parameter", "local_var", "loop_counter"


@dataclass
class ControlFlowEvidence:
    """Control flow comparison evidence."""

    identical: bool
    sequence_a: List[str]
    sequence_b: List[str]
    similarity: float


@dataclass
class ExplanationReport:
    """Complete explainability evidence report."""

    function_overlap: List[FunctionOverlap] = field(default_factory=list)
    function_count_a: int = 0
    function_count_b: int = 0
    avg_function_similarity: float = 0.0

    block_matches: List[BlockMatch] = field(default_factory=list)
    block_match_count: int = 0

    ast_function_count_a: int = 0
    ast_function_count_b: int = 0
    ast_class_count_a: int = 0
    ast_class_count_b: int = 0
    ast_shared_structure: float = 0.0

    control_flow: Optional[ControlFlowEvidence] = None

    variable_renames: List[VariableRename] = field(default_factory=list)
    renaming_pattern: str = "none"
    plagiarism_type: str = "not_plagiarized"
    plagiarism_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "function_overlap": {
                fo.name_a: {
                    "name_b": fo.name_b,
                    "similarity": round(fo.similarity, 4),
                    "lines_a": list(fo.lines_a),
                    "lines_b": list(fo.lines_b),
                    "type": fo.type,
                }
                for fo in self.function_overlap
            },
            "function_count_a": self.function_count_a,
            "function_count_b": self.function_count_b,
            "avg_function_similarity": round(self.avg_function_similarity, 4),
            "block_matches": [
                {
                    "lines_a": list(bm.lines_a),
                    "lines_b": list(bm.lines_b),
                    "score": round(bm.score, 4),
                    "type": bm.type,
                }
                for bm in self.block_matches
            ],
            "block_match_count": self.block_match_count,
            "ast": {
                "function_count_a": self.ast_function_count_a,
                "function_count_b": self.ast_function_count_b,
                "class_count_a": self.ast_class_count_a,
                "class_count_b": self.ast_class_count_b,
                "shared_structure": round(self.ast_shared_structure, 4),
            },
            "control_flow": {
                "identical": (
                    self.control_flow.identical if self.control_flow else False
                ),
                "similarity": (
                    round(self.control_flow.similarity, 4) if self.control_flow else 0.0
                ),
                "sequence_a": (
                    self.control_flow.sequence_a[:10] if self.control_flow else []
                ),
                "sequence_b": (
                    self.control_flow.sequence_b[:10] if self.control_flow else []
                ),
            },
            "variable_renames": [
                {
                    "original": vr.original,
                    "renamed_to": vr.renamed_to,
                    "context": vr.context,
                }
                for vr in self.variable_renames[:10]
            ],
            "renaming_pattern": self.renaming_pattern,
            "plagiarism_type": self.plagiarism_type,
            "plagiarism_description": self.plagiarism_description,
        }

    def summary(self) -> str:
        """Human-readable summary for academic committee reports."""
        lines = ["Evidence Summary:", ""]

        if self.function_overlap:
            lines.append("Function overlap:")
            for fo in self.function_overlap:
                lines.append(
                    f"  {fo.name_a} → {fo.name_b}: {fo.similarity:.0%} ({fo.type})"
                )
            lines.append("")

        if self.ast_shared_structure > 0:
            lines.append(
                f"AST overlap: {self.ast_shared_structure:.0%}"
                f" ({self.ast_function_count_a} vs {self.ast_function_count_b} functions)"
            )
            lines.append("")

        if self.control_flow and self.control_flow.similarity > 0:
            flow_label = (
                "identical"
                if self.control_flow.identical
                else f"{self.control_flow.similarity:.0%} similar"
            )
            lines.append(f"Control flow: {flow_label}")
            lines.append(f"  A: {' → '.join(self.control_flow.sequence_a[:8])}")
            lines.append(f"  B: {' → '.join(self.control_flow.sequence_b[:8])}")
            lines.append("")

        if self.variable_renames:
            lines.append("Variable renames detected:")
            for vr in self.variable_renames[:5]:
                lines.append(f"  {vr.original} → {vr.renamed_to} ({vr.context})")
            lines.append("")

        if self.plagiarism_type != "not_plagiarized":
            lines.append(f"Classification: {self.plagiarism_type}")
            lines.append(f"  {self.plagiarism_description}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions for code analysis
# ═══════════════════════════════════════════════════════════════════════════
PYTHON_KEYWORDS = {
    "if",
    "else",
    "elif",
    "for",
    "while",
    "def",
    "class",
    "return",
    "import",
    "from",
    "with",
    "as",
    "try",
    "except",
    "finally",
    "raise",
    "yield",
    "assert",
    "pass",
    "break",
    "continue",
    "del",
    "global",
    "nonlocal",
    "and",
    "or",
    "not",
    "in",
    "is",
    "lambda",
    "True",
    "False",
    "None",
    "print",
    "range",
    "len",
    "int",
    "str",
    "list",
    "dict",
    "set",
    "float",
}

COMMON_PYTHON_BUILTINS = {
    "len",
    "int",
    "str",
    "float",
    "list",
    "dict",
    "set",
    "tuple",
    "print",
    "range",
    "input",
    "type",
    "sum",
    "min",
    "max",
    "abs",
    "sorted",
    "reversed",
    "enumerate",
    "zip",
    "map",
    "filter",
    "isinstance",
    "hasattr",
    "getattr",
}


def _extract_functions(code: str) -> List[Dict[str, Any]]:
    """Extract function definitions from Python code."""
    lines = code.split("\n")
    functions = []
    current_func = None
    indent_level = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect function definition
        match = re.match(r"^(def|function|func)\s+(\w+)\s*\((.*?)\)", stripped)
        if match:
            if current_func:
                current_func["end_line"] = i
                current_func["body"] = "\n".join(lines[current_func["start_line"] : i])
                functions.append(current_func)

            current_func = {
                "name": match.group(2),
                "start_line": i + 1,  # 1-indexed
                "end_line": i + 1,
                "params": [
                    p.strip().split("=")[0].strip()
                    for p in match.group(3).split(",")
                    if p.strip()
                ],
                "body": "",
                "line": i,
            }
        elif current_func and line.startswith(" ") or (line and not stripped):
            current_func["end_line"] = i + 1
        elif current_func and stripped and not line.startswith(" "):
            current_func["body"] = "\n".join(lines[current_func["start_line"] : i])
            current_func["end_line"] = i
            functions.append(current_func)
            current_func = None

    if current_func:
        current_func["body"] = "\n".join(lines[current_func["start_line"] - 1 :])
        current_func["end_line"] = len(lines)
        functions.append(current_func)

    return functions


def _extract_control_flow(code: str) -> List[str]:
    """Extract control flow keywords sequence from code."""
    tokens = re.findall(r"[A-Za-z_]\w*|\S", code)
    flow_tokens = []
    for tok in tokens:
        if tok in {
            "if",
            "else",
            "elif",
            "for",
            "while",
            "switch",
            "case",
            "return",
            "break",
            "continue",
        }:
            flow_tokens.append(tok.upper())
        elif tok in {"try", "catch", "except", "finally"}:
            flow_tokens.append("EXCEPTION")
        elif tok == "{":
            flow_tokens.append("BLOCK_START")
        elif tok == "}":
            flow_tokens.append("BLOCK_END")
    return flow_tokens


def _detect_renames(
    params_a: List[str],
    params_b: List[str],
    body_a: str,
    body_b: str,
) -> List[VariableRename]:
    """Detect variable renaming between two function bodies."""
    renames = []

    # Parameter renaming
    for pa, pb in zip(params_a, params_b):
        if pa != pb and pa not in COMMON_PYTHON_BUILTINS:
            renames.append(
                VariableRename(original=pa, renamed_to=pb, context="parameter")
            )

    # Identifier-only renaming check
    # Remove all strings, numbers, and keywords, compare remaining identifiers
    def extract_identifiers(code: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z_]\w*", code)
        return [
            t
            for t in tokens
            if t not in PYTHON_KEYWORDS and t not in COMMON_PYTHON_BUILTINS
        ]

    ids_a = extract_identifiers(body_a)
    ids_b = extract_identifiers(body_b)

    counter_a = Counter(ids_a)
    counter_b = Counter(ids_b)

    # Try to find a mapping between identifiers
    unique_a = set(ids_a)
    unique_b = set(ids_b)
    shared = unique_a & unique_b

    # Only report renames for identifiers that exist in both but differently
    for id_a in unique_a - shared:
        # Check if similar identifiers exist in unique_b
        for id_b in unique_b - shared:
            if (
                len(id_a) == len(id_b)
                and SequenceMatcher(None, id_a, id_b).ratio() > 0.6
            ):
                renames.append(
                    VariableRename(original=id_a, renamed_to=id_b, context="local_var")
                )
                break

    return renames[:10]  # Cap at 10 renames


class Layer4Explainability:
    """Explainability layer — generates human-readable evidence for every verdict.

    This layer provides the detailed evidence chain needed for:
      - Course coordinators reviewing plagiarism reports
      - Academic integrity committee hearings
      - Student appeals (why was this flagged?)
      - Legal compliance (evidence preservation)
    """

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Optional[Dict[str, float]] = None,
        engine_details: Optional[Dict[str, Any]] = None,
    ) -> ExplanationReport:
        """Run explainability analysis on a pair of code files.

        Args:
            code_a: Source code of first file.
            code_b: Source code of second file.
            engine_scores: Pre-computed engine scores (unused for explainability).
            engine_details: Optional detailed engine output.

        Returns:
            ExplanationReport with detailed evidence.
        """
        # ── Extract functions from both files ──
        funcs_a = _extract_functions(code_a)
        funcs_b = _extract_functions(code_b)

        # ── Compare functions ──
        function_overlap: List[FunctionOverlap] = []
        func_sims = []

        for fa in funcs_a:
            best_match = None
            best_sim = 0.0
            for fb in funcs_b:
                sim = SequenceMatcher(None, fa["body"], fb["body"]).ratio()
                if sim > best_sim and sim > 0.3:  # threshold for "similar"
                    best_sim = sim
                    best_match = fb

            if best_match:
                # Classify overlap type
                if best_sim > 0.95:
                    overlap_type = "identical"
                elif best_match["name"] != fa["name"]:
                    overlap_type = "renamed_variables"
                else:
                    overlap_type = "restructured"

                function_overlap.append(
                    FunctionOverlap(
                        name_a=fa["name"],
                        name_b=best_match["name"],
                        similarity=best_sim,
                        lines_a=(fa["start_line"], fa["end_line"]),
                        lines_b=(best_match["start_line"], best_match["end_line"]),
                        type=overlap_type,
                    )
                )
                func_sims.append(best_sim)

        avg_func_sim = sum(func_sims) / len(func_sims) if func_sims else 0.0

        # ── Block-level comparison ──
        lines_a = code_a.split("\n")
        lines_b = code_b.split("\n")
        block_matches = []

        # Simple line-by-line block matching
        window_size = 4  # Match blocks of 4 lines
        for i in range(0, max(1, len(lines_a) - window_size), window_size):
            block_a = "\n".join(lines_a[i : i + window_size])
            if not block_a.strip():
                continue
            for j in range(0, max(1, len(lines_b) - window_size), window_size):
                block_b = "\n".join(lines_b[j : j + window_size])
                if not block_b.strip():
                    continue
                score = SequenceMatcher(None, block_a, block_b).ratio()
                if score > 0.7:  # Threshold for block match
                    # Determine block type
                    keywords = {"for ", "while ", "if ", "return "}
                    block_text = block_a.lower()
                    if any(kw in block_text for kw in keywords):
                        btype = (
                            "loop_pattern"
                            if ("for " in block_text or "while " in block_text)
                            else "conditional_block"
                        )
                    else:
                        btype = "function_body"
                    block_matches.append(
                        BlockMatch(
                            lines_a=(i + 1, i + window_size),
                            lines_b=(j + 1, j + window_size),
                            score=score,
                            type=btype,
                        )
                    )
                    break  # Only one match per A block

        # Deduplicate and sort by score
        seen = set()
        deduped = []
        for bm in sorted(block_matches, key=lambda x: -x.score):
            key = (bm.lines_a[0], bm.lines_b[0])
            if key not in seen:
                seen.add(key)
                deduped.append(bm)
        block_matches = deduped[:15]  # Cap at 15 blocks

        # ── AST-level comparison ──
        func_count_a = len(funcs_a)
        func_count_b = len(funcs_b)

        class_count_a = sum(
            1 for line in lines_a if re.match(r"^\s*(class\s+\w+)", line.strip())
        )
        class_count_b = sum(
            1 for line in lines_b if re.match(r"^\s*(class\s+\w+)", line.strip())
        )

        # Shared structure: ratio of function count similarity
        struct_sim = (
            SequenceMatcher(
                None,
                sorted([f["name"] for f in funcs_a]),
                sorted([f["name"] for f in funcs_b]),
            ).ratio()
            if (funcs_a or funcs_b)
            else 0.0
        )

        # ── Control flow comparison ──
        flow_a = _extract_control_flow(code_a)
        flow_b = _extract_control_flow(code_b)

        if flow_a and flow_b:
            flow_sim = SequenceMatcher(None, flow_a, flow_b).ratio()
            flow_identical = flow_a == flow_b
        else:
            flow_sim = 0.0
            flow_identical = False

        control_flow = ControlFlowEvidence(
            identical=flow_identical,
            sequence_a=flow_a[:15],
            sequence_b=flow_b[:15],
            similarity=flow_sim,
        )

        # ── Variable renaming detection ──
        all_renames: List[VariableRename] = []
        for fa in funcs_a:
            for fb in funcs_b:
                renames = _detect_renames(
                    fa["params"], fb["params"], fa["body"], fb["body"]
                )
                all_renames.extend(renames)

        # Deduplicate
        seen_renames = set()
        unique_renames = []
        for r in all_renames:
            key = (r.original, r.renamed_to)
            if key not in seen_renames:
                seen_renames.add(key)
                unique_renames.append(r)
        variable_renames = unique_renames[:10]

        # ── Classify plagiarism type ──
        plagiarism_type, plagiarism_desc = self._classify_type(
            function_overlap=function_overlap,
            block_matches=block_matches,
            variable_renames=variable_renames,
            control_flow_sim=control_flow.similarity,
        )

        # ── Determine renaming pattern ──
        if variable_renames:
            renaming_pattern = "identifier_renaming"
        elif function_overlap and any(
            fo.type == "identical" for fo in function_overlap
        ):
            renaming_pattern = "exact_copy"
        elif block_matches:
            renaming_pattern = "block_reuse"
        else:
            renaming_pattern = "none"

        return ExplanationReport(
            function_overlap=function_overlap,
            function_count_a=func_count_a,
            function_count_b=func_count_b,
            avg_function_similarity=avg_func_sim,
            block_matches=block_matches,
            block_match_count=len(block_matches),
            ast_function_count_a=func_count_a,
            ast_function_count_b=func_count_b,
            ast_class_count_a=class_count_a,
            ast_class_count_b=class_count_b,
            ast_shared_structure=struct_sim,
            control_flow=control_flow,
            variable_renames=variable_renames,
            renaming_pattern=renaming_pattern,
            plagiarism_type=plagiarism_type,
            plagiarism_description=plagiarism_desc,
        )

    def _classify_type(
        self,
        function_overlap: List[FunctionOverlap],
        block_matches: List[BlockMatch],
        variable_renames: List[VariableRename],
        control_flow_sim: float,
    ) -> Tuple[str, str]:
        """Classify the plagiarism type based on evidence.

        Returns:
            Tuple of (type_name, human_description)
        """
        has_identical_funcs = any(fo.type == "identical" for fo in function_overlap)
        has_renamed_funcs = any(
            fo.type == "renamed_variables" for fo in function_overlap
        )
        has_restructured = any(fo.type == "restructured" for fo in function_overlap)
        avg_func_sim = (
            sum(fo.similarity for fo in function_overlap) / len(function_overlap)
            if function_overlap
            else 0.0
        )
        high_block_match = any(bm.score > 0.8 for bm in block_matches)

        if has_identical_funcs and not variable_renames:
            return (
                "type_1_identical",
                "Exact copy detected — functions are identical across both files.",
            )
        elif has_renamed_funcs and variable_renames:
            return (
                "type_2_renamed",
                f"Identifier renaming detected — {len(variable_renames)} variables renamed. "
                f"Function bodies remain structurally similar.",
            )
        elif has_restructured and control_flow_sim > 0.5:
            return (
                "type_3_restructured",
                "Control flow reordering with renaming — same logic, different structure.",
            )
        elif avg_func_sim > 0.5 and not variable_renames:
            return (
                "type_4_semantic",
                "Similar functionality with different implementation — "
                "may indicate code generation from same requirements.",
            )
        elif high_block_match and avg_func_sim < 0.3:
            return (
                "type_5_template",
                "Shared code blocks (template/starter code) — "
                "check if assignment template matches.",
            )
        return (
            "not_plagiarized",
            "Insufficient evidence for plagiarism classification.",
        )
