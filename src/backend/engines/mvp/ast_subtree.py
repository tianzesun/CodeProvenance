"""Normalized AST subtree hashing for structure-aware plagiarism detection."""

from __future__ import annotations

import ast
import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ASTSubtreeHashResult:
    """Subtree hash multiset and parse status."""

    hashes: List[str]
    parse_error: str = ""


class _ASTNormalizer(ast.NodeTransformer):
    """Normalize identifiers and literals inside a Python AST."""

    def __init__(self) -> None:
        self.identifier_map: Dict[str, str] = {}

    def visit_Name(self, node: ast.Name) -> ast.AST:
        """Normalize variable names."""
        node.id = self._identifier(node.id)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        """Normalize argument names."""
        node.arg = self._identifier(node.arg)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        """Normalize function names and descend into the body."""
        node.name = self._identifier(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        """Normalize async function names and descend into the body."""
        node.name = self._identifier(node.name)
        self.generic_visit(node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        """Normalize literal values while preserving broad literal type."""
        if isinstance(node.value, str):
            node.value = "LIT_STR"
        elif isinstance(node.value, (int, float, complex)):
            node.value = 0
        elif isinstance(node.value, bool):
            node.value = bool(node.value)
        return node

    def _identifier(self, value: str) -> str:
        """Map original identifiers to stable placeholders."""
        if value not in self.identifier_map:
            self.identifier_map[value] = f"ID_{len(self.identifier_map)}"
        return self.identifier_map[value]


class ASTSubtreeHasher:
    """Compute normalized AST subtree hashes and multiset similarity."""

    def __init__(self, min_subtree_size: int = 2, max_subtree_size: int = 32) -> None:
        self.min_subtree_size = min_subtree_size
        self.max_subtree_size = max_subtree_size

    def hash_source(self, source: str) -> ASTSubtreeHashResult:
        """Parse, normalize, and hash all eligible AST subtrees."""
        try:
            tree = ast.parse(source or "")
        except SyntaxError as exc:
            return ASTSubtreeHashResult([], parse_error=str(exc))

        tree = _ASTNormalizer().visit(tree)
        ast.fix_missing_locations(tree)

        hashes: List[str] = []
        self._hash_node(tree, hashes)
        return ASTSubtreeHashResult(hashes)

    def similarity(self, source_a: str, source_b: str) -> float:
        """Return multiset Jaccard similarity between normalized subtree hashes."""
        hashes_a = self.hash_source(source_a).hashes
        hashes_b = self.hash_source(source_b).hashes
        if not hashes_a and not hashes_b:
            return 1.0
        if not hashes_a or not hashes_b:
            return 0.0

        counts_a = Counter(hashes_a)
        counts_b = Counter(hashes_b)
        all_hashes = set(counts_a) | set(counts_b)
        intersection = sum(min(counts_a[item], counts_b[item]) for item in all_hashes)
        union = sum(max(counts_a[item], counts_b[item]) for item in all_hashes)
        return intersection / union if union else 0.0

    def _hash_node(self, node: ast.AST, output: List[str]) -> Tuple[str, int]:
        """Return hash and subtree size for one AST node."""
        child_results = [
            self._hash_node(child, output) for child in ast.iter_child_nodes(node)
        ]
        child_hashes = [item[0] for item in child_results]
        size = 1 + sum(item[1] for item in child_results)
        payload = (
            node.__class__.__name__,
            self._stable_fields(node),
            tuple(child_hashes),
        )
        digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
        if self.min_subtree_size <= size <= self.max_subtree_size:
            output.append(digest)
        return digest, size

    def _stable_fields(self, node: ast.AST) -> tuple:
        """Return stable scalar fields for hashing, excluding location metadata."""
        ignored = {"lineno", "col_offset", "end_lineno", "end_col_offset", "ctx"}
        fields = []
        for name, value in ast.iter_fields(node):
            if name in ignored or isinstance(value, (list, ast.AST)):
                continue
            fields.append((name, value))
        return tuple(sorted(fields))
