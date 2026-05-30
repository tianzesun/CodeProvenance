"""TSX/JSX-aware structural analysis for React components.

This module provides specialized analysis for React/TSX files that:
1. Separates component-tree similarity from AST shape similarity
2. Identifies React-specific patterns (components, hooks, JSX structure)
3. Prevents boilerplate structures from producing false positives
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ComponentInfo:
    """Information about a React component."""

    name: str
    line_start: int
    line_end: int
    props: List[str]
    has_hooks: bool
    hook_names: List[str]
    jsx_depth: int
    children_count: int


@dataclass
class TSXAnalysisResult:
    """Result of TSX-aware analysis."""

    component_tree: List[ComponentInfo]
    has_jsx: bool
    has_react_imports: bool
    hook_usage: Dict[str, int]
    structural_patterns: List[str]
    component_similarity: float  # 0.0-1.0
    boilerplate_similarity: float  # 0.0-1.0 (to be discounted)


class TSXAnalyzer:
    """Analyzes TSX/JSX files for React-specific patterns."""

    REACT_IMPORT_PATTERNS = [
        r"import\s+React\s+from\s+['\"]react['\"]",
        r"import\s+\{.*\}\s+from\s+['\"]react['\"]",
        r"from\s+['\"]react['\"]",
    ]

    HOOK_PATTERNS = [
        (r"useState\s*\(", "useState"),
        (r"useEffect\s*\(", "useEffect"),
        (r"useCallback\s*\(", "useCallback"),
        (r"useMemo\s*\(", "useMemo"),
        (r"useContext\s*\(", "useContext"),
        (r"useReducer\s*\(", "useReducer"),
        (r"useLayoutEffect\s*\(", "useLayoutEffect"),
        (r"useRef\s*\(", "useRef"),
    ]

    def __init__(self) -> None:
        self._jsx_tag_pattern = re.compile(r"<[A-Za-z]")

    def analyze(self, code: str) -> TSXAnalysisResult:
        """Analyze TSX/JSX code for React patterns."""
        has_react_imports = self._detect_react_imports(code)
        has_jsx = self._detect_jsx(code)
        components = self._extract_components(code) if has_jsx else []
        hook_usage = self._extract_hooks(code)
        structural_patterns = self._extract_structural_patterns(code)

        return TSXAnalysisResult(
            component_tree=components,
            has_jsx=has_jsx,
            has_react_imports=has_react_imports,
            hook_usage=hook_usage,
            structural_patterns=structural_patterns,
            component_similarity=0.0,
            boilerplate_similarity=0.0,
        )

    def _detect_react_imports(self, code: str) -> bool:
        """Check if file imports React or React hooks."""
        for pattern in self.REACT_IMPORT_PATTERNS:
            if re.search(pattern, code):
                return True
        return False

    def _detect_jsx(self, code: str) -> bool:
        """Check if file contains JSX syntax."""
        return bool(self._jsx_tag_pattern.search(code))

    def _extract_components(self, code: str) -> List[ComponentInfo]:
        """Extract React component definitions."""
        components = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if it's a component (PascalCase name, returns JSX)
                    if self._is_component_function(node):
                        component = self._analyze_component(node, code)
                        if component:
                            components.append(component)
        except SyntaxError:
            pass
        return components

    def _is_component_function(self, node: ast.FunctionDef) -> bool:
        """Check if a function is a React component."""
        # PascalCase naming convention
        if not node.name[0].isupper():
            return False

        # Check for JSX return (look for JSX-like patterns in source)
        return True  # Simplified - in practice would need to check return type

    def _analyze_component(
        self, node: ast.FunctionDef, code: str
    ) -> Optional[ComponentInfo]:
        """Analyze a component's structure."""
        props = []
        hook_names = []
        has_hooks = False
        jsx_depth = 0
        children_count = 0

        # Extract props from destructured arguments
        for arg in node.args.args:
            props.append(arg.arg)

        # Check for hooks in function body
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    if child.func.id.startswith("use"):
                        has_hooks = True
                        hook_names.append(child.func.id)

        # Estimate JSX depth and children from source
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if node.name in line and "<" in line:
                jsx_depth += line.count("<") - line.count(">")
                children_count += line.count("{children}") + line.count("{/*")

        return ComponentInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            props=props,
            has_hooks=has_hooks,
            hook_names=hook_names,
            jsx_depth=max(0, jsx_depth),
            children_count=children_count,
        )

    def _extract_hooks(self, code: str) -> Dict[str, int]:
        """Extract hook usage counts."""
        hook_usage = {}
        for pattern, hook_name in self.HOOK_PATTERNS:
            matches = re.findall(pattern, code)
            if matches:
                hook_usage[hook_name] = len(matches)
        return hook_usage

    def _extract_structural_patterns(self, code: str) -> List[str]:
        """Extract structural patterns that should be discounted."""
        patterns = []

        # Check for common boilerplate
        if re.search(r"import\s+.*react", code, re.IGNORECASE):
            patterns.append("react_import")
        if re.search(r"export\s+default", code):
            patterns.append("default_export")
        if re.search(r"className\s*=", code):
            patterns.append("jsx_attributes")
        if re.search(r"const\s+\w+\s*=\s*\(", code):
            patterns.append("arrow_functions")

        return patterns

    def compare_components(
        self,
        components_a: List[ComponentInfo],
        components_b: List[ComponentInfo],
    ) -> float:
        """Compare component trees between two files."""
        if not components_a or not components_b:
            return 0.0

        # Match components by name similarity
        matches = 0
        for comp_a in components_a:
            for comp_b in components_b:
                # Simple name matching (could be enhanced with fuzzy matching)
                if self._names_match(comp_a.name, comp_b.name):
                    matches += 1

        return matches / max(len(components_a), len(components_b))

    def _names_match(self, name_a: str, name_b: str) -> bool:
        """Check if component names match or are similar."""
        # Exact match
        if name_a == name_b:
            return True
        # Common renaming patterns
        if name_a.lower() == name_b.lower():
            return True
        # Remove suffixes like "Component", "View", etc.
        base_a = re.sub(r"(Component|View|Page|Screen)$", "", name_a)
        base_b = re.sub(r"(Component|View|Page|Screen)$", "", name_b)
        return base_a == base_b


