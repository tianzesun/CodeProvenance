"""Token-level similarity heatmap generator.

Generates visual heatmaps showing token-level similarity between code pairs,
highlighting matching regions and similarity scores.
"""
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class HeatmapConfig:
    """Configuration for heatmap generation."""
    width: int = 800
    height: int = 600
    colormap: str = "YlOrRd"
    show_labels: bool = True
    highlight_threshold: float = 0.8
    font_size: int = 10
    output_format: str = "png"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "width": self.width,
            "height": self.height,
            "colormap": self.colormap,
            "show_labels": self.show_labels,
            "highlight_threshold": self.highlight_threshold,
            "font_size": self.font_size,
            "output_format": self.output_format
        }


class TokenHeatmapGenerator:
    """Generates token-level similarity heatmaps.

    Creates visual representations of token similarity matrices,
    highlighting regions of high similarity for forensic analysis.
    """

    def __init__(self, config: Optional[HeatmapConfig] = None):
        """Initialize heatmap generator.

        Args:
            config: Heatmap configuration options
        """
        self.config = config or HeatmapConfig()

    def tokenize(self, code: str) -> List[str]:
        """Tokenize code into individual tokens.

        Args:
            code: Source code string

        Returns:
            List of tokens
        """
        import re
        tokens = re.findall(r'\b\w+\b|[^\s\w]', code)
        return [t for t in tokens if t.strip()]

    def compute_similarity_matrix(
        self,
        tokens_a: List[str],
        tokens_b: List[str]
    ) -> List[List[float]]:
        """Compute similarity matrix between two token lists.

        Args:
            tokens_a: First list of tokens
            tokens_b: Second list of tokens

        Returns:
            2D similarity matrix
        """
        matrix = []
        for token_a in tokens_a:
            row = []
            for token_b in tokens_b:
                similarity = 1.0 if token_a == token_b else 0.0
                row.append(similarity)
            matrix.append(row)
        return matrix

    def find_high_similarity_regions(
        self,
        similarity_matrix: List[List[float]],
        tokens_a: List[str],
        tokens_b: List[str]
    ) -> List[Dict[str, Any]]:
        """Find regions with high similarity.

        Args:
            similarity_matrix: Token similarity matrix
            tokens_a: First token list
            tokens_b: Second token list

        Returns:
            List of high similarity regions
        """
        regions = []
        threshold = self.config.highlight_threshold

        for i, row in enumerate(similarity_matrix):
            for j, score in enumerate(row):
                if score >= threshold:
                    regions.append({
                        "row": i,
                        "col": j,
                        "token_a": tokens_a[i],
                        "token_b": tokens_b[j],
                        "similarity": score
                    })

        return regions

    def generate(
        self,
        code_a: str,
        code_b: str,
        output_path: str,
        title: str = "Token Similarity Heatmap"
    ) -> Dict[str, Any]:
        """Generate heatmap visualization.

        Args:
            code_a: First code snippet
            code_b: Second code snippet
            output_path: Path to save visualization
            title: Heatmap title

        Returns:
            Generation result with metadata
        """
        tokens_a = self.tokenize(code_a)
        tokens_b = self.tokenize(code_b)
        similarity_matrix = self.compute_similarity_matrix(tokens_a, tokens_b)
        high_regions = self.find_high_similarity_regions(
            similarity_matrix, tokens_a, tokens_b
        )

        total_comparisons = len(tokens_a) * len(tokens_b)
        avg_similarity = (
            sum(sum(row) for row in similarity_matrix) / total_comparisons
            if total_comparisons > 0 else 0
        )

        result = {
            "output_path": output_path,
            "title": title,
            "config": self.config.to_dict(),
            "statistics": {
                "tokens_a_count": len(tokens_a),
                "tokens_b_count": len(tokens_b),
                "total_comparisons": total_comparisons,
                "average_similarity": avg_similarity,
                "high_similarity_count": len(high_regions)
            },
            "high_similarity_regions": high_regions,
            "similarity_matrix": similarity_matrix
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