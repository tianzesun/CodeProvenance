"""Table generation for certification reports.

Generates publication-grade tables for:
- Main results comparison
- Statistical significance tests
- Stratified analysis
- Effect size summaries
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass
class ResultsTable:
    """Table for main results comparison."""
    engines: List[str] = field(default_factory=list)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    confidence_intervals: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    title: str = "Main Results"

    def add_engine(
        self,
        engine_name: str,
        metrics: Dict[str, float],
        confidence_intervals: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> None:
        """Add an engine to the table."""
        self.engines.append(engine_name)
        for metric_name, value in metrics.items():
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            self.metrics[metric_name].append(value)
        if confidence_intervals:
            for metric_name, ci in confidence_intervals.items():
                if metric_name not in self.confidence_intervals:
                    self.confidence_intervals[metric_name] = []
                self.confidence_intervals[metric_name].append(ci)

    def to_markdown(self) -> str:
        """Generate markdown table."""
        if not self.engines:
            return f"## {self.title}\n\nNo data available."
        metric_names = list(self.metrics.keys())
        header = "| Engine |"
        separator = "|--------|"
        for metric in metric_names:
            header += f" {metric} |"
            separator += "--------|"
        rows = []
        for i, engine in enumerate(self.engines):
            row = f"| {engine} |"
            for metric in metric_names:
                values = self.metrics.get(metric, [])
                if i < len(values):
                    value = values[i]
                    if metric in self.confidence_intervals:
                        cis = self.confidence_intervals[metric]
                        if i < len(cis):
                            ci_lower, ci_upper = cis[i]
                            row += f" {value:.4f} [{ci_lower:.4f}, {ci_upper:.4f}] |"
                        else:
                            row += f" {value:.4f} |"
                    else:
                        row += f" {value:.4f} |"
                else:
                    row += " N/A |"
            rows.append(row)
        lines = [f"## {self.title}", "", header, separator] + rows
        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate HTML table."""
        if not self.engines:
            return f"<h3>{self.title}</h3><p>No data available.</p>"
        metric_names = list(self.metrics.keys())
        html = [f"<h3>{self.title}</h3>", '<table class="results-table">', "<thead>", "<tr>", "<th>Engine</th>"]
        for metric in metric_names:
            html.append(f"<th>{metric}</th>")
        html.extend(["</tr>", "</thead>", "<tbody>"])
        for i, engine in enumerate(self.engines):
            html.append("<tr>")
            html.append(f"<td><strong>{engine}</strong></td>")
            for metric in metric_names:
                values = self.metrics.get(metric, [])
                if i < len(values):
                    value = values[i]
                    if metric in self.confidence_intervals:
                        cis = self.confidence_intervals[metric]
                        if i < len(cis):
                            ci_lower, ci_upper = cis[i]
                            html.append(f"<td>{value:.4f}<br><span class=\"ci\">[{ci_lower:.4f}, {ci_upper:.4f}]</span></td>")
                        else:
                            html.append(f"<td>{value:.4f}</td>")
                    else:
                        html.append(f"<td>{value:.4f}</td>")
                else:
                    html.append("<td>N/A</td>")
            html.append("</tr>")
        html.extend(["</tbody>", "</table>"])
        return "\n".join(html)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "engines": self.engines,
            "metrics": self.metrics,
            "confidence_intervals": {k: [list(ci) for ci in v] for k, v in self.confidence_intervals.items()},
        }


