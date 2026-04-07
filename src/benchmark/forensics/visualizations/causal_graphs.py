"""Causal Graph Generator for code similarity detection.

Generates causal similarity graphs for publication-ready visualizations.

Causal graphs show:
- Component contributions to similarity
- Error attribution relationships
- Improvement priority rankings

Usage:
    from src.benchmark.forensics.visualizations.causal_graphs import CausalGraphGenerator

    generator = CausalGraphGenerator()
    generator.generate(root_cause_report, "output.png")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GraphConfig:
    """Configuration for causal graph generation.
    
    Attributes:
        figsize: Figure size (width, height).
        dpi: Dots per inch for output.
        node_size: Size of nodes.
        font_size: Font size for labels.
        edge_width: Width of edges.
        show_weights: Whether to show edge weights.
        output_format: Output format (png, pdf, svg).
    """
    figsize: Tuple[int, int] = (10, 8)
    dpi: int = 150
    node_size: int = 500
    font_size: int = 10
    edge_width: float = 2.0
    show_weights: bool = True
    output_format: str = "png"


@dataclass
class CausalNode:
    """Represents a node in causal graph.
    
    Attributes:
        node_id: Unique identifier.
        label: Display label.
        node_type: Type of node (component, error, improvement).
        weight: Weight for visualization.
    """
    node_id: str
    label: str
    node_type: str = "component"
    weight: float = 1.0


@dataclass
class CausalEdge:
    """Represents an edge in causal graph.
    
    Attributes:
        source: Source node ID.
        target: Target node ID.
        weight: Edge weight.
        label: Edge label.
    """
    source: str
    target: str
    weight: float = 1.0
    label: str = ""


class CausalGraphGenerator:
    """Generates causal similarity graphs.
    
    Creates publication-ready visualizations showing causal relationships
    between components, errors, and improvements.
    
    Usage:
        generator = CausalGraphGenerator()
        generator.generate(root_cause_report, "output.png")
    """
    
    def __init__(self, config: Optional[GraphConfig] = None):
        """Initialize causal graph generator.
        
        Args:
            config: Configuration for graph generation.
        """
        self.config = config or GraphConfig()
    
    def generate(
        self,
        root_cause_report: Any,
        output_path: str,
    ) -> str:
        """Generate causal graph from root cause report.
        
        Args:
            root_cause_report: Root cause report from RootCauseAttributor.
            output_path: Path to save the output.
            
        Returns:
            Path to the generated graph.
        """
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
        except ImportError:
            raise ImportError(
                "matplotlib and networkx are required for graph generation. "
                "Install with: pip install matplotlib networkx"
            )
        
        # Build graph from report
        graph = self._build_graph(root_cause_report)
        
        # Create figure
        fig, ax = plt.subplots(figsize=self.config.figsize)
        
        # Plot graph
        self._plot_graph(graph, ax)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _build_graph(self, report: Any) -> Any:
        """Build networkx graph from root cause report.
        
        Args:
            report: Root cause report.
            
        Returns:
            NetworkX graph.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "networkx is required for graph generation. "
                "Install with: pip install networkx"
            )
        
        graph = nx.DiGraph()
        
        # Add component nodes
        component_losses = getattr(report, 'component_losses', {})
        for comp_name, loss in component_losses.items():
            graph.add_node(
                f"comp_{comp_name}",
                label=f"{comp_name}\n({loss:.3f})",
                node_type="component",
                weight=loss,
            )
        
        # Add error nodes
        primary_causes = getattr(report, 'primary_cause_distribution', {})
        for cause, count in primary_causes.items():
            graph.add_node(
                f"error_{cause}",
                label=f"{cause}\n({count})",
                node_type="error",
                weight=count,
            )
            
            # Add edges from components to errors
            for comp_name in component_losses:
                if comp_name in cause:
                    graph.add_edge(
                        f"comp_{comp_name}",
                        f"error_{cause}",
                        weight=component_losses[comp_name],
                    )
        
        # Add improvement nodes (if available)
        if hasattr(report, 'component_effectiveness'):
            for comp_name, eff in report.component_effectiveness.items():
                correlation = getattr(eff, 'correlation', 0.5)
                if correlation < 0.3:
                    graph.add_node(
                        f"improve_{comp_name}",
                        label=f"Improve\n{comp_name}",
                        node_type="improvement",
                        weight=1 - correlation,
                    )
                    
                    # Add edge from component to improvement
                    graph.add_edge(
                        f"comp_{comp_name}",
                        f"improve_{comp_name}",
                        weight=1 - correlation,
                        label="needs improvement",
                    )
        
        return graph
    
    def _plot_graph(self, graph: Any, ax: Any) -> None:
        """Plot graph on axis.
        
        Args:
            graph: NetworkX graph.
            ax: Matplotlib axis.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "networkx is required for graph generation. "
                "Install with: pip install networkx"
            )
        
        if len(graph.nodes) == 0:
            ax.text(0.5, 0.5, "No causal relationships", ha='center', va='center')
            return
        
        # Layout
        pos = nx.spring_layout(graph, k=2, iterations=50)
        
        # Get node types for coloring
        node_colors = []
        for node_id, data in graph.nodes(data=True):
            node_type = data.get('node_type', 'component')
            if node_type == 'component':
                node_colors.append('lightblue')
            elif node_type == 'error':
                node_colors.append('lightcoral')
            elif node_type == 'improvement':
                node_colors.append('lightgreen')
            else:
                node_colors.append('lightgray')
        
        # Draw nodes
        nx.draw_networkx_nodes(
            graph, pos, ax=ax,
            node_size=self.config.node_size,
            node_color=node_colors,
            alpha=0.8,
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            graph, pos, ax=ax,
            arrows=True,
            arrowsize=15,
            edge_color='gray',
            width=self.config.edge_width,
        )
        
        # Draw labels
        labels = nx.get_node_attributes(graph, 'label')
        nx.draw_networkx_labels(
            graph, pos, labels, ax=ax,
            font_size=self.config.font_size,
            font_weight='bold',
        )
        
        # Draw edge weights if enabled
        if self.config.show_weights:
            edge_labels = nx.get_edge_attributes(graph, 'label')
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    graph, pos, edge_labels, ax=ax,
                    font_size=self.config.font_size - 2,
                )
        
        # Add legend
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w',
                      markerfacecolor='lightblue', markersize=10, label='Component'),
            plt.Line2D([0], [0], marker='o', color='w',
                      markerfacecolor='lightcoral', markersize=10, label='Error'),
            plt.Line2D([0], [0], marker='o', color='w',
                      markerfacecolor='lightgreen', markersize=10, label='Improvement'),
        ]
        ax.legend(handles=legend_elements, loc='upper left')
        
        ax.set_title('Causal Similarity Graph')
        ax.axis('off')
    
    def generate_improvement_ranking(
        self,
        causal_ranking_report: Any,
        output_path: str,
    ) -> str:
        """Generate improvement ranking visualization.
        
        Args:
            causal_ranking_report: Causal ranking report.
            output_path: Path to save the output.
            
        Returns:
            Path to the generated visualization.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for visualization. "
                "Install with: pip install matplotlib"
            )
        
        # Get candidates
        candidates = getattr(causal_ranking_report, 'candidates', [])
        
        if not candidates:
            fig, ax = plt.subplots(figsize=self.config.figsize)
            ax.text(0.5, 0.5, "No improvement candidates", ha='center', va='center')
            plt.savefig(output_path, dpi=self.config.dpi, bbox_inches='tight')
            plt.close()
            return output_path
        
        # Prepare data
        targets = [c.target for c in candidates[:10]]
        impacts = [c.estimated_impact for c in candidates[:10]]
        confidences = [c.confidence for c in candidates[:10]]
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=(self.config.figsize[0] * 1.5, self.config.figsize[1]))
        
        # Plot 1: Impact ranking
        axes[0].barh(range(len(targets)), impacts, color='steelblue', alpha=0.8)
        axes[0].set_yticks(range(len(targets)))
        axes[0].set_yticklabels(targets, fontsize=self.config.font_size)
        axes[0].set_xlabel('Estimated Impact', fontsize=self.config.font_size)
        axes[0].set_title('Improvement Impact Ranking', fontsize=self.config.font_size + 2)
        axes[0].invert_yaxis()
        
        # Plot 2: Impact vs Confidence scatter
        axes[1].scatter(impacts, confidences, s=100, alpha=0.6, c='steelblue')
        axes[1].set_xlabel('Estimated Impact', fontsize=self.config.font_size)
        axes[1].set_ylabel('Confidence', fontsize=self.config.font_size)
        axes[1].set_title('Impact vs Confidence', fontsize=self.config.font_size + 2)
        
        # Add labels to points
        for i, target in enumerate(targets):
            axes[1].annotate(
                target,
                (impacts[i], confidences[i]),
                fontsize=self.config.font_size - 2,
                ha='center',
                va='bottom',
            )
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        
        return output_path