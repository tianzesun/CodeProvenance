"""Professor-readable structural evidence from source code.

The AST layer should not only return a similarity number. This module extracts
simple, stable structural facts and compares them as evidence labels professors
can understand: same function decomposition, branch order, loop nesting,
exception handling, and helper-function pattern.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class StructuralProfile:
    """Normalized structure facts extracted from one submission."""

    function_count: int = 0
    function_shapes: List[int] = field(default_factory=list)
    branch_order: List[str] = field(default_factory=list)
    max_loop_nesting: int = 0
    exception_handlers: int = 0
    helper_call_pattern: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuralEvidence:
    """Professor-readable comparison evidence from two structural profiles."""

    same_function_decomposition: bool
    same_branch_order: bool
    same_loop_nesting: bool
    same_exception_handling: bool
    same_helper_function_pattern: bool
    evidence: List[str]


def extract_structural_profile(source: str) -> StructuralProfile:
    """Extract normalized Python AST structure facts from source text."""
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return StructuralProfile()

    function_shapes: List[int] = []
    branch_order: List[str] = []
    exception_handlers = 0
    helper_calls: List[str] = []
    max_loop_nesting = 0

    def visit(node: ast.AST, loop_depth: int = 0) -> None:
        nonlocal exception_handlers, max_loop_nesting

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_shapes.append(len(node.args.args))
        if isinstance(node, ast.If):
            branch_order.append("if")
        elif isinstance(node, ast.For):
            branch_order.append("for")
            loop_depth += 1
            max_loop_nesting = max(max_loop_nesting, loop_depth)
        elif isinstance(node, ast.While):
            branch_order.append("while")
            loop_depth += 1
            max_loop_nesting = max(max_loop_nesting, loop_depth)
        elif isinstance(node, ast.Try):
            branch_order.append("try")
            exception_handlers += len(node.handlers)
        elif isinstance(node, ast.Call):
            helper_calls.append(_normalize_call(node))

        for child in ast.iter_child_nodes(node):
            visit(child, loop_depth)

    visit(tree)
    return StructuralProfile(
        function_count=len(function_shapes),
        function_shapes=function_shapes,
        branch_order=branch_order,
        max_loop_nesting=max_loop_nesting,
        exception_handlers=exception_handlers,
        helper_call_pattern=helper_calls[:16],
    )


def compare_structural_profiles(
    profile_a: StructuralProfile, profile_b: StructuralProfile
) -> StructuralEvidence:
    """Compare normalized structural profiles and return readable evidence."""
    same_function_decomposition = (
        profile_a.function_count > 0
        and profile_a.function_count == profile_b.function_count
        and profile_a.function_shapes == profile_b.function_shapes
    )
    same_branch_order = _same_sequence(profile_a.branch_order, profile_b.branch_order)
    same_loop_nesting = (
        profile_a.max_loop_nesting > 0
        and profile_a.max_loop_nesting == profile_b.max_loop_nesting
    )
    same_exception_handling = (
        profile_a.exception_handlers > 0
        and profile_a.exception_handlers == profile_b.exception_handlers
    )
    same_helper_function_pattern = _same_sequence(
        profile_a.helper_call_pattern, profile_b.helper_call_pattern
    )

    evidence: List[str] = []
    if same_function_decomposition:
        evidence.append("same function decomposition")
    if same_branch_order:
        evidence.append("same branch order")
    if same_loop_nesting:
        evidence.append("same loop nesting")
    if same_exception_handling:
        evidence.append("same exception handling")
    if same_helper_function_pattern:
        evidence.append("same helper function pattern")

    return StructuralEvidence(
        same_function_decomposition=same_function_decomposition,
        same_branch_order=same_branch_order,
        same_loop_nesting=same_loop_nesting,
        same_exception_handling=same_exception_handling,
        same_helper_function_pattern=same_helper_function_pattern,
        evidence=evidence,
    )


def compare_structural_evidence(source_a: str, source_b: str) -> StructuralEvidence:
    """Extract and compare professor-readable structural evidence."""
    return compare_structural_profiles(
        extract_structural_profile(source_a),
        extract_structural_profile(source_b),
    )


def structural_evidence_features(evidence: StructuralEvidence) -> Dict[str, float]:
    """Convert structural evidence booleans into ranker-ready features."""
    return {
        "same_function_decomposition": float(evidence.same_function_decomposition),
        "same_branch_order": float(evidence.same_branch_order),
        "same_loop_nesting": float(evidence.same_loop_nesting),
        "same_exception_handling": float(evidence.same_exception_handling),
        "same_helper_function_pattern": float(evidence.same_helper_function_pattern),
    }


def _same_sequence(left: Sequence[str], right: Sequence[str]) -> bool:
    """Return true for meaningful identical normalized sequences."""
    return len(left) >= 2 and list(left) == list(right)


def _normalize_call(node: ast.Call) -> str:
    """Normalize call sites while preserving helper-call shape."""
    if isinstance(node.func, ast.Name):
        return "helper"
    if isinstance(node.func, ast.Attribute):
        return "method"
    return "call"