@dataclass
class SignificanceTable:
    """Table for statistical significance tests."""
    comparisons: List[str] = field(default_factory=list)
    mcnemar_pvalues: List[float] = field(default_factory=list)
    wilcoxon_pvalues: List[float] = field(default_factory=list)
    effect_sizes: List[float] = field(default_factory=list)
    significant: List[bool] = field(default_factory=list)
    title: str = "Statistical Significance"

    def add_comparison(self, comparison_name: str, mcnemar_pvalue: float, wilcoxon_pvalue: float, effect_size: float, significant: bool) -> None:
        """Add a comparison to the table."""
        self.comparisons.append(comparison_name)
        self.mcnemar_pvalues.append(mcnemar_pvalue)
        self.wilcoxon_pvalues.append(wilcoxon_pvalue)
        self.effect_sizes.append(effect_size)
        self.significant.append(significant)

    def to_markdown(self) -> str:
        """Generate markdown table."""
        if not self.comparisons:
            return f"## {self.title}\n\nNo comparisons available."
        lines = [f"## {self.title}", "", "| Comparison | McNemar p-value | Wilcoxon p-value | Effect Size (d) | Significant |", "|------------|-----------------|------------------|-----------------|-------------|"]
        for i, comparison in enumerate(self.comparisons):
            mcn_p = self.mcnemar_pvalues[i] if i < len(self.mcnemar_pvalues) else 1.0
            wil_p = self.wilcoxon_pvalues[i] if i < len(self.wilcoxon_pvalues) else 1.0
            effect = self.effect_sizes[i] if i < len(self.effect_sizes) else 0.0
            sig = self.significant[i] if i < len(self.significant) else False
            sig_str = "Yes" if sig else "No"
            lines.append(f"| {comparison} | {mcn_p:.6f} | {wil_p:.6f} | {effect:.4f} | {sig_str} |")
        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate HTML table."""
        if not self.comparisons:
            return f"<h3>{self.title}</h3><p>No comparisons available.</p>"
        html = [f"<h3>{self.title}</h3>", '<table class="significance-table">', "<thead>", "<tr>", "<th>Comparison</th>", "<th>McNemar p-value</th>", "<th>Wilcoxon p-value</th>", "<th>Effect Size (d)</th>", "<th>Significant</th>", "</tr>", "</thead>", "<tbody>"]
        for i, comparison in enumerate(self.comparisons):
            mcn_p = self.mcnemar_pvalues[i] if i < len(self.mcnemar_pvalues) else 1.0
            wil_p = self.wilcoxon_pvalues[i] if i < len(self.wilcoxon_pvalues) else 1.0
            effect = self.effect_sizes[i] if i < len(self.effect_sizes) else 0.0
            sig = self.significant[i] if i < len(self.significant) else False
            sig_class = "significant" if sig else "not-significant"
            sig_str = "✓ Yes" if sig else "✗ No"
            html.append(f'<tr class="{sig_class}">')
            html.append(f"<td><strong>{comparison}</strong></td>")
            html.append(f"<td>{mcn_p:.6f}</td>")
            html.append(f"<td>{wil_p:.6f}</td>")
            html.append(f"<td>{effect:.4f}</td>")
            html.append(f"<td>{sig_str}</td>")
            html.append("</tr>")
        html.extend(["</tbody>", "</table>"])
        return "\n".join(html)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"title": self.title, "comparisons": self.comparisons, "mcnemar_pvalues": self.mcnemar_pvalues, "wilcoxon_pvalues": self.wilcoxon_pvalues, "effect_sizes": self.effect_sizes, "significant": self.significant}


@dataclass
class StratifiedTable:
    """Table for stratified analysis results."""
    stratum_name: str = "Stratum"
    strata: List[Union[int, str]] = field(default_factory=list)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    sample_sizes: List[int] = field(default_factory=list)
    title: str = "Stratified Results"

    def add_stratum(self, stratum_value: Union[int, str], metrics: Dict[str, float], sample_size: int = 0) -> None:
        """Add a stratum to the table."""
        self.strata.append(stratum_value)
        self.sample_sizes.append(sample_size)
        for metric_name, value in metrics.items():
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            self.metrics[metric_name].append(value)

    def to_markdown(self) -> str:
        """Generate markdown table."""
        if not self.strata:
            return f"## {self.title}\n\nNo data available."
        metric_names = list(self.metrics.keys())
        header = f"| {self.stratum_name} | N |"
        separator = "|--------|---|"
        for metric in metric_names:
            header += f" {metric} |"
            separator += "--------|"
        lines = [f"## {self.title}", "", header, separator]
        for i, stratum in enumerate(self.strata):
            n = self.sample_sizes[i] if i < len(self.sample_sizes) else 0
            row = f"| {stratum} | {n} |"
            for metric in metric_names:
                values = self.metrics.get(metric, [])
                if i < len(values):
                    row += f" {values[i]:.4f} |"
                else:
                    row += " N/A |"
            lines.append(row)
        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate HTML table."""
        if not self.strata:
            return f"<h3>{self.title}</h3><p>No data available.</p>"
        metric_names = list(self.metrics.keys())
        html = [f"<h3>{self.title}</h3>", '<table class="stratified-table">', "<thead>", "<tr>", f"<th>{self.stratum_name}</th>", "<th>N</th>"]
        for metric in metric_names:
            html.append(f"<th>{metric}</th>")
        html.extend(["</tr>", "</thead>", "<tbody>"])
        for i, stratum in enumerate(self.strata):
            n = self.sample_sizes[i] if i < len(self.sample_sizes) else 0
            html.append("<tr>")
            html.append(f"<td><strong>{stratum}</strong></td>")
            html.append(f"<td>{n}</td>")
            for metric in metric_names:
                values = self.metrics.get(metric, [])
                if i < len(values):
                    html.append(f"<td>{values[i]:.4f}</td>")
                else:
                    html.append("<td>N/A</td>")
            html.append("</tr>")
        html.extend(["</tbody>", "</table>"])
        return "\n".join(html)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"title": self.title, "stratum_name": self.stratum_name, "strata": self.strata, "sample_sizes": self.sample_sizes, "metrics": self.metrics}


def format_pvalue(pvalue: float) -> str:
    """Format p-value for display."""
    if pvalue < 0.001:
        return "<0.001"
    elif pvalue < 0.01:
        return f"{pvalue:.4f}"
    else:
        return f"{pvalue:.3f}"


def format_effect_size(effect: float, method: str = "cohens_d") -> str:
    """Format effect size with interpretation."""
    if method == "cohens_d":
        if abs(effect) < 0.2:
            return f"{effect:.3f} (negligible)"
        elif abs(effect) < 0.5:
            return f"{effect:.3f} (small)"
        elif abs(effect) < 0.8:
            return f"{effect:.3f} (medium)"
        else:
            return f"{effect:.3f} (large)"
    elif method == "cliffs_delta":
        if abs(effect) < 0.147:
            return f"{effect:.3f} (negligible)"
        elif abs(effect) < 0.33:
            return f"{effect:.3f} (small)"
        elif abs(effect) < 0.474:
            return f"{effect:.3f} (medium)"
        else:
            return f"{effect:.3f} (large)"
    else:
        return f"{effect:.3f}"