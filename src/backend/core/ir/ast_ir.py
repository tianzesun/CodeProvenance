"""
AST-based Intermediate Representation.

Provides tree-based representation of code structure using Abstract Syntax Trees.
"""

import ast as python_ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .base_ir import BaseIR, IRMetadata, normalize_language


@dataclass
class ASTNode:
    """Represents a node in the Abstract Syntax Tree.

    Attributes:
        node_type: Type of AST node (e.g., 'FunctionDef', 'If', 'For')
        value: String value of the node (e.g., function name, operator)
        children: List of child AST nodes
        line_start: Starting line number in source (1-indexed)
        line_end: Ending line number in source (1-indexed)
        col_start: Starting column number (0-indexed, in characters)
        col_end: Ending column number (0-indexed)
        metadata: Additional metadata about the node (e.g. ``const_type`` for
            Python constants, ``calls`` for Java/JS function nodes)

    All traversal helpers are iterative: the recursive versions raised
    RecursionError on deep trees (a long ``a + b + c + ...`` chain nests one
    level per operand).
    """

    node_type: str
    value: str
    children: list["ASTNode"] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    col_start: int = 0
    col_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def iter_nodes(self) -> Iterator["ASTNode"]:
        """Pre-order (document order) iteration over this subtree."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def to_dict(self) -> dict[str, Any]:
        """Serialize AST node to dictionary (iteratively)."""
        root: dict[str, Any] = {}
        stack: list[tuple[ASTNode, dict[str, Any]]] = [(self, root)]
        while stack:
            node, out = stack.pop()
            out.update(
                node_type=node.node_type,
                value=node.value,
                children=[{} for _ in node.children],
                line_start=node.line_start,
                line_end=node.line_end,
                col_start=node.col_start,
                col_end=node.col_end,
                metadata=node.metadata,
            )
            stack.extend(zip(node.children, out["children"], strict=True))
        return root

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ASTNode":
        """Deserialize AST node from dictionary (iteratively)."""

        def make(d: dict[str, Any]) -> "ASTNode":
            return cls(
                node_type=d["node_type"],
                value=d["value"],
                line_start=d.get("line_start", 0),
                line_end=d.get("line_end", 0),
                col_start=d.get("col_start", 0),
                col_end=d.get("col_end", 0),
                metadata=d.get("metadata", {}),
            )

        root = make(data)
        stack = [(root, data)]
        while stack:
            node, d = stack.pop()
            for child_data in d.get("children", []):
                child = make(child_data)
                node.children.append(child)
                stack.append((child, child_data))
        return root

    def get_all_node_types(self) -> set[str]:
        """Get all unique node types in this subtree."""
        return {n.node_type for n in self.iter_nodes()}

    def get_depth(self) -> int:
        """Get depth of this subtree."""
        deepest = 0
        stack = [(self, 1)]
        while stack:
            node, depth = stack.pop()
            deepest = max(deepest, depth)
            stack.extend((c, depth + 1) for c in node.children)
        return deepest

    def get_node_count(self) -> int:
        """Get total number of nodes in this subtree."""
        return sum(1 for _ in self.iter_nodes())

    def find_nodes_by_type(self, node_type: str) -> list["ASTNode"]:
        """Find all nodes of a specific type in this subtree (document order)."""
        return [n for n in self.iter_nodes() if n.node_type == node_type]

    def __repr__(self) -> str:
        if self.children:
            return f"ASTNode({self.node_type}, children={len(self.children)})"
        return f"ASTNode({self.node_type}, '{self.value}')"


_OP_HOLDERS = (
    python_ast.BinOp,
    python_ast.BoolOp,
    python_ast.UnaryOp,
    python_ast.AugAssign,
)


def _python_value(node: python_ast.AST) -> str:
    """The identifying string of a Python AST node (name, literal, operator)."""
    if isinstance(node, python_ast.Name):
        return node.id
    if isinstance(node, python_ast.Constant):
        return str(node.value)
    if isinstance(
        node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef, python_ast.ClassDef)
    ):
        return node.name  # async defs used to have no value
    if isinstance(node, python_ast.Attribute):
        return node.attr  # `a.b` and `a.c` were indistinguishable
    if isinstance(node, python_ast.arg):
        return node.arg
    if isinstance(node, python_ast.keyword):
        return node.arg or ""
    if isinstance(node, python_ast.alias):
        return node.name
    if isinstance(node, python_ast.ImportFrom):
        return node.module or ""
    if isinstance(node, (python_ast.Global, python_ast.Nonlocal)):
        return ",".join(node.names)
    if isinstance(node, python_ast.ExceptHandler):
        return node.name or ""
    if isinstance(node, _OP_HOLDERS):
        return type(node.op).__name__
    if isinstance(node, python_ast.Compare):
        return type(node.ops[0]).__name__ if node.ops else ""
    return ""


class ASTIR(BaseIR):
    """AST-based intermediate representation.

    Represents code as a tree structure where each node represents
    a syntactic construct (function, loop, condition, etc.).
    """

    REPRESENTATION_TYPE = "ast"

    _FUNCTION_TYPES = ("FunctionDef", "AsyncFunctionDef", "Method", "Function")
    _CLASS_TYPES = ("ClassDef", "Class")
    _CONTROL_TYPES = (
        "If", "For", "AsyncFor", "While", "Do", "IfStmt", "ForStmt", "WhileStmt",
    )  # fmt: skip

    def __init__(self, root: ASTNode, metadata: IRMetadata):
        super().__init__(metadata)
        self.root = root

    def to_dict(self) -> dict[str, Any]:
        """Serialize AST IR to dictionary."""
        return {
            "root": self.root.to_dict(),
            "node_count": self.root.get_node_count(),
            "max_depth": self.root.get_depth(),
            "node_types": sorted(self.root.get_all_node_types()),  # was set order
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], metadata: IRMetadata | None = None
    ) -> "ASTIR":
        """Deserialize AST IR from ``to_dict()`` output.

        A payload without a ``"root"`` key yields an empty placeholder IR (the
        historical behaviour); the old implementation did this for *every*
        input, silently discarding the tree.
        """
        meta = cls._resolve_metadata(data, metadata)
        if isinstance(data, dict) and "root" in data:
            root = ASTNode.from_dict(data["root"])
        else:
            root = ASTNode(node_type="Module", value="")
        return cls(root=root, metadata=meta)

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        self.root = ASTNode.from_dict(data["root"])

    def validate(self) -> bool:
        """Validate AST IR integrity (every node is a well-formed ASTNode)."""
        if not self.metadata.validate():
            return False
        if not isinstance(self.root, ASTNode):
            return False
        return all(
            isinstance(n, ASTNode)
            and isinstance(n.node_type, str)
            and isinstance(n.children, list)
            for n in self.root.iter_nodes()
        )

    @property
    def has_error(self) -> bool:
        """True if the source failed to parse (root is an ``Error`` node)."""
        return self.root.node_type == "Error"

    @classmethod
    def from_source(
        cls, source_code: str, language: str, file_path: str | None = None
    ) -> "ASTIR":
        """Create AST IR from source code.

        Raises:
            ValueError: If language is not supported
        """
        language = normalize_language(language)
        root = cls._parse_source(source_code, language)  # fail before hashing
        metadata = cls.create_metadata(source_code, language, "ast", file_path)
        return cls(root=root, metadata=metadata)

    @staticmethod
    def _parse_source(source_code: str, language: str) -> ASTNode:
        language = normalize_language(language)
        if language == "python":
            return ASTIR._parse_python(source_code)
        if language == "java":
            return ASTIR._parse_java(source_code)
        if language == "javascript":
            return ASTIR._parse_javascript(source_code)
        raise ValueError(f"Unsupported language: {language}")

    @staticmethod
    def _parse_python(source_code: str) -> ASTNode:
        """Parse Python source with the built-in ``ast`` module.

        Syntax problems yield an ``Error`` root (see :attr:`has_error`).
        """
        try:
            tree = python_ast.parse(source_code)
        except (
            SyntaxError,
            ValueError,
            RecursionError,
            OverflowError,
            MemoryError,
        ) as e:
            return ASTNode(
                node_type="Error",
                value=f"{type(e).__name__}: {e!s}",
                line_start=getattr(e, "lineno", 0) or 0,
                line_end=getattr(e, "lineno", 0) or 0,
                metadata={"error": str(e)},
            )
        return ASTIR._convert_python_ast(tree, lines=source_code.splitlines())

    @staticmethod
    def _convert_python_ast(
        node: python_ast.AST, line_offset: int = 0, lines: list[str] | None = None
    ) -> ASTNode:
        """Convert a Python ``ast`` tree to :class:`ASTNode` (iteratively).

        Python reports ``col_offset`` in UTF-8 *bytes*; when ``lines`` is given
        columns on non-ASCII lines are converted to character offsets.
        """
        non_ascii = (
            {i + 1 for i, text in enumerate(lines) if not text.isascii()}
            if lines
            else set()
        )

        def char_col(line: int, col: int) -> int:
            if line in non_ascii and lines and 0 < line <= len(lines):
                return len(
                    lines[line - 1].encode("utf-8")[:col].decode("utf-8", "ignore")
                )
            return col

        def make(n: python_ast.AST) -> ASTNode:
            lineno = getattr(n, "lineno", 0) or 0
            end_lineno = getattr(n, "end_lineno", None) or lineno
            col = getattr(n, "col_offset", 0) or 0
            end_col = getattr(n, "end_col_offset", None)
            end_col = col if end_col is None else end_col
            out = ASTNode(
                node_type=type(n).__name__,
                value=_python_value(n),
                line_start=lineno + line_offset if lineno else 0,
                line_end=end_lineno + line_offset if end_lineno else 0,
                col_start=char_col(lineno, col),
                col_end=char_col(end_lineno, end_col),
            )
            if isinstance(n, python_ast.Constant):
                out.metadata["const_type"] = type(n.value).__name__
            elif isinstance(n, python_ast.Compare):
                out.metadata["ops"] = [type(o).__name__ for o in n.ops]
            return out

        root = make(node)
        stack = [(node, root)]
        while stack:
            py_node, out = stack.pop()
            for py_child in python_ast.iter_child_nodes(py_node):
                child = make(py_child)
                out.children.append(child)
                stack.append((py_child, child))
        return root

    @staticmethod
    def _parse_java(source_code: str) -> ASTNode:
        """Parse Java into a brace-nested tree (classes, methods, control flow).

        Heuristic, not a full parser: the old line-by-line regexes produced a
        flat list in which every ``if (...)`` was a "Method" named ``if``.
        """
        from ._clike import parse_clike

        return parse_clike(source_code, "java")

    @staticmethod
    def _parse_javascript(source_code: str) -> ASTNode:
        """Parse JavaScript into a brace-nested tree (see :meth:`_parse_java`)."""
        from ._clike import parse_clike

        return parse_clike(source_code, "javascript")

    def _find_types(self, types: tuple[str, ...]) -> list[ASTNode]:
        wanted = set(types)
        return [n for n in self.root.iter_nodes() if n.node_type in wanted]

    def get_functions(self) -> list[ASTNode]:
        """All function/method definitions (the old ``or`` chain returned only
        the first non-empty category, and ignored ``async def``)."""
        return self._find_types(self._FUNCTION_TYPES)

    def get_classes(self) -> list[ASTNode]:
        """All class definitions."""
        return self._find_types(self._CLASS_TYPES)

    def get_control_flow(self) -> list[ASTNode]:
        """All control flow statements (if, for, while), in document order."""
        return self._find_types(self._CONTROL_TYPES)

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the AST."""
        node_types = self.root.get_all_node_types()
        return {
            "total_nodes": self.root.get_node_count(),
            "max_depth": self.root.get_depth(),
            "node_type_count": len(node_types),
            "node_types": sorted(node_types),
            "function_count": len(self.get_functions()),
            "class_count": len(self.get_classes()),
            "control_flow_count": len(self.get_control_flow()),
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"ASTIR(nodes={stats['total_nodes']}, depth={stats['max_depth']}, "
            f"language={self.metadata.language})"
        )
