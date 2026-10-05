"""AST-based structural analysis for AI detection.

Uses Abstract Syntax Trees to measure structural traits that survive variable renaming and
comment removal:
- Uniform function length / complexity
- Imports gathered at the top, in order
- Defensive patterns (try/except, explicit None checks) inside functions
- Documentation and annotation coverage
- Unreachable statements

Read these as WEAK indicators. Several of them (docstring coverage, type-hint coverage,
imports at the top, uniform small helpers) are exactly what a course's style guide asks of
students - the UofT CS1 design recipe requires a docstring and type annotations on every
function - so on such courses they describe well-taught students at least as often as machines.
Calibrate on your own course data and never use the score alone.
"""

from __future__ import annotations

import ast
import logging
import warnings
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Source longer than this is not parsed (an unbounded ``ast.parse`` is a cheap DoS).
MAX_SOURCE_CHARS = 1_000_000
_PYTHON_NAMES = frozenset({"python", "py", "python3"})

_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_CONTROL_NODES = tuple(
    getattr(ast, name)
    for name in ("If", "For", "AsyncFor", "While", "With", "AsyncWith", "Try", "TryStar", "Match")
    if hasattr(ast, name)
)
_TRY_NODES = tuple(getattr(ast, name) for name in ("Try", "TryStar") if hasattr(ast, name))


@dataclass
class ASTFeatures:
    """Structural features extracted from AST."""

    function_count: int
    class_count: int
    avg_function_length: float  # lines
    function_length_cv: float  # coefficient of variation (uniformity measure)
    max_nesting_depth: int  # control-flow nesting
    avg_nesting_depth: float
    import_clustering_score: float  # 1.0 = imports at the top and in order
    dead_code_count: int
    defensive_pattern_count: int  # try/except and None checks inside functions
    docstring_coverage: float  # ratio of documented functions/classes
    type_hint_coverage: float  # annotated parameters + return types
    complexity_uniformity: float  # McCabe complexity uniformity
    #: False when the source could not be analysed (not Python, syntax error, too large).
    #: All other fields are then zero and mean "unknown", NOT "human-like".
    parse_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
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
            "parse_ok": self.parse_ok,
        }


def _parse(code: str) -> ast.AST | None:
    """Parse Python source; None when it cannot be (instead of raising)."""
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_SOURCE_CHARS:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # SyntaxWarning (invalid escapes) is noise here
            return ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        # ValueError: NUL bytes; Recursion/MemoryError: pathological nesting. All of these used
        # to escape (only SyntaxError was caught) and fail the whole analysis.
        logger.debug("AST parse failed: %s", exc)
        return None


