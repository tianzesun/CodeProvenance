"""Score distribution plotter.

Generates visualizations of similarity score distributions across benchmark results,
showing statistical patterns and outliers.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import json


class DistributionType(Enum):
    """Types of distributions."""
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    VIOLIN = "violin"
    KDE = "kde"


@dataclass
class DistributionConfig:
    """Configuration for distribution plots."""
    distribution_type: DistributionType = DistributionType.HISTOGRAM
    bins: int = 20
    show_mean: bool = True
    show_median: bool = True
    show_std: bool = True
    show_outliers: bool = True
    color: str = "#3498db"
    width: int = 800
    height: int = 600

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "distribution_type": self.distribution_type.value,
            "bins": self.bins,
            "show_mean": self.show_mean,
            "show_median": self.show_median,
            "show_std": self.show_std,
            "show_outliers": self.show_outliers,
            "color": self.color,
            "width": self.width,
            "height": self.height
        }


class DistributionPlotter:
    """Generates score distribution visualizations.

    Creates visual representations of similarity score distributions,
    helping identify patterns, outliers, and statistical properties.
    """

    def __init__(self, config: Optional[DistributionConfig] = None):
        """Initialize distribution plotter.

        Args:
            config: Distribution configuration
        """
        self.config = config or DistributionConfig()

    def compute_statistics(self, scores: List[float]) -> Dict[str, float]:
        """Compute statistical measures for scores.

        Args:
            scores: List of similarity scores

        Returns:
            Dictionary of statistical measures
        """
        if not scores:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "q1": 0.0,
                "q3": 0.0,
                "iqr": 0.0
            }

        sorted_scores = sorted(scores)
        n = len(sorted_scores)

        mean = sum(scores) / n
        median = sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2

        variance = sum((x - mean) ** 2 for x in scores) / n
        std = variance ** 0.5

        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_scores[q1_idx]
        q3 = sorted_scores[q3_idx]
        iqr = q3 - q1

        return {
            "count": n,
            "mean": mean,
            "median": median,
            "std": std,
            "min": sorted_scores[0],
            "max": sorted_scores[-1],
            "q1": q1,
            "q3": q3,
            "iqr": iqr
        }

    def detect_outliers(self, scores: List[float]) -> List[float]:
        """Detect outliers using IQR method.

        Args:
            scores: List of similarity scores

        Returns:
            List of outlier scores
        """
        if len(scores) < 4:
            return []

        stats = self.compute_statistics(scores)
        lower_bound = stats["q1"] - 1.5 * stats["iqr"]
        upper_bound = stats["q3"] + 1.5 * stats["iqr"]

        return [s for s in scores if s < lower_bound or s > upper_bound]

    def compute_histogram(self, scores: List[float]) -> Dict[str, Any]:
        """Compute histogram bins and counts.

        Args:
            scores: List of similarity scores

        Returns:
            Histogram data
        """
        if not scores:
            return {"bins": [], "counts": []}

        min_val = min(scores)
        max_val = max(scores)
        bin_width = (max_val - min_val) / self.config.bins if max_val > min_val else 1.0

        bins = [min_val + i * bin_width for i in range(self.config.bins + 1)]
        counts = [0] * self.config.bins

        for score in scores:
            bin_idx = min(int((score - min_val) / bin_width), self.config.bins - 1)
            counts[bin_idx] += 1

        return {
            "bins": bins,
            "counts": counts,
            "bin_width": bin_width
        }

    def generate(
        self,
        scores: List[float],
        output_path: str,
        title: str = "Score Distribution",
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate distribution visualization.

        Args:
            scores: List of similarity scores
            output_path: Path to save visualization
            title: Plot title
            labels: Optional labels for data points

        Returns:
            Generation result with metadata
        """
        statistics = self.compute_statistics(scores)
        outliers = self.detect_outliers(scores)
        histogram = self.compute_histogram(scores)

        result = {
            "output_path": output_path,
            "title": title,
            "config": self.config.to_dict(),
            "statistics": statistics,
            "outliers": outliers,
            "outlier_count": len(outliers),
            "histogram": histogram,
            "data": {
                "scores": scores,
                "labels": labels
            }
        }

        return result

    def generate_comparison(
        self,
        distributions: Dict[str, List[float]],
        output_path: str,
        title: str = "Score Distribution Comparison"
    ) -> Dict[str, Any]:
        """Generate comparison of multiple distributions.

        Args:
            distributions: Dictionary mapping names to score lists
            output_path: Path to save visualization
            title: Plot title

        Returns:
            Generation result with metadata
        """
        comparison_stats = {}
        for name, scores in distributions.items():
            comparison_stats[name] = self.compute_statistics(scores)

        result = {
            "output_path": output_path,
            "title": title,
            "config": self.config.to_dict(),
            "distributions": comparison_stats,
            "data": distributions
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