"""Publication-quality comparison report generator.

Produces both HTML and Markdown reports comparing IntegrityDesk against
competitor tools with:
  - Ranked overall metrics table (P / R / F1 / AUC)
  - Per-clone-type recall heatmap
  - Bootstrap 95% confidence intervals
  - McNemar statistical significance annotations
  - Capability comparison matrix (AI detection, language count)
  - Winner summary with delta analysis
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .runner import CompetitorBenchmarkResult, ToolMetrics, SignificanceResult


class CompetitorComparisonReport:
    """Generate publication-quality comparison reports."""

    def __init__(self, result: CompetitorBenchmarkResult):
        self.result = result

    # ==================================================================
    # Markdown report
    # ==================================================================

    def to_markdown(self) -> str:
        """Generate full Markdown report."""
        sections = [
            self._md_header(),
            self._md_summary(),
            self._md_overall_table(),
            self._md_clone_type_table(),
            self._md_confidence_intervals(),
            self._md_significance_tests(),
            self._md_capability_matrix(),
            self._md_optimal_thresholds(),
            self._md_methodology(),
            self._md_footer(),
        ]
        return "\n\n".join(sections)

    def _md_header(self) -> str:
        return (
            "# IntegrityDesk Competitive Benchmark Report\n\n"
            f"**Run ID:** `{self.result.run_id}`  \n"
            f"**Timestamp:** {self.result.timestamp}  \n"
            f"**Dataset:** {self.result.dataset_info['total_pairs']} pairs "
            f"(T1={self.result.dataset_info['type1']}, "
            f"T2={self.result.dataset_info['type2']}, "
            f"T3={self.result.dataset_info['type3']}, "
            f"T4={self.result.dataset_info['type4']}, "
            f"Neg={self.result.dataset_info['negative']})  \n"
            f"**Threshold:** {self.result.dataset_info['threshold']}  \n"
            f"**Seed:** {self.result.seed}"
        )

    def _md_summary(self) -> str:
        rankings = self.result.rankings
        f1_winner = rankings.get("f1", ["N/A"])[0]
        prec_winner = rankings.get("precision", ["N/A"])[0]
        rec_winner = rankings.get("recall", ["N/A"])[0]
        auc_winner = rankings.get("roc_auc", ["N/A"])[0]

        # Find IntegrityDesk metrics
        id_metrics = next((m for m in self.result.tool_metrics if m.tool_name == "IntegrityDesk"), None)
        best_competitor = next(
            (m for m in sorted(self.result.tool_metrics, key=lambda x: x.f1, reverse=True)
             if m.tool_name != "IntegrityDesk"),
            None,
        )

        delta = ""
        if id_metrics and best_competitor:
            f1_delta = id_metrics.f1 - best_competitor.f1
            sign = "+" if f1_delta >= 0 else ""
            delta = (
                f"\n\n**IntegrityDesk F1 advantage over best competitor "
                f"({best_competitor.tool_name}):** {sign}{f1_delta:.4f}"
            )

        return (
            "## Summary\n\n"
            f"| Metric | Winner |\n"
            f"|--------|--------|\n"
            f"| **F1-Score** | {f1_winner} |\n"
            f"| **Precision** | {prec_winner} |\n"
            f"| **Recall** | {rec_winner} |\n"
            f"| **ROC-AUC** | {auc_winner} |"
            f"{delta}"
        )

    def _md_overall_table(self) -> str:
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.f1, reverse=True)
        header = (
            "## Overall Performance (Ranked by F1)\n\n"
            "| Rank | Tool | Precision | Recall | F1-Score | ROC-AUC | Avg Precision | Accuracy |\n"
            "|------|------|-----------|--------|----------|---------|---------------|----------|\n"
        )
        rows = []
        for i, m in enumerate(sorted_metrics, 1):
            marker = " **" if m.tool_name == "IntegrityDesk" else ""
            end = "**" if marker else ""
            rows.append(
                f"| {i} | {marker}{m.tool_name}{end} | "
                f"{m.precision:.4f} | {m.recall:.4f} | {m.f1:.4f} | "
                f"{m.roc_auc:.4f} | {m.average_precision:.4f} | {m.accuracy:.4f} |"
            )
        return header + "\n".join(rows)

    def _md_clone_type_table(self) -> str:
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.f1, reverse=True)
        header = (
            "## Per-Clone-Type Recall\n\n"
            "| Tool | Type-1 (Exact) | Type-2 (Renamed) | Type-3 (Restructured) | Type-4 (Semantic) |\n"
            "|------|:--------------:|:----------------:|:---------------------:|:-----------------:|\n"
        )
        rows = []
        for m in sorted_metrics:
            t1 = m.type_recall.get(1, 0.0)
            t2 = m.type_recall.get(2, 0.0)
            t3 = m.type_recall.get(3, 0.0)
            t4 = m.type_recall.get(4, 0.0)
            rows.append(
                f"| {m.tool_name} | "
                f"{self._color_cell(t1)} | {self._color_cell(t2)} | "
                f"{self._color_cell(t3)} | {self._color_cell(t4)} |"
            )
        return header + "\n".join(rows)

    def _md_confidence_intervals(self) -> str:
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.f1, reverse=True)
        header = (
            "## 95% Bootstrap Confidence Intervals\n\n"
            "| Tool | Precision CI | Recall CI | F1 CI |\n"
            "|------|-------------|-----------|-------|\n"
        )
        rows = []
        for m in sorted_metrics:
            rows.append(
                f"| {m.tool_name} | "
                f"[{m.precision_ci[0]:.4f}, {m.precision_ci[1]:.4f}] | "
                f"[{m.recall_ci[0]:.4f}, {m.recall_ci[1]:.4f}] | "
                f"[{m.f1_ci[0]:.4f}, {m.f1_ci[1]:.4f}] |"
            )
        return header + "\n".join(rows)

    def _md_significance_tests(self) -> str:
        if not self.result.significance_tests:
            return "## Statistical Significance\n\nNo significance tests performed."

        header = (
            "## Statistical Significance (McNemar's Test)\n\n"
            "IntegrityDesk vs each competitor (α = 0.05):\n\n"
            "| Comparison | χ² Statistic | p-value | Significant? |\n"
            "|------------|:------------:|:-------:|:------------:|\n"
        )
        rows = []
        for s in self.result.significance_tests:
            sig_mark = "✓ Yes" if s.significant else "✗ No"
            rows.append(
                f"| {s.tool_a} vs {s.tool_b} | "
                f"{s.statistic:.4f} | {s.p_value:.4f} | {sig_mark} |"
            )
        return header + "\n".join(rows)

    def _md_capability_matrix(self) -> str:
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.f1, reverse=True)
        header = (
            "## Capability Comparison\n\n"
            "| Tool | AI/LLM Detection | Languages | Avg Time/Pair (ms) |\n"
            "|------|:-----------------:|:---------:|:------------------:|\n"
        )
        rows = []
        for m in sorted_metrics:
            ai = "✓" if m.ai_detection else "✗"
            rows.append(
                f"| {m.tool_name} | {ai} | {m.max_languages} | {m.avg_time_per_pair_ms:.2f} |"
            )
        return header + "\n".join(rows)

    def _md_optimal_thresholds(self) -> str:
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.optimal_f1, reverse=True)
        header = (
            "## Optimal Threshold Analysis\n\n"
            "| Tool | Optimal Threshold | F1 at Optimal | F1 at 0.50 |\n"
            "|------|:-----------------:|:-------------:|:----------:|\n"
        )
        rows = []
        for m in sorted_metrics:
            rows.append(
                f"| {m.tool_name} | {m.optimal_threshold:.2f} | "
                f"{m.optimal_f1:.4f} | {m.f1:.4f} |"
            )
        return header + "\n".join(rows)

    def _md_methodology(self) -> str:
        return (
            "## Methodology\n\n"
            "### Dataset\n"
            "Pairs are generated from canonical algorithm templates with deterministic\n"
            "transformations for each clone type:\n"
            "- **Type-1 (Exact):** Whitespace and comment modifications only.\n"
            "- **Type-2 (Renamed):** Systematic identifier renaming.\n"
            "- **Type-3 (Restructured):** Statement reordering, dead code insertion, loop restructuring.\n"
            "- **Type-4 (Semantic):** Functionally equivalent but structurally different implementations.\n"
            "- **Negative:** Unrelated algorithm pairs.\n\n"
            "### Competitor Baselines\n"
            "Competitor performance profiles are sourced from peer-reviewed literature:\n"
            "- Ragkhitwetsagul et al. (2019) — \"A comparison of code similarity analysers\"\n"
            "- Novak et al. (2019) — \"Source Code Plagiarism Detection: A Systematic Review\"\n"
            "- Svajlenko & Roy (2021) — BigCloneBench evaluations\n"
            "- Prechelt et al. (2002) — JPlag evaluation\n\n"
            "### Statistical Rigour\n"
            "- **Bootstrap CIs:** 1000-sample stratified bootstrap for 95% confidence intervals.\n"
            "- **McNemar's Test:** Paired significance test with continuity correction (χ², df=1).\n"
            "- **Deterministic:** All random processes are seeded for full reproducibility.\n"
            "- **Threshold sweep:** Optimal threshold found by exhaustive sweep [0.05, 0.95]."
        )

    def _md_footer(self) -> str:
        return (
            "---\n"
            f"*Generated by IntegrityDesk Benchmark Suite — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

    @staticmethod
    def _color_cell(val: float) -> str:
        """Format a recall value with visual indicator."""
        if val >= 0.90:
            return f"**{val:.4f}** 🟢"
        elif val >= 0.70:
            return f"{val:.4f} 🟡"
        elif val >= 0.50:
            return f"{val:.4f} 🟠"
        else:
            return f"{val:.4f} 🔴"

    # ==================================================================
    # HTML report
    # ==================================================================

    def to_html(self) -> str:
        """Generate publication-quality HTML report."""
        sorted_metrics = sorted(self.result.tool_metrics, key=lambda m: m.f1, reverse=True)

        # Build table rows
        overall_rows = ""
        for i, m in enumerate(sorted_metrics, 1):
            cls = ' class="highlight"' if m.tool_name == "IntegrityDesk" else ""
            overall_rows += (
                f"<tr{cls}>"
                f"<td>{i}</td>"
                f"<td><strong>{m.tool_name}</strong></td>"
                f"<td>{m.precision:.4f}</td>"
                f"<td>{m.recall:.4f}</td>"
                f"<td>{m.f1:.4f}</td>"
                f"<td>{m.roc_auc:.4f}</td>"
                f"<td>{m.accuracy:.4f}</td>"
                f"</tr>\n"
            )

        # Clone type rows
        clone_rows = ""
        for m in sorted_metrics:
            cls = ' class="highlight"' if m.tool_name == "IntegrityDesk" else ""
            clone_rows += (
                f"<tr{cls}>"
                f"<td><strong>{m.tool_name}</strong></td>"
                f"<td>{self._html_cell(m.type_recall.get(1, 0))}</td>"
                f"<td>{self._html_cell(m.type_recall.get(2, 0))}</td>"
                f"<td>{self._html_cell(m.type_recall.get(3, 0))}</td>"
                f"<td>{self._html_cell(m.type_recall.get(4, 0))}</td>"
                f"</tr>\n"
            )

        # CI rows
        ci_rows = ""
        for m in sorted_metrics:
            ci_rows += (
                f"<tr>"
                f"<td>{m.tool_name}</td>"
                f"<td>[{m.precision_ci[0]:.4f}, {m.precision_ci[1]:.4f}]</td>"
                f"<td>[{m.recall_ci[0]:.4f}, {m.recall_ci[1]:.4f}]</td>"
                f"<td>[{m.f1_ci[0]:.4f}, {m.f1_ci[1]:.4f}]</td>"
                f"</tr>\n"
            )

        # Significance rows
        sig_rows = ""
        for s in self.result.significance_tests:
            sig_cls = ' class="sig-yes"' if s.significant else ' class="sig-no"'
            sig_mark = "✓ Significant" if s.significant else "✗ Not Significant"
            sig_rows += (
                f"<tr>"
                f"<td>{s.tool_a} vs {s.tool_b}</td>"
                f"<td>{s.statistic:.4f}</td>"
                f"<td>{s.p_value:.4f}</td>"
                f"<td{sig_cls}>{sig_mark}</td>"
                f"</tr>\n"
            )

        # Winner info
        f1_winner = self.result.rankings.get("f1", ["N/A"])[0]
        id_m = next((m for m in self.result.tool_metrics if m.tool_name == "IntegrityDesk"), None)
        best_comp = next(
            (m for m in sorted_metrics if m.tool_name != "IntegrityDesk"), None
        )
        delta_str = ""
        if id_m and best_comp:
            d = id_m.f1 - best_comp.f1
            delta_str = f"<p class='delta'>IntegrityDesk F1 advantage: <strong>{'+' if d>=0 else ''}{d:.4f}</strong> over {best_comp.tool_name}</p>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IntegrityDesk Competitive Benchmark Report</title>
<style>
  :root {{ --primary: #1a56db; --success: #059669; --warning: #d97706; --danger: #dc2626; --bg: #f8fafc; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: #1e293b; line-height: 1.6; padding: 2rem; max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: var(--primary); border-bottom: 3px solid var(--primary); padding-bottom: 0.5rem; margin-bottom: 1rem; }}
  h2 {{ color: #334155; margin: 2rem 0 1rem; border-left: 4px solid var(--primary); padding-left: 0.75rem; }}
  .meta {{ background: #e0e7ff; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-size: 0.9rem; }}
  .delta {{ background: #d1fae5; padding: 0.75rem; border-radius: 6px; margin: 1rem 0; font-size: 1.1rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th {{ background: #1e40af; color: white; padding: 12px 16px; text-align: left; font-weight: 600; }}
  td {{ padding: 10px 16px; border-bottom: 1px solid #e2e8f0; }}
  tr:nth-child(even) {{ background: #f1f5f9; }}
  tr:hover {{ background: #e0e7ff; }}
  tr.highlight {{ background: #dbeafe !important; font-weight: 600; }}
  .cell-high {{ background: #d1fae5; color: #065f46; font-weight: 700; }}
  .cell-med {{ background: #fef3c7; color: #92400e; }}
  .cell-low {{ background: #fee2e2; color: #991b1b; }}
  .sig-yes {{ color: var(--success); font-weight: 700; }}
  .sig-no {{ color: #94a3b8; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #cbd5e1; font-size: 0.85rem; color: #64748b; }}
</style>
</head>
<body>
<h1>IntegrityDesk Competitive Benchmark Report</h1>

<div class="meta">
  <strong>Run ID:</strong> {self.result.run_id} &nbsp;|&nbsp;
  <strong>Timestamp:</strong> {self.result.timestamp} &nbsp;|&nbsp;
  <strong>Dataset:</strong> {self.result.dataset_info['total_pairs']} pairs &nbsp;|&nbsp;
  <strong>Seed:</strong> {self.result.seed} &nbsp;|&nbsp;
  <strong>Threshold:</strong> {self.result.dataset_info['threshold']}
</div>

{delta_str}

<h2>Overall Performance (Ranked by F1)</h2>
<table>
  <thead><tr><th>#</th><th>Tool</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th><th>Accuracy</th></tr></thead>
  <tbody>{overall_rows}</tbody>
</table>

<h2>Per-Clone-Type Recall</h2>
<table>
  <thead><tr><th>Tool</th><th>Type-1 (Exact)</th><th>Type-2 (Renamed)</th><th>Type-3 (Restructured)</th><th>Type-4 (Semantic)</th></tr></thead>
  <tbody>{clone_rows}</tbody>
</table>

<h2>95% Bootstrap Confidence Intervals</h2>
<table>
  <thead><tr><th>Tool</th><th>Precision CI</th><th>Recall CI</th><th>F1 CI</th></tr></thead>
  <tbody>{ci_rows}</tbody>
</table>

<h2>Statistical Significance (McNemar's Test, α = 0.05)</h2>
<table>
  <thead><tr><th>Comparison</th><th>χ² Statistic</th><th>p-value</th><th>Result</th></tr></thead>
  <tbody>{sig_rows}</tbody>
</table>

<div class="footer">
  Generated by IntegrityDesk Benchmark Suite — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
  Competitor baselines sourced from Ragkhitwetsagul et al. (2019), Novak et al. (2019), Svajlenko &amp; Roy (2021).
</div>
</body>
</html>"""
        return html

    @staticmethod
    def _html_cell(val: float) -> str:
        if val >= 0.90:
            return f'<td class="cell-high">{val:.4f}</td>'
        elif val >= 0.60:
            return f'<td class="cell-med">{val:.4f}</td>'
        else:
            return f'<td class="cell-low">{val:.4f}</td>'

    # ==================================================================
    # Save helpers
    # ==================================================================

    def save_markdown(self, path: str = "reports/competitor/comparison_report.md") -> str:
        """Write Markdown report to file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_markdown(), encoding="utf-8")
        return str(p)

    def save_html(self, path: str = "reports/competitor/comparison_report.html") -> str:
        """Write HTML report to file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_html(), encoding="utf-8")
        return str(p)

    def save_all(self, output_dir: str = "reports/competitor") -> Dict[str, str]:
        """Save all report formats and return paths."""
        d = Path(output_dir)
        d.mkdir(parents=True, exist_ok=True)

        md_path = self.save_markdown(str(d / "comparison_report.md"))
        html_path = self.save_html(str(d / "comparison_report.html"))

        # Also save raw JSON
        json_path = str(d / "comparison_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.result.to_dict(), f, indent=2)

        return {
            "markdown": md_path,
            "html": html_path,
            "json": json_path,
        }
