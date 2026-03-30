"""
AST Delta Visualization Module for CodeProvenance.

Provides visual side-by-side AST comparison for understanding
structural differences between code files.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class DiffType(Enum):
    """Type of AST difference."""
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"


@dataclass
class ASTNode:
    """Represents an AST node with diff information."""
    id: str
    node_type: str
    value: Any = None
    children: List['ASTNode'] = field(default_factory=list)
    diff_type: DiffType = DiffType.UNCHANGED
    similarity_score: float = 1.0
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiffResult:
    """Result of AST diff comparison."""
    root_a: ASTNode
    root_b: ASTNode
    total_nodes_a: int
    total_nodes_b: int
    unchanged_count: int
    added_count: int
    removed_count: int
    modified_count: int
    similarity_score: float
    changes: List[Dict[str, Any]] = field(default_factory=list)


class ASTDiffGenerator:
    """
    Generates visual AST diffs for code comparison.
    
    Provides:
    - Side-by-side tree visualization
    - HTML diff output
    - JSON structured diff
    - Interactive visualization data
    """
    
    def __init__(self):
        self._node_counter = 0
    
    def generate_diff(
        self,
        ast_a: Dict[str, Any],
        ast_b: Dict[str, Any],
        threshold: float = 0.5
    ) -> DiffResult:
        """
        Generate AST diff between two code files.
        
        Args:
            ast_a: First AST dictionary
            ast_b: Second AST dictionary
            threshold: Similarity threshold for matching nodes
            
        Returns:
            DiffResult with detailed diff information
        """
        self._node_counter = 0
        
        # Convert to ASTNode trees
        root_a = self._dict_to_node(ast_a, None)
        root_b = self._dict_to_node(ast_b, None)
        
        # Calculate statistics
        nodes_a = self._count_nodes(root_a)
        nodes_b = self._count_nodes(root_b)
        
        # Perform diff
        self._compute_diff(root_a, root_b, threshold)
        
        # Calculate statistics
        unchanged, added, removed, modified = self._count_diffs(root_a)
        
        # Calculate overall similarity
        total = unchanged + added + removed + modified
        similarity = unchanged / total if total > 0 else 0.0
        
        # Extract changes
        changes = self._extract_changes(root_a, root_b)
        
        return DiffResult(
            root_a=root_a,
            root_b=root_b,
            total_nodes_a=nodes_a,
            total_nodes_b=nodes_b,
            unchanged_count=unchanged,
            added_count=added,
            removed_count=removed,
            modified_count=modified,
            similarity_score=similarity,
            changes=changes
        )
    
    def _dict_to_node(self, ast: Dict[str, Any], parent: Optional[ASTNode]) -> ASTNode:
        """Convert AST dictionary to ASTNode tree."""
        self._node_counter += 1
        node_id = f"node_{self._node_counter}"
        
        node = ASTNode(
            id=node_id,
            node_type=ast.get('_type', 'Unknown'),
            value=ast.get('name') or ast.get('id'),
            diff_type=DiffType.UNCHANGED,
            metadata={'dict_keys': list(ast.keys())}
        )
        
        # Process children
        for key, value in ast.items():
            if key == '_type':
                continue
            
            if isinstance(value, dict):
                child = self._dict_to_node(value, node)
                node.children.append(child)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        child = self._dict_to_node(item, node)
                        node.children.append(child)
        
        return node
    
    def _count_nodes(self, node: ASTNode) -> int:
        """Count total nodes in tree."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count
    
    def _compute_diff(
        self,
        node_a: ASTNode,
        node_b: ASTNode,
        threshold: float
    ):
        """Compute diff between two AST trees."""
        # Check if nodes match
        if self._nodes_match(node_a, node_b, threshold):
            node_a.diff_type = DiffType.UNCHANGED
            node_a.similarity_score = 1.0
        else:
            node_a.diff_type = DiffType.MODIFIED
            node_a.similarity_score = 0.5
        
        # Create mapping of node_b by type
        type_map_b = {}
        self._build_type_map(node_b, type_map_b)
        
        # Mark unmatched nodes in A as removed
        matched_b_ids = set()
        self._match_children(node_a, node_b, type_map_b, matched_b_ids, threshold)
        
        # Mark unmatched nodes in B as added
        self._mark_added(node_b, matched_b_ids)
    
    def _nodes_match(
        self,
        node_a: ASTNode,
        node_b: ASTNode,
        threshold: float
    ) -> bool:
        """Check if two nodes match based on type and structure."""
        if node_a.node_type != node_b.node_type:
            return False
        
        # Check children count
        if len(node_a.children) != len(node_b.children):
            return False
        
        # Check value similarity
        if node_a.value and node_b.value:
            if node_a.value == node_b.value:
                return True
            # Partial match
            return self._string_similarity(str(node_a.value), str(node_b.value)) >= threshold
        
        return len(node_a.children) == 0 and len(node_b.children) == 0
    
    def _string_similarity(self, str_a: str, str_b: str) -> float:
        """Calculate string similarity."""
        if str_a == str_b:
            return 1.0
        if not str_a or not str_b:
            return 0.0
        
        set_a = set(str_a.lower())
        set_b = set(str_b.lower())
        
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _build_type_map(
        self,
        node: ASTNode,
        type_map: Dict[str, List[ASTNode]]
    ):
        """Build mapping of node types to nodes."""
        if node.node_type not in type_map:
            type_map[node.node_type] = []
        type_map[node.node_type].append(node)
        
        for child in node.children:
            self._build_type_map(child, type_map)
    
    def _match_children(
        self,
        node_a: ASTNode,
        node_b: ASTNode,
        type_map_b: Dict[str, List[ASTNode]],
        matched_b_ids: set,
        threshold: float
    ):
        """Match children between nodes."""
        for child_a in node_a.children:
            matched = False
            
            if child_a.node_type in type_map_b:
                for i, candidate_b in enumerate(type_map_b[child_a.node_type]):
                    if i not in matched_b_ids:
                        if self._nodes_match(child_a, candidate_b, threshold):
                            child_a.diff_type = DiffType.UNCHANGED
                            child_a.similarity_score = 1.0
                            matched_b_ids.add(i)
                            matched = True
                            
                            # Recursively match grandchildren
                            self._match_children(
                                child_a,
                                candidate_b,
                                type_map_b,
                                matched_b_ids,
                                threshold
                            )
                            break
            
            if not matched:
                child_a.diff_type = DiffType.REMOVED
                child_a.similarity_score = 0.0
    
    def _mark_added(self, node: ASTNode, matched_ids: set):
        """Mark unmatched nodes as added."""
        for i, child in enumerate(node.children):
            if i not in matched_ids:
                child.diff_type = DiffType.ADDED
                child.similarity_score = 0.0
    
    def _count_diffs(self, node: ASTNode) -> Tuple[int, int, int, int]:
        """Count different diff types in tree."""
        unchanged = 1 if node.diff_type == DiffType.UNCHANGED else 0
        added = 1 if node.diff_type == DiffType.ADDED else 0
        removed = 1 if node.diff_type == DiffType.REMOVED else 0
        modified = 1 if node.diff_type == DiffType.MODIFIED else 0
        
        for child in node.children:
            u, a, r, m = self._count_diffs(child)
            unchanged += u
            added += a
            removed += r
            modified += m
        
        return unchanged, added, removed, modified
    
    def _extract_changes(
        self,
        node_a: ASTNode,
        node_b: ASTNode
    ) -> List[Dict[str, Any]]:
        """Extract list of changes between trees."""
        changes = []
        
        if node_a.diff_type != DiffType.UNCHANGED:
            changes.append({
                'type': node_a.diff_type.value,
                'node_type': node_a.node_type,
                'path': self._get_node_path(node_a),
                'value': node_a.value
            })
        
        for child in node_a.children:
            changes.extend(self._extract_changes(child, node_b))
        
        return changes
    
    def _get_node_path(self, node: ASTNode) -> str:
        """Get path to node in tree."""
        parts = []
        current = node
        while current:
            parts.append(current.node_type)
            current = getattr(current, 'parent', None)
        return '/'.join(reversed(parts))