def calculate_boilerplate_discount(analysis: TSXAnalysisResult) -> float:
    """Calculate discount factor for boilerplate structures.

    Returns a value between 0.0 and 1.0 that should be multiplied
    with the similarity score to discount boilerplate.
    """
    if not analysis.has_jsx:
        return 1.0

    # Count boilerplate patterns
    boilerplate_count = len(analysis.structural_patterns)

    # If mostly boilerplate, apply heavy discount
    if boilerplate_count >= 3:
        return 0.1  # 90% discount
    elif boilerplate_count >= 2:
        return 0.3  # 70% discount
    elif boilerplate_count >= 1:
        return 0.6  # 40% discount

    return 1.0


def analyze_tsx_similarity(code_a: str, code_b: str) -> Dict[str, float]:
    """Analyze TSX/JSX similarity with component-aware logic.

    Returns dictionary with:
    - component_similarity: Component tree similarity
    - boilerplate_similarity: Boilerplate structure similarity (to discount)
    - has_jsx: Whether both files have JSX
    - discount_factor: Factor to apply to similarity score
    """
    analyzer = TSXAnalyzer()

    analysis_a = analyzer.analyze(code_a)
    analysis_b = analyzer.analyze(code_b)

    component_sim = analyzer.compare_components(
        analysis_a.component_tree,
        analysis_b.component_tree,
    )

    # Calculate boilerplate similarity
    boilerplate_sim = 0.0
    if analysis_a.has_jsx and analysis_b.has_jsx:
        common_patterns = set(analysis_a.structural_patterns) & set(
            analysis_b.structural_patterns
        )
        boilerplate_sim = len(common_patterns) / max(
            len(analysis_a.structural_patterns), 1
        )

    # Calculate discount factor
    discount_factor = calculate_boilerplate_discount(analysis_a)
    if analysis_b.has_jsx:
        discount_factor = min(
            discount_factor, calculate_boilerplate_discount(analysis_b)
        )

    return {
        "component_similarity": component_sim,
        "boilerplate_similarity": boilerplate_sim,
        "has_jsx": analysis_a.has_jsx and analysis_b.has_jsx,
        "discount_factor": discount_factor,
    }
