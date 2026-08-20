"""Control Flow Visualization for plagiarism detection.

This module generates visual representations of control flow structures
that help professors understand the structural similarity between submissions.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class ControlFlowNode:
    """Represents a node in the control flow tree."""

    node_type: str
    line_number: int
    children: list[ControlFlowNode] = field(default_factory=list)

    def add_child(self, child: ControlFlowNode) -> None:
        self.children.append(child)

    def to_string(self, indent: int = 0) -> str:
        """Convert to indented string representation."""
        prefix = "  " * indent
        result = f"{prefix}{self.node_type}"
        if self.line_number > 0:
            result += f" (line {self.line_number})"
        result += "\n"

        for child in self.children:
            result += child.to_string(indent + 1)

        return result


@dataclass
class ControlFlowTree:
    """Control flow tree for a code file."""

    root: ControlFlowNode | None = None
    total_nodes: int = 0
    depth: int = 0

    def get_structure_signature(self) -> list[str]:
        """Get a signature of the control flow structure."""
        if not self.root:
            return []
        return self._collect_structure(self.root)

    def _collect_structure(self, node: ControlFlowNode) -> list[str]:
        """Recursively collect structure signature."""
        result = [node.node_type]
        for child in node.children:
            result.extend(self._collect_structure(child))
        return result


class ControlFlowVisualizer:
    """Generates control flow visualizations from source code."""

    CONTROL_STRUCTURES = {"If", "For", "While", "With", "Try", "IfExp"}

    def __init__(self) -> None:
        self._cache: dict[str, ControlFlowTree] = {}

    def analyze(self, code: str, filename: str = "") -> ControlFlowTree:
        """Analyze control flow of source code.

        Args:
            code: Source code string.
            filename: Optional filename for caching.

        Returns:
            ControlFlowTree representing the control flow structure.
        """
        cache_key = filename if filename else code[:100]
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            tree = ast.parse(code)
            root = self._build_tree(tree)
            cf_tree = ControlFlowTree(
                root=root,
                total_nodes=self._count_nodes(root),
                depth=self._compute_depth(root),
            )
            if filename:
                self._cache[cache_key] = cf_tree
            return cf_tree
        except SyntaxError:
            return ControlFlowTree()

    def _build_tree(
        self, tree: ast.AST, parent: ControlFlowNode | None = None
    ) -> ControlFlowNode | None:
        """Build control flow tree from AST."""
        root = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                cf_node = ControlFlowNode(
                    node_type=type(node).__name__,
                    line_number=getattr(node, "lineno", 0),
                )

                if parent is None:
                    root = cf_node
                else:
                    parent.add_child(cf_node)

                # Process children
                self._process_children(node, cf_node)

        return root

    def _process_children(self, node: ast.AST, parent: ControlFlowNode) -> None:
        """Process child nodes of a control structure."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_node = ControlFlowNode(
                    node_type=type(child).__name__,
                    line_number=getattr(child, "lineno", 0),
                )
                parent.add_child(child_node)
                self._process_children(child, child_node)

    def _count_nodes(self, node: ControlFlowNode | None) -> int:
        """Count total nodes in tree."""
        if not node:
            return 0
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    def _compute_depth(
        self, node: ControlFlowNode | None, current_depth: int = 0
    ) -> int:
        """Compute maximum depth of tree."""
        if not node:
            return current_depth
        max_depth = current_depth
        for child in node.children:
            depth = self._compute_depth(child, current_depth + 1)
            max_depth = max(max_depth, depth)
        return max_depth

    def compare_structures(
        self, tree_a: ControlFlowTree, tree_b: ControlFlowTree
    ) -> dict:
        """Compare two control flow trees.

        Returns:
            Dictionary with comparison metrics.
        """
        sig_a = tree_a.get_structure_signature()
        sig_b = tree_b.get_structure_signature()

        # Compute similarity
        from difflib import SequenceMatcher

        matcher = SequenceMatcher(None, sig_a, sig_b)
        similarity = matcher.ratio()

        return {
            "similarity": similarity,
            "structure_a": sig_a,
            "structure_b": sig_b,
            "nodes_a": tree_a.total_nodes,
            "nodes_b": tree_b.total_nodes,
            "depth_a": tree_a.depth,
            "depth_b": tree_b.depth,
        }


def generate_control_flow_report(
    tree_a: ControlFlowTree, tree_b: ControlFlowTree
) -> str:
    """Generate a human-readable control flow comparison report.

    Args:
        tree_a: Control flow tree for first file.
        tree_b: Control flow tree for second file.

    Returns:
        Formatted report string.
    """
    visualizer = ControlFlowVisualizer()
    comparison = visualizer.compare_structures(tree_a, tree_b)

    lines = ["Control Flow Visualization:"]
    lines.append("")
    lines.append(f"Similarity: {comparison['similarity']:.1%}")
    lines.append("")
    lines.append(
        f"File A: {comparison['nodes_a']} control nodes, depth {comparison['depth_a']}"
    )
    lines.append(
        f"File B: {comparison['nodes_b']} control nodes, depth {comparison['depth_b']}"
    )
    lines.append("")

    if tree_a.root:
        lines.append("Structure A:")
        lines.append(tree_a.root.to_string())

    if tree_b.root:
        lines.append("Structure B:")
        lines.append(tree_b.root.to_string())

    return "\n".join(lines)