class ASTDiffVisualizer:
    """
    Visualizes AST diffs in various formats.
    """
    
    def __init__(self):
        self.diff_generator = ASTDiffGenerator()
    
    def generate_html_diff(
        self,
        ast_a: Dict[str, Any],
        ast_b: Dict[str, Any],
        filename_a: str = "File A",
        filename_b: str = "File B"
    ) -> str:
        """
        Generate HTML side-by-side diff visualization.
        
        Args:
            ast_a: First AST
            ast_b: Second AST
            filename_a: Name of first file
            filename_b: Name of second file
            
        Returns:
            HTML string
        """
        diff_result = self.diff_generator.generate_diff(ast_a, ast_b)
        
        html = self._generate_html_header()
        html += self._generate_stats_section(diff_result)
        html += self._generate_legend()
        html += self._generate_side_by_side(diff_result.root_a, diff_result.root_b, filename_a, filename_b)
        html += self._generate_changes_list(diff_result.changes)
        html += self._generate_html_footer()
        
        return html
    
    def _generate_html_header(self) -> str:
        """Generate HTML header with styles."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AST Diff Visualization</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        header { background: #2d3748; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        header h1 { margin-bottom: 5px; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; }
        .stat-label { color: #666; font-size: 0.9em; }
        .stat.unchanged { border-left: 4px solid #48bb78; }
        .stat.added { border-left: 4px solid solid #4299e1; }
        .stat.removed { border-left: 4px solid #f56565; }
        .stat.modified { border-left: 4px solid #ed8936; }
        
        .legend { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-color { width: 20px; height: 20px; border-radius: 4px; }
        .legend-color.unchanged { background: #48bb78; }
        .legend-color.added { background: #4299e1; }
        .legend-color.removed { background: #f56565; }
        .legend-color.modified { background: #ed8936; }
        
        .diff-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .diff-panel { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
        .diff-header { background: #edf2f7; padding: 10px 15px; font-weight: bold; border-bottom: 1px solid #e2e8f0; }
        .diff-content { padding: 15px; max-height: 500px; overflow-y: auto; font-family: 'Fira Code', monospace; font-size: 0.85em; }
        
        .ast-node { margin: 5px 0; }
        .ast-node.unchanged { color: #2d3748; }
        .ast-node.added { color: #2b6cb0; background: #ebf8ff; padding: 2px 5px; border-radius: 3px; }
        .ast-node.removed { color: #c53030; background: #fff5f5; padding: 2px 5px; border-radius: 3px; text-decoration: line-through; }
        .ast-node.modified { color: #c05621; background: #fffaf0; padding: 2px 5px; border-radius: 3px; }
        
        .node-type { color: #805ad5; font-weight: bold; }
        .node-value { color: #38a169; }
        .node-children { margin-left: 20px; border-left: 1px dashed #e2e8f0; padding-left: 10px; }
        
        .changes-section { margin-top: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; }
        .changes-section h2 { margin-bottom: 15px; color: #2d3748; }
        .change-item { padding: 10px; margin: 5px 0; border-radius: 4px; }
        .change-item.added { background: #ebf8ff; border-left: 3px solid #4299e1; }
        .change-item.removed { background: #fff5f5; border-left: 3px solid #f56565; }
        .change-item.modified { background: #fffaf0; border-left: 3px solid #ed8936; }
        
        @media print { .stats { grid-template-columns: repeat(4, 1fr); } }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 AST Diff Visualization</h1>
            <p>Structural comparison of Abstract Syntax Trees</p>
        </header>
"""
    
    def _generate_stats_section(self, result: DiffResult) -> str:
        """Generate statistics section."""
        total = result.total_nodes_a + result.total_nodes_b
        return f"""
        <div class="stats">
            <div class="stat unchanged">
                <div class="stat-value">{result.unchanged_count}</div>
                <div class="stat-label">Unchanged</div>
            </div>
            <div class="stat added">
                <div class="stat-value">{result.added_count}</div>
                <div class="stat-label">Added</div>
            </div>
            <div class="stat removed">
                <div class="stat-value">{result.removed_count}</div>
                <div class="stat-label">Removed</div>
            </div>
            <div class="stat modified">
                <div class="stat-value">{result.modified_count}</div>
                <div class="stat-label">Modified</div>
            </div>
        </div>
        """
    
    def _generate_legend(self) -> str:
        """Generate legend."""
        return """
        <div class="legend">
            <div class="legend-item"><div class="legend-color unchanged"></div> Unchanged</div>
            <div class="legend-item"><div class="legend-color added"></div> Added</div>
            <div class="legend-item"><div class="legend-color removed"></div> Removed</div>
            <div class="legend-item"><div class="legend-color modified"></div> Modified</div>
        </div>
        """
    
    def _generate_side_by_side(
        self,
        root_a: ASTNode,
        root_b: ASTNode,
        filename_a: str,
        filename_b: str
    ) -> str:
        """Generate side-by-side diff panels."""
        tree_a = self._render_tree(root_a)
        tree_b = self._render_tree(root_b)
        
        return f"""
        <div class="diff-container">
            <div class="diff-panel">
                <div class="diff-header">{filename_a}</div>
                <div class="diff-content">{tree_a}</div>
            </div>
            <div class="diff-panel">
                <div class="diff-header">{filename_b}</div>
                <div class="diff-content">{tree_b}</div>
            </div>
        </div>
        """
    
    def _render_tree(self, node: ASTNode, depth: int = 0) -> str:
        """Render AST tree as HTML."""
        diff_class = node.diff_type.value
        
        html = f'<div class="ast-node {diff_class}">'
        html += f'<span class="node-type">{node.node_type}</span>'
        
        if node.value:
            html += f'<span class="node-value">"{node.value}"</span>'
        
        if node.children:
            html += '<div class="node-children">'
            for child in node.children:
                html += self._render_tree(child, depth + 1)
            html += '</div>'
        
        html += '</div>'
        return html
    
    def _generate_changes_list(self, changes: List[Dict[str, Any]]) -> str:
        """Generate list of changes."""
        if not changes:
            return '<div class="changes-section"><p>No changes detected.</p></div>'
        
        items = []
        for change in changes:
            diff_class = change['type']
            items.append(f"""
                <div class="change-item {diff_class}">
                    <strong>{diff_class.upper()}</strong>: 
                    <code>{change['node_type']}</code>
                    at <code>{change['path']}</code>
                </div>
            """)
        
        return f"""
        <div class="changes-section">
            <h2>📝 Changes Summary</h2>
            {''.join(items)}
        </div>
        """
    
    def _generate_html_footer(self) -> str:
        """Generate HTML footer."""
        return """
    </div>
</body>
</html>
"""
    
    def generate_json_diff(
        self,
        ast_a: Dict[str, Any],
        ast_b: Dict[str, Any]
    ) -> str:
        """
        Generate JSON diff output.
        
        Args:
            ast_a: First AST
            ast_b: Second AST
            
        Returns:
            JSON string
        """
        diff_result = self.diff_generator.generate_diff(ast_a, ast_b)
        
        return json.dumps({
            'statistics': {
                'total_nodes_a': diff_result.total_nodes_a,
                'total_nodes_b': diff_result.total_nodes_b,
                'unchanged': diff_result.unchanged_count,
                'added': diff_result.added_count,
                'removed': diff_result.removed_count,
                'modified': diff_result.modified_count,
                'similarity_score': diff_result.similarity_score
            },
            'changes': diff_result.changes
        }, indent=2)
    
    def generate_unified_diff(
        self,
        ast_a: Dict[str, Any],
        ast_b: Dict[str, Any]
    ) -> str:
        """
        Generate unified text diff.
        
        Args:
            ast_a: First AST
            ast_b: Second AST
            
        Returns:
            Unified diff string
        """
        diff_result = self.diff_generator.generate_diff(ast_a, ast_b)
        
        lines = [
            "AST Diff Report",
            "=" * 50,
            "",
            f"Nodes in A: {diff_result.total_nodes_a}",
            f"Nodes in B: {diff_result.total_nodes_b}",
            f"Similarity: {diff_result.similarity_score:.2%}",
            "",
            "-" * 50,
            "Changes:",
            "-" * 50,
        ]
        
        for change in diff_result.changes:
            lines.append(f"{change['type']:8} | {change['node_type']:20} | {change['path']}")
        
        return '\n'.join(lines)


# Convenience function
def visualize_ast_diff(
    ast_a: Dict[str, Any],
    ast_b: Dict[str, Any],
    format: str = 'html',
    filename_a: str = "File A",
    filename_b: str = "File B"
) -> str:
    """
    Generate AST diff visualization.
    
    Args:
        ast_a: First AST
        ast_b: Second AST
        format: Output format ('html', 'json', 'text')
        filename_a: Name of first file
        filename_b: Name of second file
        
    Returns:
        Formatted diff string
    """
    visualizer = ASTDiffVisualizer()
    
    if format == 'json':
        return visualizer.generate_json_diff(ast_a, ast_b)
    elif format == 'text':
        return visualizer.generate_unified_diff(ast_a, ast_b)
    else:
        return visualizer.generate_html_diff(ast_a, ast_b, filename_a, filename_b)
