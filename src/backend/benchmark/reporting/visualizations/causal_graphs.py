"""Causal similarity graph generator.

Generates graph visualizations showing causal relationships between code similarities,
highlighting attribution chains and influence patterns.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import json


class NodeType(Enum):
    """Types of nodes in causal graph."""
    ORIGINAL = "original"
    DERIVATIVE = "derivative"
    INDEPENDENT = "independent"
    SUSPECT = "suspect"


class EdgeType(Enum):
    """Types of edges in causal graph."""
    DERIVED_FROM = "derived_from"
    SIMILAR_TO = "similar_to"
    INFLUENCED = "influenced"
    INDEPENDENT = "independent"


@dataclass
class CausalNode:
    """A node in the causal graph."""
    node_id: str
    label: str
    node_type: NodeType
    similarity_score: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "label": self.label,
            "node_type": self.node_type.value,
            "similarity_score": self.similarity_score,
            "metadata": self.metadata
        }


@dataclass
class CausalEdge:
    """An edge in the causal graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float
    confidence: float
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "confidence": self.confidence,
            "evidence": self.evidence
        }


class CausalGraphGenerator:
    """Generates causal similarity graphs.

    Creates visual representations of causal relationships between code files,
    showing attribution chains and influence patterns.
    """

    def __init__(self, min_confidence: float = 0.5, layout: str = "force"):
        """Initialize causal graph generator.

        Args:
            min_confidence: Minimum confidence threshold for edges
            layout: Graph layout algorithm
        """
        self.min_confidence = min_confidence
        self.layout = layout

    def build_graph(
        self,
        files: List[Dict[str, Any]],
        similarities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build causal graph from file data and similarities.

        Args:
            files: List of file information
            similarities: List of similarity pairs

        Returns:
            Graph data structure
        """
        nodes = []
        edges = []

        # Create nodes for each file
        for file_info in files:
            node_type = NodeType(file_info.get("attribution", "independent"))
            node = CausalNode(
                node_id=file_info["file_id"],
                label=file_info["filename"],
                node_type=node_type,
                similarity_score=file_info.get("max_similarity", 0.0),
                metadata={
                    "language": file_info.get("language", "unknown"),
                    "lines": file_info.get("lines", 0),
                    "author": file_info.get("author", "unknown")
                }
            )
            nodes.append(node)

        # Create edges from similarities
        for sim in similarities:
            if sim["confidence"] >= self.min_confidence:
                edge = CausalEdge(
                    source_id=sim["source_id"],
                    target_id=sim["target_id"],
                    edge_type=EdgeType(sim.get("relationship", "similar_to")),
                    weight=sim["similarity"],
                    confidence=sim["confidence"],
                    evidence=sim.get("evidence", [])
                )
                edges.append(edge)

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "layout": self.layout,
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "avg_confidence": (
                    sum(e.confidence for e in edges) / len(edges)
                    if edges else 0
                )
            }
        }

    def generate(
        self,
        files: List[Dict[str, Any]],
        similarities: List[Dict[str, Any]],
        output_path: str,
        title: str = "Causal Similarity Graph"
    ) -> Dict[str, Any]:
        """Generate causal graph visualization.

        Args:
            files: List of file information
            similarities: List of similarity pairs
            output_path: Path to save visualization
            title: Graph title

        Returns:
            Generation result with metadata
        """
        graph_data = self.build_graph(files, similarities)

        result = {
            "output_path": output_path,
            "title": title,
            "graph": graph_data,
            "layout": self.layout,
            "metadata": {
                "min_confidence": self.min_confidence,
                "generated_at": "2026-04-02T15:51:00Z"
            }
        }

        return result

    def to_json(self, result: Dict[str, Any]) -> str:
        """Convert generation result to JSON.

        Args:
            result: Generation result

        Returns:
            JSON string
        """
        return json.dumps(result, indent=2)