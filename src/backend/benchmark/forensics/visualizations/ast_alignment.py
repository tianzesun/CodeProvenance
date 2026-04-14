"""AST Alignment Visualizer for code similarity detection.

Generates AST alignment diagrams for publication-ready visualizations.

AST alignment shows:
- Tree structure comparison
- Node-by-node alignment
- Matching subtrees highlighted

Usage:
    from src.backend.benchmark.forensics.visualizations.ast_alignment import ASTAlignmentVisualizer

    visualizer = ASTAlignmentVisualizer()
    visualizer.generate(code_a, code_b, "output.png")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AlignmentConfig:
    """Configuration for AST alignment visualization.
    
    Attributes:
        figsize: Figure size (width, height).
        dpi: Dots per inch for output.
        node_size: Size of AST nodes.
        font_size: Font size for labels.
        show_node_types: Whether to show node types.
        max_depth: Maximum depth to display.
        output_format: Output format (png, pdf, svg).
    """
    figsize: Tuple[int, int] = (12, 8)
    dpi: int = 150
    node_size: int = 300
    font_size: int = 8
    show_node_types: bool = True
    max_depth: int = 5
    output_format: str = "png"


@dataclass
class ASTNode:
    """Represents an AST node.
    
    Attributes:
        node_type: Type of the node.
        value: Value of the node.
        children: List of child nodes.
        line_start: Starting line number.
        line_end: Ending line number.
    """
    node_type: str
    value: str = ""
    children: List['ASTNode'] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


class ASTAlignmentVisualizer:
    """Visualizes AST alignment between code snippets.
    
    Creates publication-ready visualizations showing AST structure
    and alignment between two code snippets.
    
    Usage:
        visualizer = ASTAlignmentVisualizer()
        visualizer.generate(code_a, code_b, "output.png")
    """
    
    def __init__(self, config: Optional[AlignmentConfig] = None):
        """Initialize AST alignment visualizer.
        
        Args:
            config: Configuration for visualization.
        """
        self.config = config or AlignmentConfig()
    
    def generate(
        self,
        code_a: str,
        code_b: str,
        output_path: str,
    ) -> str:
        """Generate AST alignment visualization.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            output_path: Path to save the output.
            
        Returns:
            Path to the generated visualization.
        """
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
        except ImportError:
            raise ImportError(
                "matplotlib and networkx are required for AST visualization. "
                "Install with: pip install matplotlib networkx"
            )
        
        # Parse ASTs
        ast_a = self._parse_ast(code_a)
        ast_b = self._parse_ast(code_b)
        
        # Create graphs
        graph_a = self._ast_to_graph(ast_a, "A")
        graph_b = self._ast_to_graph(ast_b, "B")
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=self.config.figsize)
        
        # Plot AST A
        self._plot_ast(graph_a, axes[0], "Code A AST")
        
        # Plot AST B
        self._plot_ast(graph_b, axes[1], "Code B AST")
        
        # Highlight matching nodes
        matching_nodes = self._find_matching_nodes(ast_a, ast_b)
        self._highlight_matches(graph_a, graph_b, matching_nodes, axes)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _parse_ast(self, code: str) -> ASTNode:
        """Parse code into AST.
        
        Args:
            code: Code string.
            
        Returns:
            Root AST node.
        """
        # Simplified AST parsing (in production, use ast module)
        lines = code.split('\n')
        root = ASTNode(node_type="Module", line_start=1, line_end=len(lines))
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Detect function definitions
            if line.startswith('def '):
                func_node = ASTNode(
                    node_type="FunctionDef",
                    value=line.split('(')[0].replace('def ', ''),
                    line_start=i + 1,
                    line_end=i + 1,
                )
                root.children.append(func_node)
            
            # Detect class definitions
            elif line.startswith('class '):
                class_node = ASTNode(
                    node_type="ClassDef",
                    value=line.split(':')[0].replace('class ', ''),
                    line_start=i + 1,
                    line_end=i + 1,
                )
                root.children.append(class_node)
            
            # Detect assignments
            elif '=' in line and not line.startswith('='):
                assign_node = ASTNode(
                    node_type="Assign",
                    value=line.split('=')[0].strip(),
                    line_start=i + 1,
                    line_end=i + 1,
                )
                root.children.append(assign_node)
            
            # Detect if statements
            elif line.startswith('if '):
                if_node = ASTNode(
                    node_type="If",
                    value=line.split(':')[0],
                    line_start=i + 1,
                    line_end=i + 1,
                )
                root.children.append(if_node)
            
            # Detect for loops
            elif line.startswith('for '):
                for_node = ASTNode(
                    node_type="For",
                    value=line.split(':')[0],
                    line_start=i + 1,
                    line_end=i + 1,
                )
                root.children.append(for_node)
        
        return root
    
    def _ast_to_graph(self, ast: ASTNode, prefix: str) -> Any:
        """Convert AST to networkx graph.
        
        Args:
            ast: Root AST node.
            prefix: Prefix for node IDs.
            
        Returns:
            NetworkX graph.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "networkx is required for AST visualization. "
                "Install with: pip install networkx"
            )
        
        graph = nx.DiGraph()
        self._add_nodes_to_graph(graph, ast, prefix, 0)
        return graph
    
    def _add_nodes_to_graph(
        self,
        graph: Any,
        node: ASTNode,
        prefix: str,
        depth: int,
    ) -> str:
        """Add nodes to graph recursively.
        
        Args:
            graph: NetworkX graph.
            node: AST node.
            prefix: Prefix for node IDs.
            depth: Current depth.
            
        Returns:
            Node ID.
        """
        if depth > self.config.max_depth:
            return ""
        
        node_id = f"{prefix}_{id(node)}"
        
        # Add node
        label = node.value if node.value else node.node_type
        if self.config.show_node_types:
            label = f"{node.node_type}\n{label}"
        
        graph.add_node(node_id, label=label, node_type=node.node_type)
        
        # Add children
        for child in node.children:
            child_id = self._add_nodes_to_graph(graph, child, prefix, depth + 1)
            if child_id:
                graph.add_edge(node_id, child_id)
        
        return node_id
    
    def _plot_ast(self, graph: Any, ax: Any, title: str) -> None:
        """Plot AST on axis.
        
        Args:
            graph: NetworkX graph.
            ax: Matplotlib axis.
            title: Plot title.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "networkx is required for AST visualization. "
                "Install with: pip install networkx"
            )
        
        if len(graph.nodes) == 0:
            ax.text(0.5, 0.5, "No AST nodes", ha='center', va='center')
            ax.set_title(title)
            return
        
        # Layout
        pos = nx.spring_layout(graph, k=1, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(
            graph, pos, ax=ax,
            node_size=self.config.node_size,
            node_color='lightblue',
            alpha=0.8,
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            graph, pos, ax=ax,
            arrows=True,
            arrowsize=10,
            edge_color='gray',
        )
        
        # Draw labels
        labels = nx.get_node_attributes(graph, 'label')
        nx.draw_networkx_labels(
            graph, pos, labels, ax=ax,
            font_size=self.config.font_size,
        )
        
        ax.set_title(title)
        ax.axis('off')
    
    def _find_matching_nodes(
        self,
        ast_a: ASTNode,
        ast_b: ASTNode,
    ) -> List[Tuple[ASTNode, ASTNode]]:
        """Find matching nodes between two ASTs.
        
        Args:
            ast_a: First AST.
            ast_b: Second AST.
            
        Returns:
            List of matching node pairs.
        """
        matches = []
        
        # Simple matching by node type and value
        for node_a in ast_a.children:
            for node_b in ast_b.children:
                if (node_a.node_type == node_b.node_type and
                    node_a.value == node_b.value):
                    matches.append((node_a, node_b))
        
        return matches
    
    def _highlight_matches(
        self,
        graph_a: Any,
        graph_b: Any,
        matches: List[Tuple[ASTNode, ASTNode]],
        axes: List[Any],
    ) -> None:
        """Highlight matching nodes in graphs.
        
        Args:
            graph_a: First graph.
            graph_b: Second graph.
            matches: List of matching node pairs.
            axes: List of matplotlib axes.
        """
        try:
            import networkx as nx
        except ImportError:
            return
        
        if not matches:
            return
        
        # Highlight matching nodes
        for node_a, node_b in matches:
            # Find node IDs
            for node_id, data in graph_a.nodes(data=True):
                if data.get('node_type') == node_a.node_type:
                    # Highlight in first graph
                    nx.draw_networkx_nodes(
                        graph_a,
                        nx.spring_layout(graph_a),
                        ax=axes[0],
                        nodelist=[node_id],
                        node_color='yellow',
                        node_size=self.config.node_size * 1.5,
                    )
            
            for node_id, data in graph_b.nodes(data=True):
                if data.get('node_type') == node_b.node_type:
                    # Highlight in second graph
                    nx.draw_networkx_nodes(
                        graph_b,
                        nx.spring_layout(graph_b),
                        ax=axes[1],
                        nodelist=[node_id],
                        node_color='yellow',
                        node_size=self.config.node_size * 1.5,
                    )