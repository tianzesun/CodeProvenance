"""AST Evidence Extractor for Academic Integrity Detection.

This module implements a redesigned AST system that:
1. Computes multiple independent evidence layers
2. Distinguishes AST structure from semantic content
3. Handles React/TSX files specially
4. Prevents boilerplate false positives

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                    AST EVIDENCE EXTRACTOR                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 1: SHAPE EVIDENCE (weight: 0.20)              │   │
│  │ - Tree structure (parent-child relationships)        │   │
│  │ - Node depth distribution                          │   │
│  │ - CHILD: NOT dominant in final decision            │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 2: SEMANTIC NODE EVIDENCE (weight: 0.35)      │   │
│  │ - function calls                                   │   │
│  │ - operators                                        │   │
│  │ - expressions                                      │   │
│  │ - FUNCTION LOGIC: Dominant weight                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 3: CONTROL FLOW EVIDENCE (weight: 0.25)       │   │
│  │ - if/else                                            │   │
│  │ - loops                                              │   │
│  │ - return patterns                                    │   │
│  │ - branching structure                                │   │
│  │  OPERATION: High weight                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 4: IDENTIFIER ROLE EVIDENCE (weight: 0.20)    │   │
│  │ - variable roles                                     │   │
│  │ - function roles                                     │   │
│  │ - parameter patterns                                 │   │
│  │  NOT: full identifier normalization                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 5: REACT COMPONENT EVIDENCE (TSX only)        │   │
│  │ - Component hierarchy                                │   │
│  │ - Props structure                                  │   │
│  │ - Hook usage                                         │   │
│  │ - BOILERPLATE DISCOUNT APPLIED                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ STRUCTURAL DIVERGENCE SCORE                         │   │
│  │ - function count diff                              │   │
│  │ - component count diff                             │   │
│  │ - nesting depth diff                               │   │
│  │ - control flow diff                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ EVIDENCE FUSION (NOT SCORE)                         │   │
│  │ - Evidence-based rule engine decides                │   │
│  │ - NO AST score allowed in final decision          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ASTEvidence:
    """Evidence from AST analysis layers.

    IMPORTANT: This contains EVIDENCE, not scores.
    The rule engine uses this evidence to make decisions.
    """

    # Shape evidence (structural patterns)
    shape_evidence: dict[str, Any] = field(default_factory=dict)
    shape_node_counts: dict[str, int] = field(default_factory=dict)
    shape_depth_distribution: dict[int, int] = field(default_factory=dict)

    # Semantic node evidence (logic operations)
    semantic_calls: list[str] = field(default_factory=list)
    semantic_operators: list[str] = field(default_factory=list)
    semantic_expressions: list[str] = field(default_factory=list)
    semantic_function_defs: list[str] = field(default_factory=list)

    # Control flow evidence
    control_flow_structures: list[str] = field(default_factory=list)
    control_flow_patterns: dict[str, int] = field(default_factory=dict)

    # Identifier role evidence (NOT normalized names)
    variable_roles: list[str] = field(default_factory=list)
    function_roles: list[str] = field(default_factory=list)
    parameter_patterns: list[str] = field(default_factory=list)

    # React/TSX specific evidence
    has_react_imports: bool = False
    has_jsx: bool = False
    component_names: list[str] = field(default_factory=list)
    hook_usage: dict[str, int] = field(default_factory=dict)
    boilerplate_patterns: list[str] = field(default_factory=list)
    boilerplate_discount: float = 1.0

    # Structural divergence
    divergence_score: float = 0.0

    # File type
    file_type: str = "CODE"


class ASTEvidenceExtractor:
    """Extracts evidence from AST analysis for academic integrity decisions.

    This is NOT a similarity scorer. It extracts evidence that the
    rule engine uses to make decisions.
    """

    LOGIC_NODES: ClassVar[set] = {
        "Call",
        "FunctionDef",
        "AsyncFunctionDef",
        "ClassDef",
        "BinOp",
        "BoolOp",
        "Compare",
        "Assign",
        "AugAssign",
        "Return",
        "Yield",
        "Await",
        "Lambda",
        "IfExp",
        "ListComp",
        "SetComp",
        "DictComp",
        "GeneratorExp",
    }

    CONTROL_NODES: ClassVar[set] = {
        "If",
        "For",
        "While",
        "With",
        "Try",
        "ExceptHandler",
        "Raise",
        "Assert",
        "Return",
        "Yield",
        "Break",
        "Continue",
    }

    REACT_IMPORT_PATTERNS: ClassVar[list] = [
        r"import\s+React\s+from\s+['\"]react['\"]",
        r"import\s+\{.*\}\s+from\s+['\"]react['\"]",
        r"from\s+['\"]react['\"]",
    ]

    HOOK_PATTERNS: ClassVar[list] = [
        (r"useState\s*\(", "useState"),
        (r"useEffect\s*\(", "useEffect"),
        (r"useCallback\s*\(", "useCallback"),
        (r"useMemo\s*\(", "useMemo"),
        (r"useContext\s*\(", "useContext"),
        (r"useReducer\s*\(", "useReducer"),
    ]

    def __init__(self) -> None:
        self._jsx_tag_pattern = re.compile(r"</?[A-Z][a-zA-Z0-9]*")

    def extract(
        self, code_a: str, code_b: str, file_type: str = "CODE"
    ) -> tuple[ASTEvidence, ASTEvidence]:
        """Extract evidence from two code strings.

        Args:
            code_a: First code string
            code_b: Second code string
            file_type: File type classification (CODE, CONFIG, etc.)

        Returns:
            Tuple of (evidence_a, evidence_b)
        """
        evidence_a = self._extract_single(code_a, file_type)
        evidence_b = self._extract_single(code_b, file_type)

        # Compute divergence score
        evidence_a.divergence_score = self._compute_divergence(evidence_a, evidence_b)
        evidence_b.divergence_score = evidence_a.divergence_score

        return evidence_a, evidence_b

    def _extract_single(self, code: str, file_type: str) -> ASTEvidence:
        """Extract evidence from a single code string."""
        evidence = ASTEvidence(file_type=file_type)

        # Check for React/JSX
        evidence.has_react_imports = self._detect_react_imports(code)
        evidence.has_jsx = self._detect_jsx(code)

        # Extract boilerplate for React files
        if evidence.has_react_imports or evidence.has_jsx:
            evidence.boilerplate_patterns = self._extract_structural_patterns(code)
            evidence.boilerplate_discount = self._compute_boilerplate_discount(
                evidence.boilerplate_patterns
            )
            evidence.hook_usage = self._extract_hooks(code)
            evidence.component_names = self._extract_component_names(code)

        # Parse AST
        tree = None
        try:
            tree = ast.parse(code)
        except SyntaxError:
            pass

        if tree is not None:
            # Extract all evidence layers
            evidence.shape_node_counts = self._extract_shape_node_counts(tree)
            evidence.shape_depth_distribution = self._extract_shape_depth(tree)
            evidence.shape_evidence = self._extract_shape_evidence(tree)

            evidence.semantic_calls = self._extract_semantic_calls(tree)
            evidence.semantic_operators = self._extract_semantic_operators(tree)
            evidence.semantic_expressions = self._extract_semantic_expressions(tree)
            evidence.semantic_function_defs = self._extract_semantic_function_defs(tree)

            evidence.control_flow_structures = self._extract_control_flow(tree)
            evidence.control_flow_patterns = self._extract_control_flow_patterns(tree)

            evidence.variable_roles = self._extract_variable_roles(tree)
            evidence.function_roles = self._extract_function_roles(tree)
            evidence.parameter_patterns = self._extract_parameter_patterns(tree)
        else:
            # Fallback to regex for non-Python code
            evidence.shape_node_counts = self._extract_regex_node_counts(code)
            evidence.control_flow_structures = self._extract_regex_control_flow(code)
            evidence.semantic_calls = self._extract_regex_calls(code)

        return evidence

    def _detect_react_imports(self, code: str) -> bool:
        """Check if file imports React."""
        for pattern in self.REACT_IMPORT_PATTERNS:
            if re.search(pattern, code):
                return True
        return False

    def _detect_jsx(self, code: str) -> bool:
        """Check if code contains JSX."""
        return bool(self._jsx_tag_pattern.search(code))

    def _extract_structural_patterns(self, code: str) -> list[str]:
        """Extract structural boilerplate patterns."""
        patterns = []

        if re.search(r"import\s+.*react", code, re.IGNORECASE):
            patterns.append("react_import")
        if re.search(r"export\s+default", code):
            patterns.append("default_export")
        if re.search(r"className\s*=", code):
            patterns.append("jsx_attributes")
        if re.search(r"useState|useEffect|useContext", code):
            patterns.append("react_hooks")
        if re.search(r"\.map\s*\(", code):
            patterns.append("array_map")

        return patterns

    def _compute_boilerplate_discount(self, patterns: list[str]) -> float:
        """Compute discount for boilerplate patterns."""
        if len(patterns) >= 3:
            return 0.1  # 90% discount
        elif len(patterns) >= 2:
            return 0.3  # 70% discount
        elif len(patterns) >= 1:
            return 0.6  # 40% discount
        return 1.0

    def _extract_hooks(self, code: str) -> dict[str, int]:
        """Extract hook usage counts."""
        hook_usage = {}
        for pattern, hook_name in self.HOOK_PATTERNS:
            matches = re.findall(pattern, code)
            if matches:
                hook_usage[hook_name] = len(matches)
        return hook_usage

    def _extract_component_names(self, code: str) -> list[str]:
        """Extract React component names (PascalCase functions)."""
        components = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name[0].isupper():
                    components.append(node.name)
        except SyntaxError:
            pass
        return components

    def _extract_shape_node_counts(self, tree: ast.AST) -> dict[str, int]:
        """Count each node type in the AST."""
        counts: dict[str, int] = {}
        for node in ast.walk(tree):
            node_name = type(node).__name__
            counts[node_name] = counts.get(node_name, 0) + 1
        return counts

    def _extract_shape_depth(self, tree: ast.AST) -> dict[int, int]:
        """Extract depth distribution of nodes."""
        depths: dict[int, int] = {}

        def walk_with_depth(node: ast.AST, depth: int) -> None:
            depths[depth] = depths.get(depth, 0) + 1
            for child in ast.iter_child_nodes(node):
                walk_with_depth(child, depth + 1)

        walk_with_depth(tree, 0)
        return depths

    def _extract_shape_evidence(self, tree: ast.AST) -> dict[str, Any]:
        """Extract shape evidence (structure patterns)."""
        evidence: dict[str, Any] = {}

        total_nodes = len(list(ast.walk(tree)))
        evidence["total_nodes"] = total_nodes
        evidence["function_count"] = len(
            [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        )
        evidence["class_count"] = len(
            [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        )

        return evidence

    def _extract_semantic_calls(self, tree: ast.AST) -> list[str]:
        """Extract function call names."""
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.append(node.func.id)
        return calls

    def _extract_semantic_operators(self, tree: ast.AST) -> list[str]:
        """Extract operator types."""
        operators = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.BoolOp)):
                operators.append(type(node.op).__name__)
        return operators

    def _extract_semantic_expressions(self, tree: ast.AST) -> list[str]:
        """Extract expression types."""
        expressions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                expressions.append("Compare")
            elif isinstance(node, ast.BinOp):
                expressions.append("BinOp")
            elif isinstance(node, ast.BoolOp):
                expressions.append("BoolOp")
        return expressions

    def _extract_semantic_function_defs(self, tree: ast.AST) -> list[str]:
        """Extract function definition names."""
        return [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]

    def _extract_control_flow(self, tree: ast.AST) -> list[str]:
        """Extract control flow structure types."""
        flow = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                flow.append(type(node).__name__)
        return flow

    def _extract_control_flow_patterns(self, tree: ast.AST) -> dict[str, int]:
        """Extract control flow pattern counts."""
        patterns: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                patterns["if"] = patterns.get("if", 0) + 1
            elif isinstance(node, (ast.For, ast.While)):
                patterns["loop"] = patterns.get("loop", 0) + 1
            elif isinstance(node, ast.With):
                patterns["with"] = patterns.get("with", 0) + 1
        return patterns

    def _extract_variable_roles(self, tree: ast.AST) -> list[str]:
        """Extract variable role patterns (assignments, usages)."""
        roles = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                roles.append("assign")
            elif isinstance(node, ast.AugAssign):
                roles.append("aug_assign")
        return roles

    def _extract_function_roles(self, tree: ast.AST) -> list[str]:
        """Extract function role patterns."""
        roles = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.decorator_list:
                    roles.append("decorated")
                else:
                    roles.append("plain_func")
        return roles

    def _extract_parameter_patterns(self, tree: ast.AST) -> list[str]:
        """Extract parameter patterns."""
        patterns = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                arg_count = len(node.args.args)
                if arg_count == 0:
                    patterns.append("no_args")
                elif arg_count <= 2:
                    patterns.append("few_args")
                else:
                    patterns.append("many_args")
        return patterns

    def _compute_divergence(
        self, evidence_a: ASTEvidence, evidence_b: ASTEvidence
    ) -> float:
        """Compute structural divergence score.

        Higher divergence = more different structures.
        """
        divergence_components = []

        # Function count divergence
        func_a = evidence_a.shape_evidence.get("function_count", 0)
        func_b = evidence_b.shape_evidence.get("function_count", 0)
        if func_a or func_b:
            func_div = abs(func_a - func_b) / max(func_a, func_b)
            divergence_components.append(func_div)

        # Class count divergence
        class_a = evidence_a.shape_evidence.get("class_count", 0)
        class_b = evidence_b.shape_evidence.get("class_count", 0)
        if class_a or class_b:
            class_div = abs(class_a - class_b) / max(class_a, class_b)
            divergence_components.append(class_div)

        # Control flow divergence
        flow_a = Counter(evidence_a.control_flow_structures)
        flow_b = Counter(evidence_b.control_flow_structures)
        if flow_a or flow_b:
            all_keys = set(flow_a.keys()) | set(flow_b.keys())
            flow_div = sum(abs(flow_a.get(k, 0) - flow_b.get(k, 0)) for k in all_keys)
            max_flow = max(sum(flow_a.values()), sum(flow_b.values()), 1)
            divergence_components.append(flow_div / max_flow)

        return (
            sum(divergence_components) / len(divergence_components)
            if divergence_components
            else 0.0
        )

    # Regex fallback methods for non-Python code
    def _extract_regex_node_counts(self, code: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        counts["function"] = len(re.findall(r"function\s+\w+", code))
        counts["class"] = len(re.findall(r"class\s+\w+", code))
        counts["if"] = len(re.findall(r"\bif\b", code))
        counts["loop"] = len(re.findall(r"\b(for|while)\b", code))
        return counts

    def _extract_regex_control_flow(self, code: str) -> list[str]:
        flow = []
        flow.extend(["if"] * len(re.findall(r"\bif\s*\(", code)))
        flow.extend(["loop"] * len(re.findall(r"\b(for|while)\s*\(", code)))
        return flow

    def _extract_regex_calls(self, code: str) -> list[str]:
        return re.findall(r"(\w+)\s*\(", code)


def extract_ast_evidence(
    code_a: str, code_b: str, file_type: str = "CODE"
) -> dict[str, Any]:
    """Convenience function to extract AST evidence and return as dictionary.

    This is the main entry point for the feature extractor.

    Returns:
        Dictionary with evidence fields for fusion with other signals.
    """
    extractor = ASTEvidenceExtractor()
    evidence_a, _evidence_b = extractor.extract(code_a, code_b, file_type)

    return {
        "shape_evidence": evidence_a.shape_evidence,
        "semantic_calls": evidence_a.semantic_calls,
        "semantic_operators": evidence_a.semantic_operators,
        "control_flow_structures": evidence_a.control_flow_structures,
        "variable_roles": evidence_a.variable_roles,
        "function_roles": evidence_a.function_roles,
        "parameter_patterns": evidence_a.parameter_patterns,
        "has_react_imports": evidence_a.has_react_imports,
        "has_jsx": evidence_a.has_jsx,
        "component_names": evidence_a.component_names,
        "hook_usage": evidence_a.hook_usage,
        "boilerplate_patterns": evidence_a.boilerplate_patterns,
        "boilerplate_discount": evidence_a.boilerplate_discount,
        "divergence_score": evidence_a.divergence_score,
    }


def compute_ast_layer_scores(
    code_a: str, code_b: str, file_type: str = "CODE"
) -> dict[str, float]:
    """Backwards-compatible function that returns evidence-based scores.

    NOTE: These are derived from evidence, not direct similarity scores.
    The rule engine makes the final decision.
    """
    evidence = extract_ast_evidence(code_a, code_b, file_type)

    # Compute scores from evidence (for backwards compatibility)
    # These are NOT the final decision - just evidence for the rule engine

    # Shape score from node counts
    shape_score = 0.0
    if evidence["shape_evidence"]:
        func_count = evidence["shape_evidence"].get("function_count", 0)
        shape_score = min(1.0, func_count / 10.0) if func_count > 0 else 0.0

    # Semantic score from calls and operators
    semantic_count = len(evidence["semantic_calls"]) + len(
        evidence["semantic_operators"]
    )
    semantic_score = min(1.0, semantic_count / 20.0) if semantic_count > 0 else 0.0

    # Control flow score
    flow_count = len(evidence["control_flow_structures"])
    control_flow_score = min(1.0, flow_count / 10.0) if flow_count > 0 else 0.0

    # Apply boilerplate discount
    discount = evidence["boilerplate_discount"]

    # Final score respects divergence
    divergence = evidence["divergence_score"]

    # Variable roles score
    var_roles_count = len(evidence.get("variable_roles", []))
    variable_roles_score = (
        min(1.0, var_roles_count / 10.0) if var_roles_count > 0 else 0.0
    )

    final_score = (
        (
            shape_score * 0.20
            + semantic_score * 0.35
            + control_flow_score * 0.25
            + variable_roles_score * 0.20
        )
        * discount
        * (1.0 - divergence * 0.5)
    )

    return {
        "shape_similarity": shape_score,
        "node_type_similarity": semantic_score,
        "control_flow_similarity": control_flow_score,
        "semantic_node_similarity": semantic_score,
        "component_similarity": len(evidence["component_names"]) * 0.1,
        "boilerplate_discount": discount,
        "final_score": min(1.0, max(0.0, final_score)),
        "divergence_score": divergence,
        "evidence": evidence,
    }
