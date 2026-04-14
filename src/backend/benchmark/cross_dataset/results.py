"""Structured results for cross-dataset benchmarking.

Contains result objects for:
    - Per-dataset tool results
    - Per-tool cross-dataset results
    - Overall summary with rankings, variance, and stability
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class RankingEntry:
    """A single entry in a ranking table."""
    rank: int
    tool_name: str
    metric_name: str
    value: float
    std: float = 0.0
    dataset_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "tool_name": self.tool_name,
            "metric_name": self.metric_name,
            "value": round(self.value, 4),
            "std": round(self.std, 4),
            "dataset_count": self.dataset_count,
        }


@dataclass
class DatasetResult:
    """Results for one tool on one dataset."""
    dataset_name: str
    tool_name: str
    num_pairs: int
    num_positive: int
    num_negative: int
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float
    pr_auc: float
    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset_name,
            "tool": self.tool_name,
            "num_pairs": self.num_pairs,
            "num_positive": self.num_positive,
            "num_negative": self.num_negative,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "threshold": round(self.threshold, 4),
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
        }


@dataclass
class ToolResult:
    """Aggregated results for one tool across all datasets."""
    tool_name: str
    dataset_results: List[DatasetResult] = field(default_factory=list)
    mean_metrics: Dict[str, float] = field(default_factory=dict)
    std_metrics: Dict[str, float] = field(default_factory=dict)
    min_metrics: Dict[str, float] = field(default_factory=dict)
    max_metrics: Dict[str, float] = field(default_factory=dict)
    stability_score: float = 0.0

    def compute_aggregates(self) -> None:
        """Compute mean, std, min, max across all dataset results."""
        if not self.dataset_results:
            return

        metric_names = ["precision", "recall", "f1", "accuracy", "roc_auc", "pr_auc"]
        values: Dict[str, List[float]] = {m: [] for m in metric_names}

        for dr in self.dataset_results:
            for m in metric_names:
                val = getattr(dr, m, 0.0)
                values[m].append(val)

        self.mean_metrics = {m: float(np.mean(vs)) for m, vs in values.items() if vs}
        self.std_metrics = {m: float(np.std(vs)) for m, vs in values.items() if vs}
        self.min_metrics = {m: float(np.min(vs)) for m, vs in values.items() if vs}
        self.max_metrics = {m: float(np.max(vs)) for m, vs in values.items() if vs}

        stability_scores = []
        for m in metric_names:
            if m in self.std_metrics and m in self.mean_metrics:
                mean_val = self.mean_metrics[m]
                std_val = self.std_metrics[m]
                cv = std_val / mean_val if mean_val > 0 else std_val
                stability_scores.append(1.0 - min(cv, 1.0))

        self.stability_score = float(np.mean(stability_scores)) if stability_scores else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "num_datasets": len(self.dataset_results),
            "mean_metrics": {k: round(v, 4) for k, v in self.mean_metrics.items()},
            "std_metrics": {k: round(v, 4) for k, v in self.std_metrics.items()},
            "min_metrics": {k: round(v, 4) for k, v in self.min_metrics.items()},
            "max_metrics": {k: round(v, 4) for k, v in self.max_metrics.items()},
            "stability_score": round(self.stability_score, 4),
            "per_dataset": [dr.to_dict() for dr in self.dataset_results],
        }


@dataclass
class CrossEvalSummary:
    """Complete summary of cross-dataset evaluation.

    Contains:
        - Per-dataset rankings (which tool performed best on each dataset)
        - Average performance across datasets per tool
        - Variance and stability metrics
    """
    dataset_results: List[DatasetResult] = field(default_factory=list)
    tool_results: Dict[str, ToolResult] = field(default_factory=dict)
    per_dataset_rankings: Dict[str, List[RankingEntry]] = field(default_factory=dict)
    overall_rankings: Dict[str, List[RankingEntry]] = field(default_factory=dict)
    stability_rankings: List[RankingEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_rankings(self) -> None:
        """Compute all rankings from dataset results."""
        self._compute_per_dataset_rankings()
        self._compute_overall_rankings()
        self._compute_stability_rankings()

    def _compute_per_dataset_rankings(self) -> None:
        """Rank tools per dataset by F1 score."""
        by_dataset: Dict[str, List[DatasetResult]] = {}
        for dr in self.dataset_results:
            by_dataset.setdefault(dr.dataset_name, []).append(dr)

        rankings: Dict[str, List[RankingEntry]] = {}
        for ds_name, results in by_dataset.items():
            sorted_results = sorted(results, key=lambda r: r.f1, reverse=True)
            rankings[ds_name] = [
                RankingEntry(
                    rank=i + 1,
                    tool_name=r.tool_name,
                    metric_name="f1",
                    value=r.f1,
                    dataset_count=1,
                )
                for i, r in enumerate(sorted_results)
            ]

        self.per_dataset_rankings = rankings

    def _compute_overall_rankings(self) -> None:
        """Rank tools by mean performance across datasets."""
        metric_names = ["f1", "precision", "recall", "roc_auc", "pr_auc", "accuracy"]
        rankings: Dict[str, List[RankingEntry]] = {}

        for metric in metric_names:
            tool_means = []
            for tool_name, tool_res in self.tool_results.items():
                tool_res.compute_aggregates()
                mean_val = tool_res.mean_metrics.get(metric, 0.0)
                std_val = tool_res.std_metrics.get(metric, 0.0)
                ds_count = len(tool_res.dataset_results)
                tool_means.append((tool_name, mean_val, std_val, ds_count))

            tool_means.sort(key=lambda x: x[1], reverse=True)
            rankings[metric] = [
                RankingEntry(
                    rank=i + 1,
                    tool_name=tm[0],
                    metric_name=metric,
                    value=tm[1],
                    std=tm[2],
                    dataset_count=tm[3],
                )
                for i, tm in enumerate(tool_means)
            ]

        self.overall_rankings = rankings

    def _compute_stability_rankings(self) -> None:
        """Rank tools by stability (low variance = high stability)."""
        stability_entries = []
        for tool_name, tool_res in self.tool_results.items():
            tool_res.compute_aggregates()
            stability_entries.append((tool_name, tool_res.stability_score))

        stability_entries.sort(key=lambda x: x[1], reverse=True)
        self.stability_rankings = [
            RankingEntry(
                rank=i + 1,
                tool_name=se[0],
                metric_name="stability",
                value=se[1],
            )
            for i, se in enumerate(stability_entries)
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert full summary to dictionary."""
        return {
            "per_dataset_rankings": {
                ds: [e.to_dict() for e in entries]
                for ds, entries in self.per_dataset_rankings.items()
            },
            "overall_rankings": {
                metric: [e.to_dict() for e in entries]
                for metric, entries in self.overall_rankings.items()
            },
            "stability_rankings": [e.to_dict() for e in self.stability_rankings],
            "tool_results": {
                name: tr.to_dict() for name, tr in self.tool_results.items()
            },
            "metadata": self.metadata,
        }

    def print_summary(self) -> str:
        """Generate a human-readable summary string."""
        lines = []
        lines.append("=" * 70)
        lines.append("CROSS-DATASET BENCHMARK SUMMARY")
        lines.append("=" * 70)

        lines.append("\n--- Per-Dataset Rankings (by F1) ---")
        for ds_name, entries in sorted(self.per_dataset_rankings.items()):
            lines.append(f"\n  {ds_name}:")
            for e in entries:
                lines.append(f"    #{e.rank} {e.tool_name}: F1={e.value:.4f}")

        lines.append("\n--- Overall Rankings (by Mean F1) ---")
        if "f1" in self.overall_rankings:
            for e in self.overall_rankings["f1"]:
                lines.append(
                    f"  #{e.rank} {e.tool_name}: "
                    f"F1={e.value:.4f} (+/- {e.std:.4f}) "
                    f"[{e.dataset_count} datasets]"
                )

        lines.append("\n--- Stability Rankings ---")
        for e in self.stability_rankings:
            lines.append(f"  #{e.rank} {e.tool_name}: Stability={e.value:.4f}")

        lines.append("\n--- Per-Tool Averages ---")
        for tool_name, tool_res in sorted(self.tool_results.items()):
            tool_res.compute_aggregates()
            lines.append(f"\n  {tool_name} ({len(tool_res.dataset_results)} datasets):")
            for metric in ["f1", "precision", "recall", "roc_auc", "pr_auc", "accuracy"]:
                mean_val = tool_res.mean_metrics.get(metric, 0.0)
                std_val = tool_res.std_metrics.get(metric, 0.0)
                lines.append(f"    {metric:12s}: {mean_val:.4f} (+/- {std_val:.4f})")
            lines.append(f"    {'stability':12s}: {tool_res.stability_score:.4f}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)
