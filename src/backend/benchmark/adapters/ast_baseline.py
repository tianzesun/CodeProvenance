"""
AST baseline adapter.

Abstract Syntax Tree structural similarity baseline detector.
Used as an intermediate reference baseline for benchmark validation.
"""
from __future__ import annotations

from typing import Any, Dict, List
import ast
from collections import Counter

from .base_adapter import BaseAdapter


class ASTBaselineAdapter(BaseAdapter):
    """
    AST baseline detector using node type histogram comparison.
    This is an intermediate performance baseline.
    """

    name = "ast_baseline"
    version = "1.0.0"

    def run(self, dataset: Any) -> Dict[str, Any]:
        """Run AST baseline detection on dataset."""
        predictions = {}

        for pair in dataset.pairs:
            score = self._calculate_ast_similarity(pair.code_a, pair.code_b)
            predictions[f"{pair.id}"] = score

        return predictions

    def _calculate_ast_similarity(self, code_a: str, code_b: str) -> float:
        """Calculate similarity based on AST node type histograms."""
        try:
            tree_a = ast.parse(code_a)
            tree_b = ast.parse(code_b)
        except SyntaxError:
            return 0.0

        hist_a = Counter(self._flatten_ast_types(tree_a))
        hist_b = Counter(self._flatten_ast_types(tree_b))

        if not hist_a or not hist_b:
            return 0.0

        union = hist_a | hist_b
        intersection = hist_a & hist_b

        total_union = sum(union.values())
        total_intersection = sum(intersection.values())

        return total_intersection / total_union if total_union > 0 else 0.0

    def _flatten_ast_types(self, node: ast.AST) -> List[str]:
        """Recursively flatten AST into node type names."""
        types = [type(node).__name__]

        for child in ast.iter_child_nodes(node):
            types.extend(self._flatten_ast_types(child))

        return types
