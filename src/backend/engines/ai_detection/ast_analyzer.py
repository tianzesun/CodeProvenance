"""AST-based structural analysis for AI detection.

Uses Abstract Syntax Trees to detect AI-typical code patterns that are
immune to variable renaming, comment removal, and other surface-level obfuscation.

Key insight: AI models generate code with distinctive structural patterns:
- Uniform function complexity (all functions ~15-25 lines)
- Perfect import organization (alphabetical, grouped by type)
- Balanced nesting depth (rarely deep, rarely flat)
- Defensive patterns (try/except everywhere, explicit None checks)
- Dead code presence (unreachable statements)
"""

from __future__ import annotations

import ast
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ASTFeatures:
    """Structural features extracted from AST."""

    function_count: int
    class_count: int
    avg_function_length: float
    function_length_cv: float  # Coefficient of variation (uniformity measure)
    max_nesting_depth: int
    avg_nesting_depth: float
    import_clustering_score: float  # 1.0 = perfect clustering
    dead_code_count: int
    defensive_pattern_count: int  # try/except, None checks
    docstring_coverage: float  # Ratio of documented functions
    type_hint_coverage: float
    complexity_uniformity: float  # McCabe complexity uniformity

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for JSON serialization."""
        return {
            "function_count": self.function_count,
            "class_count": self.class_count,
            "avg_function_length": round(self.avg_function_length, 2),
            "function_length_cv": round(self.function_length_cv, 3),
            "max_nesting_depth": self.max_nesting_depth,
            "avg_nesting_depth": round(self.avg_nesting_depth, 2),
            "import_clustering_score": round(self.import_clustering_score, 3),
            "dead_code_count": self.dead_code_count,
            "defensive_pattern_count": self.defensive_pattern_count,
            "docstring_coverage": round(self.docstring_coverage, 3),
            "type_hint_coverage": round(self.type_hint_coverage, 3),
            "complexity_uniformity": round(self.complexity_uniformity, 3),
        }


class ASTAnalyzer:
    """Extract structural features from code AST for AI detection."""

    def analyze(self, code: str, language: str = "python") -> ASTFeatures:
        """Extract AST-based features from code.

        Args:
            code: Source code to analyze
            language: Programming language (currently Python only)

        Returns:
            ASTFeatures with structural measurements
        """
        if language != "python":
            # Return default features for unsupported languages
            return ASTFeatures(
                function_count=0,
                class_count=0,
                avg_function_length=0.0,
                function_length_cv=0.0,
                max_nesting_depth=0,
                avg_nesting_depth=0.0,
                import_clustering_score=0.0,
                dead_code_count=0,
                defensive_pattern_count=0,
                docstring_coverage=0.0,
                type_hint_coverage=0.0,
                complexity_uniformity=0.0,
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Failed to parse code: {e}")
            return self._default_features()

        # Extract various metrics
        functions = self._find_functions(tree)
        classes = self._find_classes(tree)

        return ASTFeatures(
            function_count=len(functions),
            class_count=len(classes),
            avg_function_length=self._avg_function_length(functions),
            function_length_cv=self._function_length_cv(functions),
            max_nesting_depth=self._max_nesting_depth(tree),
            avg_nesting_depth=self._avg_nesting_depth(tree),
            import_clustering_score=self._import_clustering(tree),
            dead_code_count=self._count_dead_code(tree),
            defensive_pattern_count=self._count_defensive_patterns(tree),
            docstring_coverage=self._docstring_coverage(functions, classes),
            type_hint_coverage=self._type_hint_coverage(functions),
            complexity_uniformity=self._complexity_uniformity(functions),
        )

    def compute_ai_score(self, features: ASTFeatures) -> float:
        """Convert AST features to AI likelihood score [0, 1].

        AI-typical patterns:
        - Low function_length_cv (uniform lengths)
        - High import_clustering (perfect organization)
        - High defensive_pattern_count (overly cautious)
        - High docstring_coverage (documents everything)
        - High complexity_uniformity (all functions similar complexity)

        Args:
            features: AST features to score

        Returns:
            AI likelihood score [0, 1]
        """
        score = 0.0

        # Uniform function lengths (CV < 0.3 is suspicious)
        if features.function_count >= 3:
            if features.function_length_cv < 0.2:
                score += 0.25
            elif features.function_length_cv < 0.4:
                score += 0.15

        # Perfect import clustering
        if features.import_clustering_score > 0.9:
            score += 0.20
        elif features.import_clustering_score > 0.7:
            score += 0.10

        # Excessive defensive patterns
        if features.function_count > 0:
            defensive_ratio = features.defensive_pattern_count / features.function_count
            if defensive_ratio > 0.7:
                score += 0.15
            elif defensive_ratio > 0.4:
                score += 0.08

        # High docstring coverage
        if features.docstring_coverage > 0.8:
            score += 0.15
        elif features.docstring_coverage > 0.6:
            score += 0.08

        # Complexity uniformity
        if features.complexity_uniformity > 0.8:
            score += 0.15
        elif features.complexity_uniformity > 0.6:
            score += 0.08

        # Dead code presence
        if features.dead_code_count > 0:
            score += 0.10

        return min(1.0, score)

    # --- Helper methods for feature extraction ---

    @staticmethod
    def _default_features() -> ASTFeatures:
        """Return default features for unparseable code."""
        return ASTFeatures(
            function_count=0,
            class_count=0,
            avg_function_length=0.0,
            function_length_cv=0.0,
            max_nesting_depth=0,
            avg_nesting_depth=0.0,
            import_clustering_score=0.0,
            dead_code_count=0,
            defensive_pattern_count=0,
            docstring_coverage=0.0,
            type_hint_coverage=0.0,
            complexity_uniformity=0.0,
        )

    @staticmethod
    def _find_functions(tree: ast.AST) -> list[ast.FunctionDef]:
        """Find all function definitions."""
        return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    @staticmethod
    def _find_classes(tree: ast.AST) -> list[ast.ClassDef]:
        """Find all class definitions."""
        return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    @staticmethod
    def _function_length(func: ast.FunctionDef) -> int:
        """Count lines in a function (statements + docstring)."""
        return len(list(ast.walk(func)))

    def _avg_function_length(self, functions: list[ast.FunctionDef]) -> float:
        """Average function length in AST nodes."""
        if not functions:
            return 0.0
        lengths = [self._function_length(f) for f in functions]
        return sum(lengths) / len(lengths)

    def _function_length_cv(self, functions: list[ast.FunctionDef]) -> float:
        """Coefficient of variation for function lengths."""
        if len(functions) < 2:
            return 0.0

        lengths = [self._function_length(f) for f in functions]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        std = variance**0.5
        return std / mean

    @staticmethod
    def _nesting_depth(node: ast.AST, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth from a node."""
        nesting_nodes = (
            ast.If,
            ast.For,
            ast.While,
            ast.With,
            ast.Try,
            ast.FunctionDef,
            ast.ClassDef,
        )

        if isinstance(node, nesting_nodes):
            current_depth += 1

        max_depth = current_depth
        for child in ast.iter_child_nodes(node):
            child_depth = ASTAnalyzer._nesting_depth(child, current_depth)
            max_depth = max(max_depth, child_depth)

        return max_depth

    def _max_nesting_depth(self, tree: ast.AST) -> int:
        """Maximum nesting depth in the entire AST."""
        return self._nesting_depth(tree)

    def _avg_nesting_depth(self, tree: ast.AST) -> float:
        """Average nesting depth across all statements."""
        depths = []

        def collect_depths(node: ast.AST, depth: int = 0):
            nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try)
            if isinstance(node, nesting_nodes):
                depth += 1
                depths.append(depth)
            for child in ast.iter_child_nodes(node):
                collect_depths(child, depth)

        collect_depths(tree)
        return sum(depths) / len(depths) if depths else 0.0

    @staticmethod
    def _import_clustering(tree: ast.AST) -> float:
        """Measure how well imports are clustered at the top.

        Returns 1.0 if all imports are at the top, 0.0 if scattered.
        """
        imports = []
        non_imports = []

        for i, node in enumerate(tree.body if hasattr(tree, "body") else []):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(i)
            else:
                non_imports.append(i)

        if not imports:
            return 1.0  # No imports = perfect clustering

        # Check if all imports come before all non-imports
        if not non_imports or max(imports) < min(non_imports):
            return 1.0

        # Calculate clustering score based on how early imports appear
        max_idx = max(imports) if imports else 0
        total_nodes = len(tree.body) if hasattr(tree, "body") else 1
        return 1.0 - (max_idx / max(total_nodes, 1))

    @staticmethod
    def _count_dead_code(tree: ast.AST) -> int:
        """Count unreachable code statements."""
        dead_count = 0

        def check_block(statements: list[ast.stmt]):
            nonlocal dead_count
            found_return = False
            for stmt in statements:
                if found_return:
                    dead_count += 1
                if isinstance(stmt, ast.Return):
                    found_return = True

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                check_block(node.body)

        return dead_count

    @staticmethod
    def _count_defensive_patterns(tree: ast.AST) -> int:
        """Count defensive programming patterns (try/except, None checks)."""
        count = 0

        for node in ast.walk(tree):
            # Count try/except blocks
            if isinstance(node, ast.Try):
                count += 1

            # Count explicit None checks
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    if isinstance(op, (ast.Is, ast.IsNot)):
                        # Check if comparing to None
                        for comp in node.comparators:
                            if isinstance(comp, ast.Constant) and comp.value is None:
                                count += 1

        return count

    @staticmethod
    def _docstring_coverage(functions: list[ast.FunctionDef], classes: list[ast.ClassDef]) -> float:
        """Ratio of functions/classes with docstrings."""
        total = len(functions) + len(classes)
        if total == 0:
            return 0.0

        documented = 0
        for func in functions:
            if ast.get_docstring(func):
                documented += 1
        for cls in classes:
            if ast.get_docstring(cls):
                documented += 1

        return documented / total

    @staticmethod
    def _type_hint_coverage(functions: list[ast.FunctionDef]) -> float:
        """Ratio of function parameters with type hints."""
        total_params = 0
        typed_params = 0

        for func in functions:
            for arg in func.args.args:
                if arg.arg not in ("self", "cls"):
                    total_params += 1
                    if arg.annotation is not None:
                        typed_params += 1

        return typed_params / total_params if total_params > 0 else 0.0

    def _complexity_uniformity(self, functions: list[ast.FunctionDef]) -> float:
        """Measure uniformity of cyclomatic complexity across functions.

        Returns 1.0 if all functions have similar complexity, 0.0 if highly varied.
        """
        if len(functions) < 2:
            return 0.0

        complexities = [self._cyclomatic_complexity(f) for f in functions]
        mean = sum(complexities) / len(complexities)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in complexities) / len(complexities)
        cv = (variance**0.5) / mean

        # Low CV = uniform = high score
        return max(0.0, min(1.0, 1.0 - cv / 2.0))

    @staticmethod
    def _cyclomatic_complexity(func: ast.FunctionDef) -> int:
        """Calculate McCabe cyclomatic complexity for a function."""
        complexity = 1  # Base complexity

        for node in ast.walk(func):
            # Decision points
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

        return complexity


# Singleton instance
_global_analyzer: ASTAnalyzer | None = None


def get_analyzer() -> ASTAnalyzer:
    """Get or create the global AST analyzer instance."""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = ASTAnalyzer()
    return _global_analyzer


def analyze_ast(code: str, language: str = "python") -> ASTFeatures:
    """Convenience function: extract AST features from code."""
    analyzer = get_analyzer()
    return analyzer.analyze(code, language)


def compute_ast_score(code: str, language: str = "python") -> dict[str, Any]:
    """Convenience function: compute AI score from AST analysis."""
    analyzer = get_analyzer()
    features = analyzer.analyze(code, language)
    score = analyzer.compute_ai_score(features)
    return {
        "ai_score": round(score, 3),
        "features": features.to_dict(),
    }
