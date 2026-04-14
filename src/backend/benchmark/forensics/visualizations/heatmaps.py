"""Token-level Heatmap Generator for code similarity detection.

Generates token-level similarity heatmaps for publication-ready visualizations.

Heatmaps show:
- Token-by-token similarity matrix
- Highlighted matches above threshold
- Color-coded similarity scores

Usage:
    from src.backend.benchmark.forensics.visualizations.heatmaps import TokenHeatmapGenerator

    generator = TokenHeatmapGenerator()
    generator.generate(code_a, code_b, similarity_matrix, "output.png")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class HeatmapConfig:
    """Configuration for heatmap generation.
    
    Attributes:
        figsize: Figure size (width, height).
        dpi: Dots per inch for output.
        colormap: Matplotlib colormap name.
        highlight_threshold: Threshold for highlighting matches.
        show_labels: Whether to show token labels.
        max_tokens: Maximum number of tokens to display.
        output_format: Output format (png, pdf, svg).
    """
    figsize: Tuple[int, int] = (15, 6)
    dpi: int = 150
    colormap: str = "YlOrRd"
    highlight_threshold: float = 0.8
    show_labels: bool = True
    max_tokens: int = 50
    output_format: str = "png"


class TokenHeatmapGenerator:
    """Generates token-level similarity heatmaps.
    
    Creates publication-ready visualizations showing token-by-token
    similarity between two code snippets.
    
    Usage:
        generator = TokenHeatmapGenerator()
        generator.generate(code_a, code_b, similarity_matrix, "output.png")
    """
    
    def __init__(self, config: Optional[HeatmapConfig] = None):
        """Initialize heatmap generator.
        
        Args:
            config: Configuration for heatmap generation.
        """
        self.config = config or HeatmapConfig()
    
    def generate(
        self,
        code_a: str,
        code_b: str,
        similarity_matrix: np.ndarray,
        output_path: str,
    ) -> str:
        """Generate token-level similarity heatmap.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            similarity_matrix: Token similarity matrix.
            output_path: Path to save the output.
            
        Returns:
            Path to the generated heatmap.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for heatmap generation. "
                "Install with: pip install matplotlib"
            )
        
        # Tokenize
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        # Truncate if needed
        if len(tokens_a) > self.config.max_tokens:
            tokens_a = tokens_a[:self.config.max_tokens]
            similarity_matrix = similarity_matrix[:self.config.max_tokens, :]
        
        if len(tokens_b) > self.config.max_tokens:
            tokens_b = tokens_b[:self.config.max_tokens]
            similarity_matrix = similarity_matrix[:, :self.config.max_tokens]
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=self.config.figsize)
        
        # Plot similarity matrix
        im = axes[0].imshow(
            similarity_matrix,
            cmap=self.config.colormap,
            aspect='auto',
            vmin=0,
            vmax=1,
        )
        
        if self.config.show_labels:
            axes[0].set_xticks(range(len(tokens_b)))
            axes[0].set_xticklabels(tokens_b, rotation=45, ha='right', fontsize=8)
            axes[0].set_yticks(range(len(tokens_a)))
            axes[0].set_yticklabels(tokens_a, fontsize=8)
        
        axes[0].set_title('Token Similarity Matrix')
        plt.colorbar(im, ax=axes[0], label='Similarity Score')
        
        # Highlight matches
        matches = np.where(similarity_matrix > self.config.highlight_threshold)
        for i, j in zip(matches[0], matches[1]):
            axes[0].add_patch(
                plt.Rectangle(
                    (j - 0.5, i - 0.5),
                    1, 1,
                    fill=False,
                    edgecolor='red',
                    linewidth=2,
                )
            )
        
        # Plot code snippets side by side
        axes[1].axis('off')
        
        # Format code for display
        code_a_display = self._format_code_for_display(code_a)
        code_b_display = self._format_code_for_display(code_b)
        
        code_text = f"Code A:\n{code_a_display}\n\nCode B:\n{code_b_display}"
        axes[1].text(
            0.1, 0.5, code_text,
            fontfamily='monospace',
            fontsize=8,
            verticalalignment='center',
            transform=axes[1].transAxes,
        )
        axes[1].set_title('Code Snippets')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _tokenize(self, code: str) -> List[str]:
        """Tokenize code string.
        
        Args:
            code: Code string.
            
        Returns:
            List of tokens.
        """
        # Simple tokenization by splitting on whitespace and punctuation
        tokens = re.findall(r'\b\w+\b|[^\w\s]', code)
        return tokens
    
    def _format_code_for_display(self, code: str) -> str:
        """Format code for display in visualization.
        
        Args:
            code: Code string.
            
        Returns:
            Formatted code string.
        """
        # Truncate if too long
        max_lines = 10
        lines = code.split('\n')
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append("...")
        
        # Limit line length
        formatted_lines = []
        for line in lines:
            if len(line) > 50:
                line = line[:47] + "..."
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def generate_comparison(
        self,
        code_pairs: List[Tuple[str, str, str]],
        output_dir: str,
    ) -> List[str]:
        """Generate heatmaps for multiple code pairs.
        
        Args:
            code_pairs: List of (pair_id, code_a, code_b) tuples.
            output_dir: Directory to save outputs.
            
        Returns:
            List of paths to generated heatmaps.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        output_paths = []
        for pair_id, code_a, code_b in code_pairs:
            # Generate similarity matrix
            similarity_matrix = self._compute_similarity_matrix(code_a, code_b)
            
            # Generate heatmap
            output_path = os.path.join(
                output_dir,
                f"heatmap_{pair_id}.{self.config.output_format}"
            )
            self.generate(code_a, code_b, similarity_matrix, output_path)
            output_paths.append(output_path)
        
        return output_paths
    
    def _compute_similarity_matrix(
        self,
        code_a: str,
        code_b: str,
    ) -> np.ndarray:
        """Compute token similarity matrix.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            Similarity matrix.
        """
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        n = len(tokens_a)
        m = len(tokens_b)
        
        # Initialize similarity matrix
        similarity_matrix = np.zeros((n, m))
        
        # Compute similarity for each token pair
        for i, token_a in enumerate(tokens_a):
            for j, token_b in enumerate(tokens_b):
                similarity_matrix[i, j] = self._token_similarity(token_a, token_b)
        
        return similarity_matrix
    
    def _token_similarity(self, token_a: str, token_b: str) -> float:
        """Compute similarity between two tokens.
        
        Args:
            token_a: First token.
            token_b: Second token.
            
        Returns:
            Similarity score (0.0 to 1.0).
        """
        # Exact match
        if token_a == token_b:
            return 1.0
        
        # Case-insensitive match
        if token_a.lower() == token_b.lower():
            return 0.9
        
        # Prefix match
        if token_a.startswith(token_b) or token_b.startswith(token_a):
            min_len = min(len(token_a), len(token_b))
            max_len = max(len(token_a), len(token_b))
            return min_len / max_len * 0.8
        
        # No match
        return 0.0