def _cv(values: list[float]) -> float:
    """Coefficient of variation (population); 0.0 when undefined."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0.0
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 / mean


class ASTAnalyzer:
    """Extract structural features from code AST for AI detection."""

    def analyze(self, code: str, language: str = "python") -> ASTFeatures:
        """Extract AST-based features from code.

        Args:
            code: Source code to analyze
            language: Programming language (Python only; any case)

        Returns:
            ASTFeatures. ``parse_ok`` is False for unsupported languages and unparseable code.
        """
        if str(language or "python").strip().lower() not in _PYTHON_NAMES:
            return self._default_features()
        tree = _parse(code)
        if tree is None:
            return self._default_features()

        functions = self._find_functions(tree)
        classes = self._find_classes(tree)
        max_depth, avg_depth = self._nesting_stats(tree)

        return ASTFeatures(
            function_count=len(functions),
            class_count=len(classes),
            avg_function_length=self._avg_function_length(functions),
            function_length_cv=self._function_length_cv(functions),
            max_nesting_depth=max_depth,
            avg_nesting_depth=avg_depth,
            import_clustering_score=self._import_clustering(tree),
            dead_code_count=self._count_dead_code(tree),
            defensive_pattern_count=self._count_defensive_patterns(tree),
            docstring_coverage=self._docstring_coverage(functions, classes),
            type_hint_coverage=self._type_hint_coverage(functions),
            complexity_uniformity=self._complexity_uniformity(functions),
        )

    def compute_ai_score(self, features: ASTFeatures) -> float:
        """Convert AST features to an AI-likelihood score in [0, 1].

        Returns 0.0 when ``features.parse_ok`` is False: no analysis, no evidence (callers should
        check ``parse_ok`` and omit the signal rather than treat 0.0 as "human").
        """
        if not features.parse_ok:
            return 0.0
        score = 0.0

        # Uniform function lengths (CV < 0.3 is suspicious)
        if features.function_count >= 3:
            if features.function_length_cv < 0.2:
                score += 0.25
            elif features.function_length_cv < 0.4:
                score += 0.15

        # Imports gathered at the top and in order
        if features.import_clustering_score > 0.9:
            score += 0.20
        elif features.import_clustering_score > 0.7:
            score += 0.10

        # Defensive patterns inside functions
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

        # Unreachable statements
        if features.dead_code_count > 0:
            score += 0.10

        return min(1.0, score)

    # --- Helper methods for feature extraction ---

    @staticmethod
    def _default_features() -> ASTFeatures:
        """Features for unsupported or unparseable code (``parse_ok=False``)."""
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
            parse_ok=False,
        )

    @staticmethod
    def _find_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Find all function definitions, async ones included (they were ignored)."""
        return [node for node in ast.walk(tree) if isinstance(node, _FUNC_NODES)]

    @staticmethod
    def _find_classes(tree: ast.AST) -> list[ast.ClassDef]:
        """Find all class definitions."""
        return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    @staticmethod
    def _function_length(func: ast.AST) -> int:
        """Lines spanned by a function (it counted AST nodes while documented as lines)."""
        start = getattr(func, "lineno", None)
        end = getattr(func, "end_lineno", None)
        if isinstance(start, int) and isinstance(end, int) and end >= start:
            return end - start + 1
        return sum(1 for _ in ast.walk(func))

    def _avg_function_length(self, functions: list) -> float:
        """Average function length in lines."""
        if not functions:
            return 0.0
        return sum(self._function_length(f) for f in functions) / len(functions)

    def _function_length_cv(self, functions: list) -> float:
        """Coefficient of variation for function lengths."""
        return _cv([float(self._function_length(f)) for f in functions])

    @staticmethod
    def _nesting_stats(tree: ast.AST) -> tuple[int, float]:
        """(max, average) control-flow nesting depth, computed iteratively.

        The recursive versions overflowed the stack on deeply nested code, and ``max`` counted
        function/class definitions as nesting while ``avg`` did not.
        """
        depths: list[int] = []
        stack: list[tuple[ast.AST, int]] = [(tree, 0)]
        while stack:
            node, depth = stack.pop()
            if isinstance(node, _CONTROL_NODES):
                depth += 1
                depths.append(depth)
            for child in ast.iter_child_nodes(node):
                stack.append((child, depth))
        return (max(depths) if depths else 0), (sum(depths) / len(depths) if depths else 0.0)

    def _max_nesting_depth(self, tree: ast.AST) -> int:
        """Maximum control-flow nesting depth in the entire AST."""
        return self._nesting_stats(tree)[0]

    def _avg_nesting_depth(self, tree: ast.AST) -> float:
        """Average control-flow nesting depth."""
        return self._nesting_stats(tree)[1]

    @staticmethod
    def _import_clustering(tree: ast.AST) -> float:
        """How tidy the import block is: at the top (after the docstring) and in order.

        Returns 0.0 (no evidence) when there are fewer than three imports: a file with NO
        imports used to score a perfect 1.0 and so got +0.20 AI score, and a module docstring
        before the imports counted as "code before imports".
        """
        body = list(getattr(tree, "body", []))
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]  # module docstring

        positions = [i for i, node in enumerate(body) if isinstance(node, (ast.Import, ast.ImportFrom))]
        if len(positions) < 3:
            return 0.0

        last = positions[-1]
        at_top = len(positions) / (last + 1)  # 1.0 when nothing sits between the imports

        def key(node: ast.AST) -> str:
            if isinstance(node, ast.ImportFrom):
                return "." * (node.level or 0) + (node.module or "")
            return node.names[0].name if getattr(node, "names", None) else ""

        keys = [key(body[i]) for i in positions]
        pairs = list(zip(keys, keys[1:]))
        ordered = sum(1 for a, b in pairs if a.lower() <= b.lower()) / len(pairs)
        return at_top * (0.5 + 0.5 * ordered)

    @staticmethod
    def _count_dead_code(tree: ast.AST) -> int:
        """Count statements that follow return/raise/break/continue in the same block.

        Every statement list (if/else/for/try/with bodies, handlers) is checked; only the
        top level of function bodies and only ``return`` used to be.
        """
        dead = 0
        terminators = (ast.Return, ast.Raise, ast.Break, ast.Continue)
        for node in ast.walk(tree):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list) or not block or not isinstance(block[0], ast.stmt):
                    continue
                seen_terminator = False
                for stmt in block:
                    if seen_terminator:
                        dead += 1
                    elif isinstance(stmt, terminators):
                        seen_terminator = True
        return dead

    @staticmethod
    def _count_defensive_patterns(tree: ast.AST) -> int:
        """Count try/except blocks and explicit None comparisons INSIDE functions.

        (Module-level ``try`` blocks used to be counted against the number of functions, and
        every comparator of a comparison was counted for every operator.)
        """
        count = 0
        stack: list[tuple[ast.AST, bool]] = [(tree, False)]
        while stack:
            node, in_function = stack.pop()
            if in_function:
                if isinstance(node, _TRY_NODES):
                    count += 1
                elif isinstance(node, ast.Compare):
                    for op, comparator in zip(node.ops, node.comparators):
                        if (
                            isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq))
                            and isinstance(comparator, ast.Constant)
                            and comparator.value is None
                        ):
                            count += 1
            child_in_function = in_function or isinstance(node, _FUNC_NODES)
            for child in ast.iter_child_nodes(node):
                stack.append((child, child_in_function))
        return count

    @staticmethod
    def _docstring_coverage(functions: list, classes: list) -> float:
        """Ratio of functions/classes with docstrings."""
        total = len(functions) + len(classes)
        if total == 0:
            return 0.0
        documented = sum(1 for node in [*functions, *classes] if ast.get_docstring(node))
        return documented / total

    @staticmethod
    def _type_hint_coverage(functions: list) -> float:
        """Ratio of annotated parameter and return slots (all parameter kinds, not just ``args``)."""
        slots = 0
        typed = 0
        for func in functions:
            arguments = func.args
            params = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
            params += [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
            for arg in params:
                if arg.arg in ("self", "cls"):
                    continue
                slots += 1
                typed += arg.annotation is not None
            slots += 1  # return type
            typed += func.returns is not None
        return typed / slots if slots else 0.0

    def _complexity_uniformity(self, functions: list) -> float:
        """Uniformity of cyclomatic complexity across functions (1.0 = all alike).

        Functions that are all trivial (mean complexity < 2: getters, one-line helpers) are
        uninformative - they are all alike for every author - and score 0.0.
        """
        if len(functions) < 2:
            return 0.0
        complexities = [float(self._cyclomatic_complexity(f)) for f in functions]
        if sum(complexities) / len(complexities) < 2.0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - _cv(complexities) / 2.0))

    @staticmethod
    def _cyclomatic_complexity(func: ast.AST) -> int:
        """McCabe complexity of one function (nested functions are counted on their own)."""
        complexity = 1
        stack = list(ast.iter_child_nodes(func))
        while stack:
            node = stack.pop()
            if isinstance(node, (*_FUNC_NODES, ast.Lambda)):
                continue
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.IfExp)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, ast.comprehension):
                complexity += 1 + len(node.ifs)
            stack.extend(ast.iter_child_nodes(node))
        return complexity


# Singleton instance
_global_analyzer: ASTAnalyzer | None = None


def get_analyzer() -> ASTAnalyzer:
    """Get or create the global AST analyzer instance (the analyzer is stateless)."""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = ASTAnalyzer()
    return _global_analyzer


def analyze_ast(code: str, language: str = "python") -> ASTFeatures:
    """Convenience function: extract AST features from code."""
    return get_analyzer().analyze(code, language)


def compute_ast_score(code: str, language: str = "python") -> dict[str, Any]:
    """Convenience function: AI score from AST analysis.

    ``available`` is False (and ``ai_score`` None) when the code could not be analysed.
    """
    analyzer = get_analyzer()
    features = analyzer.analyze(code, language)
    if not features.parse_ok:
        return {"available": False, "ai_score": None, "features": features.to_dict()}
    return {
        "available": True,
        "ai_score": round(analyzer.compute_ai_score(features), 3),
        "features": features.to_dict(),
    }
