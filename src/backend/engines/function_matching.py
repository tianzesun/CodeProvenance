"""Function-level matching for plagiarism detection.

This module provides detailed function matching analysis that is
more interpretable for professors reviewing academic integrity cases.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


@dataclass
class FunctionMatch:
    """Represents a matched function between two code files."""

    function_name_a: str
    function_name_b: str
    similarity: float  # 0.0 - 1.0
    ast_similarity: float  # AST structure similarity
    control_flow_similarity: float  # Control flow similarity
    variable_rename_count: int
    parameter_rename_count: int
    has_structural_match: bool
    matched_blocks: List[Tuple[int, int, int, int]]  # (start_a, end_a, start_b, end_b)


@dataclass
class FunctionMatchReport:
    """Complete function matching analysis report."""

    total_functions_a: int
    total_functions_b: int
    matched_functions: List[FunctionMatch] = field(default_factory=list)
    unmatched_functions_a: List[str] = field(default_factory=list)
    unmatched_functions_b: List[str] = field(default_factory=list)
    total_matched_lines: int = 0
    rename_patterns: Dict[str, str] = field(default_factory=dict)
    variable_rename_count: int = 0
    parameter_rename_count: int = 0

    @property
    def match_count(self) -> int:
        return len(self.matched_functions)

    @property
    def match_rate(self) -> float:
        if self.total_functions_a == 0 and self.total_functions_b == 0:
            return 0.0
        max_funcs = max(self.total_functions_a, self.total_functions_b)
        return self.match_count / max_funcs if max_funcs > 0 else 0.0


class FunctionMatcher:
    """Analyzes function-level similarity between code files."""

    def __init__(self, similarity_threshold: float = 0.7) -> None:
        self.similarity_threshold = similarity_threshold

    def extract_functions(self, code: str) -> Dict[str, str]:
        """Extract function names and their bodies from code.

        Args:
            code: Source code string.

        Returns:
            Dictionary mapping function name to normalized body.
        """
        functions = {}
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Get function body as string
                    body_lines = code.split("\n")[node.lineno - 1 : node.end_lineno]
                    body = "\n".join(body_lines)
                    functions[node.name] = body
        except SyntaxError:
            pass

        return functions

    def normalize_function(self, func_code: str) -> str:
        """Normalize function code for comparison.

        - Removes docstrings
        - Normalizes whitespace
        - Replaces literals with placeholders
        """
        try:
            tree = ast.parse(func_code)
            # Remove docstrings
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str):
                        node.value = ast.Constant(value="")

            # Normalize
            normalized = func_code
            normalized = re.sub(r"\s+", " ", normalized)
            normalized = re.sub(r"\b\d+\b", "NUM", normalized)
            return normalized.strip()
        except SyntaxError:
            return func_code

    def compute_ast_similarity(self, code_a: str, code_b: str) -> float:
        """Compute AST structure similarity."""
        try:
            tree_a = ast.parse(code_a)
            tree_b = ast.parse(code_b)

            # Get structure signatures
            sig_a = self._get_ast_signature(tree_a)
            sig_b = self._get_ast_signature(tree_b)

            # Compare signatures
            matcher = SequenceMatcher(None, sig_a, sig_b)
            return matcher.ratio()
        except SyntaxError:
            return 0.0

    def _get_ast_signature(self, tree: ast.AST) -> List[str]:
        """Get a normalized signature of AST structure."""
        signature = []
        for node in ast.walk(tree):
            node_type = type(node).__name__
            if isinstance(node, ast.FunctionDef):
                signature.append(f"FUNC:{node.name}")
            elif isinstance(node, ast.ClassDef):
                signature.append(f"CLASS:{node.name}")
            elif node_type in ("For", "While", "If", "FunctionDef", "ClassDef"):
                signature.append(node_type)
        return signature

    def compute_control_flow_similarity(self, code: str) -> float:
        """Compute control flow similarity (normalized)."""
        try:
            tree = ast.parse(code)
            cf_nodes = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    cf_nodes.append(type(node).__name__)
            # Return count normalized by common structures
            return min(1.0, len(cf_nodes) / 10.0)
        except SyntaxError:
            return 0

    def detect_variable_renaming(self, code_a: str, code_b: str) -> Dict[str, str]:
        """Detect variable renaming patterns between functions."""
        renames = {}

        try:
            tree_a = ast.parse(code_a)
            tree_b = ast.parse(code_b)

            vars_a = set()
            vars_b = set()

            for node in ast.walk(tree_a):
                if isinstance(node, ast.Name):
                    vars_a.add(node.id)

            for node in ast.walk(tree_b):
                if isinstance(node, ast.Name):
                    vars_b.add(node.id)

            # Simple heuristic: if same count and similar patterns
            if len(vars_a) == len(vars_b) and len(vars_a) > 0:
                sorted_a = sorted(vars_a)
                sorted_b = sorted(vars_b)
                for va, vb in zip(sorted_a, sorted_b):
                    if va != vb:
                        renames[va] = vb
        except SyntaxError:
            pass

        return renames

    def match_functions(
        self,
        code_a: str,
        code_b: str,
        func_names_a: Optional[List[str]] = None,
        func_names_b: Optional[List[str]] = None,
    ) -> FunctionMatchReport:
        """Match functions between two code files.

        Args:
            code_a: First source code.
            code_b: Second source code.
            func_names_a: Optional list of function names in code_a.
            func_names_b: Optional list of function names in code_b.

        Returns:
            FunctionMatchReport with detailed matching information.
        """
        functions_a = self.extract_functions(code_a)
        functions_b = self.extract_functions(code_b)

        if func_names_a is None:
            func_names_a = list(functions_a.keys())
        if func_names_b is None:
            func_names_b = list(functions_b.keys())

        report = FunctionMatchReport(
            total_functions_a=len(func_names_a),
            total_functions_b=len(func_names_b),
        )

        # Match functions by name similarity
        for name_a in func_names_a:
            best_match = None
            best_score = 0.0

            for name_b in func_names_b:
                name_sim = SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()
                if name_sim > best_score and name_sim >= 0.7:
                    best_score = name_sim
                    best_match = name_b

            if best_match:
                func_a = functions_a.get(name_a, "")
                func_b = functions_b.get(best_match, "")

                ast_sim = self.compute_ast_similarity(
                    self.normalize_function(func_a),
                    self.normalize_function(func_b),
                )

                match = FunctionMatch(
                    function_name_a=name_a,
                    function_name_b=best_match,
                    similarity=ast_sim,
                    ast_similarity=ast_sim,
                    control_flow_similarity=self.compute_control_flow_similarity(
                        func_a
                    ),
                    variable_rename_count=0,
                    parameter_rename_count=0,
                    has_structural_match=ast_sim >= self.similarity_threshold,
                    matched_blocks=[],
                )

                renames = self.detect_variable_renaming(func_a, func_b)
                match.variable_rename_count = len(renames)
                match.parameter_rename_count = len(
                    [k for k in renames.keys() if k.startswith("param_")]
                )
                report.rename_patterns.update(renames)
                report.variable_rename_count += match.variable_rename_count
                report.parameter_rename_count += match.parameter_rename_count
                report.matched_functions.append(match)
                report.total_matched_lines += len(func_a.split("\n"))
            else:
                report.unmatched_functions_a.append(name_a)

        for name_b in func_names_b:
            if name_b not in [m.function_name_b for m in report.matched_functions]:
                report.unmatched_functions_b.append(name_b)

        return report


def generate_function_match_summary(report: FunctionMatchReport) -> str:
    """Generate a human-readable summary of function matches.

    Args:
        report: FunctionMatchReport to summarize.

    Returns:
        Human-readable string summarizing the matches.
    """
    if report.match_count == 0:
        return "No functions matched between submissions."

    lines = [f"Matched Functions: {report.match_count}"]
    lines.append("")

    for match in report.matched_functions:
        lines.append(f"• {match.function_name_a} ↔ {match.function_name_b}")
        lines.append(f"  AST similarity: {match.ast_similarity:.1%}")
        lines.append(f"  Control Flow: {match.control_flow_similarity:.1%}")
        if match.variable_rename_count > 0:
            lines.append(f"  Variable renames: {match.variable_rename_count}")
        lines.append("")

    lines.append(f"Total matched lines: {report.total_matched_lines}")
    return "\n".join(lines)
