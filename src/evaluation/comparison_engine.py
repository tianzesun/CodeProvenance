"""
Comparison Engine - Statistical tool ranking with significance matrix.

Answers: "Which tool is better?" statistically.
Produces:
- Per-tool metrics with bootstrap CIs
- Pairwise significance matrix (McNemar's test for all pairs)
- Tool ranking with confidence levels
- Effect size calculations (Cohen's d)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.evaluation.significance import (
    bootstrap_confidence_interval,
    mcnemar_test,
    McNemarResult,
)


@dataclass
class ToolMetrics:
    """Complete metrics for a single tool."""
    tool_name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    auc_roc: Optional[float] = None
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision_ci: Optional[Dict[str, float]] = None
    recall_ci: Optional[Dict[str, float]] = None
    f1_ci: Optional[Dict[str, float]] = None
    rank_by_f1: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "tool": self.tool_name,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn,
            "rank": self.rank_by_f1,
        }
        if self.f1_ci:
            d["f1_ci"] = f"[{self.f1_ci['ci_lower']:.3f}, {self.f1_ci['ci_upper']:.3f}]"
        if self.auc_roc is not None:
            d["auc_roc"] = round(self.auc_roc, 4)
        return d


@dataclass
class PairwiseSignificance:
    """Result of comparing two tools."""
    tool_a: str
    tool_b: str
    metric: str
    value_a: float
    value_b: float
    p_value: float
    is_significant: bool
    effect_size: float
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparison": f"{self.tool_a} vs {self.tool_b}",
            "metric": self.metric,
            f"{self.tool_a}": round(self.value_a, 4),
            f"{self.tool_b}": round(self.value_b, 4),
            "p_value": round(self.p_value, 6),
            "significant": self.is_significant,
            "effect_size": round(self.effect_size, 4),
            "interpretation": self.interpretation,
        }


@dataclass
class SignificanceMatrix:
    """Full pairwise significance matrix for all tools."""
    tools: List[str]
    metric: str
    matrix: Dict[Tuple[str, str], PairwiseSignificance] = field(default_factory=dict)

    def get(self, a: str, b: str) -> Optional[PairwiseSignificance]:
        return self.matrix.get((a, b)) or self.matrix.get((b, a))

    def to_table(self) -> List[List[str]]:
        rows = [[""] + self.tools]
        for a in self.tools:
            row = [a]
            for b in self.tools:
                if a == b:
                    row.append("-")
                else:
                    comp = self.get(a, b)
                    if comp:
                        sig = "***" if comp.p_value < 0.001 else (
                            "**" if comp.p_value < 0.01 else (
                                "*" if comp.p_value < 0.05 else "ns"
                            )
                        )
                        row.append(f"{comp.p_value:.4f}{sig}")
                    else:
                        row.append("N/A")
            rows.append(row)
        return rows

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "tools": self.tools,
            "comparisons": {
                f"{a} vs {b}": v.to_dict()
                for (a, b), v in self.matrix.items()
                if a < b
            },
        }


@dataclass
class ToolRanking:
    """Complete ranking of tools with statistical backing."""
    rankings: List[ToolMetrics]
    significance_matrix: SignificanceMatrix
    best_tool: str
    confidence_statement: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_tool": self.best_tool,
            "confidence_statement": self.confidence_statement,
            "rankings": [r.to_dict() for r in self.rankings],
            "significance_matrix": self.significance_matrix.to_dict(),
        }

    def summary_table(self) -> str:
        lines = [
            "=" * 80,
            "TOOL RANKING (by F1 score)",
            "=" * 80,
            f"{'Rank':<6}{'Tool':<15}{'Precision':<12}{'Recall':<10}{'F1':<10}{'95% CI':<20}",
            "-" * 80,
        ]
        for m in self.rankings:
            ci_str = ""
            if m.f1_ci:
                ci_str = f"[{m.f1_ci['ci_lower']:.3f}, {m.f1_ci['ci_upper']:.3f}]"
            lines.append(
                f"{m.rank_by_f1:<6}{m.tool_name:<15}{m.precision:<12.4f}"
                f"{m.recall:<10.4f}{m.f1:<10.4f}{ci_str:<20}"
            )
        lines.append("=" * 80)
        lines.append("")
        lines.append("SIGNIFICANCE MATRIX (McNemar's test p-values)")
        lines.append("-" * 80)
        for row in self.significance_matrix.to_table():
            lines.append("  ".join(f"{c:>14}" for c in row))
        lines.append("")
        lines.append(f"Best tool: {self.best_tool}")
        lines.append(f"{self.confidence_statement}")
        lines.append("=" * 80)
        return "\n".join(lines)


def _cohens_d(group1: List[int], group2: List[int]) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    mean1 = sum(group1) / n1
    mean2 = sum(group2) / n2
    var1 = sum((x - mean1) ** 2 for x in group1) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in group2) / (n2 - 1)
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return float('inf') if mean1 != mean2 else 0.0
    return (mean1 - mean2) / pooled_std


def _interpret_effect_size(d: float) -> str:
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def build_significance_matrix(
    tool_scores: Dict[str, List[float]],
    labels: List[int],
    threshold: float = 0.5,
    metric: str = "f1",
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> SignificanceMatrix:
    """
    Build a full pairwise significance matrix for all tools.

    Args:
        tool_scores: Dict mapping tool name to list of similarity scores.
        labels: Ground truth binary labels (same for all tools).
        threshold: Classification threshold.
        metric: Metric for comparison ('f1', 'precision', 'recall').
        ci_level: Confidence interval level.
        n_bootstrap: Number of bootstrap resamples.

    Returns:
        SignificanceMatrix with all pairwise comparisons.
    """
    tools = sorted(tool_scores.keys())
    matrix: Dict[Tuple[str, str], PairwiseSignificance] = {}

    for i, a in enumerate(tools):
        for j, b in enumerate(tools):
            if i >= j:
                continue

            scores_a = tool_scores[a]
            scores_b = tool_scores[b]

            ci_a = bootstrap_confidence_interval(scores_a, labels, threshold, ci_level, n_bootstrap)
            ci_b = bootstrap_confidence_interval(scores_b, labels, threshold, ci_level, n_bootstrap)

            pred_a = [1 if s >= threshold else 0 for s in scores_a]
            pred_b = [1 if s >= threshold else 0 for s in scores_b]

            mc = mcnemar_test(labels, pred_a, pred_b)

            value_a = ci_a[metric]["value"]
            value_b = ci_b[metric]["value"]

            effect = _cohens_d(pred_a, pred_b)
            effect_label = _interpret_effect_size(effect)

            if mc.is_significant:
                winner = a if value_a > value_b else b
                interp = (
                    f"{winner} is significantly better ({metric}: "
                    f"{max(value_a, value_b):.4f} vs {min(value_a, value_b):.4f}, "
                    f"p={mc.p_value:.4f}, effect={effect_label})"
                )
            else:
                interp = (
                    f"No significant difference ({metric}: {value_a:.4f} vs {value_b:.4f}, "
                    f"p={mc.p_value:.4f}, effect={effect_label})"
                )

            comp = PairwiseSignificance(
                tool_a=a,
                tool_b=b,
                metric=metric,
                value_a=value_a,
                value_b=value_b,
                p_value=mc.p_value,
                is_significant=mc.is_significant,
                effect_size=effect,
                interpretation=interp,
            )
            matrix[(a, b)] = comp
            matrix[(b, a)] = PairwiseSignificance(
                tool_a=b, tool_b=a, metric=metric,
                value_b=value_a, value_a=value_b,
                p_value=mc.p_value, is_significant=mc.is_significant,
                effect_size=-effect, interpretation=interp,
            )

    return SignificanceMatrix(tools=tools, metric=metric, matrix=matrix)


def rank_tools(
    tool_scores: Dict[str, List[float]],
    labels: List[int],
    threshold: float = 0.5,
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> ToolRanking:
    """
    Rank all tools statistically with confidence intervals and significance matrix.

    Args:
        tool_scores: Dict mapping tool name to list of similarity scores.
        labels: Ground truth binary labels.
        threshold: Classification threshold.
        ci_level: Confidence interval level.
        n_bootstrap: Number of bootstrap resamples.

    Returns:
        ToolRanking with full statistical analysis.
    """
    metrics_list = []

    for tool_name, scores in tool_scores.items():
        ci = bootstrap_confidence_interval(scores, labels, threshold, ci_level, n_bootstrap)

        tp = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 1)
        fp = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 0)
        tn = sum(1 for s, l in zip(scores, labels) if s < threshold and l == 0)
        fn = sum(1 for s, l in zip(scores, labels) if s < threshold and l == 1)

        precision = ci["precision"]["value"]
        recall = ci["recall"]["value"]
        f1 = ci["f1"]["value"]
        accuracy = (tp + tn) / len(labels) if labels else 0.0

        metrics_list.append(ToolMetrics(
            tool_name=tool_name,
            precision=precision,
            recall=recall,
            f1=f1,
            accuracy=accuracy,
            tp=tp, fp=fp, tn=tn, fn=fn,
            precision_ci=ci["precision"],
            recall_ci=ci["recall"],
            f1_ci=ci["f1"],
        ))

    metrics_list.sort(key=lambda m: m.f1, reverse=True)
    for i, m in enumerate(metrics_list):
        m.rank_by_f1 = i + 1

    if not metrics_list:
        return ToolRanking(
            rankings=[],
            significance_matrix=SignificanceMatrix(tools=[], metric="f1"),
            best_tool="",
            confidence_statement="No tools evaluated.",
        )

    sig_matrix = build_significance_matrix(
        tool_scores, labels, threshold, "f1", ci_level, n_bootstrap,
    )

    best = metrics_list[0]
    second = metrics_list[1] if len(metrics_list) > 1 else None

    if second:
        comp = sig_matrix.get(best.tool_name, second.tool_name)
        if comp and comp.is_significant:
            conf_stmt = (
                f"{best.tool_name} is statistically significantly better than "
                f"{second.tool_name} (p={comp.p_value:.4f}, "
                f"F1: {best.f1:.4f} vs {second.f1:.4f})"
            )
        else:
            conf_stmt = (
                f"{best.tool_name} ranks highest (F1={best.f1:.4f}) but the difference "
                f"from {second.tool_name} (F1={second.f1:.4f}) is not statistically "
                f"significant (p={comp.p_value if comp else 'N/A':.4f})"
            )
    else:
        conf_stmt = f"{best.tool_name} is the only tool evaluated (F1={best.f1:.4f})"

    return ToolRanking(
        rankings=metrics_list,
        significance_matrix=sig_matrix,
        best_tool=best.tool_name,
        confidence_statement=conf_stmt,
    )
