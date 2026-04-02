"""AST alignment visualization generator.

Generates visual diagrams showing AST structure alignment between code pairs,
highlighting structural similarities and differences.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import json


class AlignmentType(Enum):
    """Types of AST alignment."""
    MATCH = "match"
    MISMATCH = "mismatch"
    INSERTION = "insertion"
    DELETION = "deletion"
    RENAME = "rename"


@dataclass
class ASTNode:
    """Represents a node in the AST."""
    node_id: str
    node_type: str
    value: str
    children: List['ASTNode']
    line_start: int
    line_end: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "value": self.value,
            "children": [c.to_dict() for c in self.children],
            "line_start": self.line_start,
            "line_end": self.line_end
        }


@dataclass
class AlignmentPair:
    """A pair of aligned AST nodes."""
    source_node: ASTNode
    target_node: ASTNode
    alignment_type: AlignmentType
    similarity_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_node": self.source_node.to_dict(),
            "target_node": self.target_node.to_dict(),
            "alignment_type": self.alignment_type.value,
            "similarity_score": self.similarity_score
        }


class ASTAlignmentVisualizer:
    """Generates AST alignment visualizations.

    Creates visual representations of AST structure alignment,
    showing how code structures match between source and target.
    """

    def __init__(self, show_line_numbers: bool = True, color_coded: bool = True):
        """Initialize AST alignment visualizer.

        Args:
            show_line_numbers: Whether to show line numbers
            color_coded: Whether to use color coding for alignment types
        """
        self.show_line_numbers = show_line_numbers
        self.color_coded = color_coded

    def parse_to_ast(self, code: str) -> ASTNode:
        """Parse code to AST representation.

        Args:
            code: Source code string

        Returns:
            Root AST node
        """
        # Simplified AST parsing - in production use a proper parser
        lines = code.split('\n')
        root = ASTNode(
            node_id="root",
            node_type="Program",
            value="",
            children=[],
            line_start=1,
            line_end=len(lines)
        )

        for i, line in enumerate(lines, 1):
            if line.strip():
                child = ASTNode(
                    node_id=f"line_{i}",
                    node_type="Statement",
                    value=line.strip(),
                    children=[],
                    line_start=i,
                    line_end=i
                )
                root.children.append(child)

        return root

    def compute_alignment(
        self,
        source_ast: ASTNode,
        target_ast: ASTNode
    ) -> List[AlignmentPair]:
        """Compute alignment between two ASTs.

        Args:
            source_ast: Source AST root
            target_ast: Target AST root

        Returns:
            List of alignment pairs
        """
        alignments = []
        source_nodes = source_ast.children
        target_nodes = target_ast.children

        # Simple alignment by position - in production use tree edit distance
        max_len = max(len(source_nodes), len(target_nodes))
        for i in range(max_len):
            if i < len(source_nodes) and i < len(target_nodes):
                # Both exist - compare
                similarity = 1.0 if source_nodes[i].value == target_nodes[i].value else 0.5
                align_type = AlignmentType.MATCH if similarity > 0.8 else AlignmentType.MISMATCH
                alignments.append(AlignmentPair(
                    source_node=source_nodes[i],
                    target_node=target_nodes[i],
                    alignment_type=align_type,
                    similarity_score=similarity
                ))
            elif i < len(source_nodes):
                # Only in source - deletion
                alignments.append(AlignmentPair(
                    source_node=source_nodes[i],
                    target_node=ASTNode("empty", "Empty", "", [], 0, 0),
                    alignment_type=AlignmentType.DELETION,
                    similarity_score=0.0
                ))
            else:
                # Only in target - insertion
                alignments.append(AlignmentPair(
                    source_node=ASTNode("empty", "Empty", "", [], 0, 0),
                    target_node=target_nodes[i],
                    alignment_type=AlignmentType.INSERTION,
                    similarity_score=0.0
                ))

        return alignments

    def generate(
        self,
        code_a: str,
        code_b: str,
        output_path: str,
        title: str = "AST Alignment Diagram"
    ) -> Dict[str, Any]:
        """Generate AST alignment visualization.

        Args:
            code_a: First code snippet
            code_b: Second code snippet
            output_path: Path to save visualization
            title: Visualization title

        Returns:
            Generation result with metadata
        """
        source_ast = self.parse_to_ast(code_a)
        target_ast = self.parse_to_ast(code_b)
        alignments = self.compute_alignment(source_ast, target_ast)

        match_count = sum(1 for a in alignments if a.alignment_type == AlignmentType.MATCH)
        total_count = len(alignments)
        avg_similarity = (
            sum(a.similarity_score for a in alignments) / total_count
            if total_count > 0 else 0
        )

        result = {
            "output_path": output_path,
            "title": title,
            "source_ast": source_ast.to_dict(),
            "target_ast": target_ast.to_dict(),
            "alignments": [a.to_dict() for a in alignments],
            "statistics": {
                "total_nodes": total_count,
                "matched_nodes": match_count,
                "match_rate": match_count / total_count if total_count > 0 else 0,
                "average_similarity": avg_similarity
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