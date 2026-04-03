"""
IEEE-Style Report Generator for benchmark evaluation results.

Outputs:
- HTML (IEEE conference style)
- JSON (machine readable)
- PDF (via weasyprint/pdfkit)

Contains:
- Per-tool metrics table with CI
- Statistical significance matrix
- Tool ranking
- Reproducibility hash
"""

from __future__ import annotations

import hashlib
import json
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.comparison_engine import ToolRanking, ToolMetrics, SignificanceMatrix


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    report_id: str
    timestamp: str
    dataset_name: str
    dataset_size: int
    num_tools: int
    threshold: float
    ranking: ToolRanking
    tool_scores: Dict[str, List[float]]
    labels: List[int]
    reproducibility_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.reproducibility_hash:
            self.reproducibility_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = json.dumps({
            "dataset": self.dataset_name,
            "size": self.dataset_size,
            "num_tools": self.num_tools,
            "threshold": self.threshold,
            "rankings": [r.to_dict() for r in self.ranking.rankings],
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class IEEEStyleReportGenerator:
    """Generates IEEE-style HTML reports from benchmark results."""

    IEEE_CSS = """
    body { font-family: 'Times New Roman', Times, serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #000; }
    h1 { font-size: 18pt; text-align: center; margin-bottom: 5px; }
    h2 { font-size: 14pt; border-bottom: 1px solid #000; padding-bottom: 3px; margin-top: 20px; }
    h3 { font-size: 12pt; }
    .abstract { font-size: 10pt; font-style: italic; margin: 10px 40px; text-align: justify; }
    .author { font-size: 11pt; text-align: center; margin-bottom: 15px; }
    table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 10pt; }
    th, td { border: 1px solid #000; padding: 5px 8px; text-align: center; }
    th { background-color: #f0f0f0; font-weight: bold; }
    .sig-matrix td { font-family: monospace; font-size: 9pt; }
    .best { background-color: #e8f5e9; font-weight: bold; }
    .footer { font-size: 8pt; color: #666; text-align: center; margin-top: 30px; border-top: 1px solid #ccc; padding-top: 10px; }
    .hash { font-family: monospace; font-size: 9pt; background: #f5f5f5; padding: 5px; border-radius: 3px; }
    """

    def generate_html(self, report: BenchmarkReport) -> str:
        return self._build_html(report)

    def generate_json(self, report: BenchmarkReport) -> str:
        return json.dumps(self._build_json(report), indent=2)

    def save_html(self, report: BenchmarkReport, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.generate_html(report))

    def save_json(self, report: BenchmarkReport, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.generate_json(report))

    def save_pdf(self, report: BenchmarkReport, output_path: Path):
        html = self.generate_html(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import weasyprint
            weasyprint.HTML(string=html).write_pdf(str(output_path))
        except ImportError:
            try:
                import pdfkit
                pdfkit.from_string(html, str(output_path))
            except ImportError:
                output_path.with_suffix(".html").write_text(html)

    def _build_html(self, report: BenchmarkReport) -> str:
        ranking = report.ranking
        sig = ranking.significance_matrix

        rows = ""
        for i, m in enumerate(ranking.rankings):
            cls = " class=\"best\"" if i == 0 else ""
            ci_str = ""
            if m.f1_ci:
                ci_str = f"\u00b1{(m.f1_ci['ci_upper'] - m.f1_ci['ci_lower'])/2:.3f}"
            rows += (
                f"<tr{cls}>"
                f"<td>{m.rank_by_f1}</td>"
                f"<td>{m.tool_name}</td>"
                f"<td>{m.precision:.4f}</td>"
                f"<td>{m.recall:.4f}</td>"
                f"<td>{m.f1:.4f}{ci_str}</td>"
                f"<td>{m.accuracy:.4f}</td>"
                f"<td>{m.tp}</td><td>{m.fp}</td><td>{m.tn}</td><td>{m.fn}</td>"
                f"</tr>\n"
            )

        sig_rows = ""
        for row in sig.to_table():
            cells = "".join(f"<td>{c}</td>" for c in row)
            sig_rows += f"<tr>{cells}</tr>\n"

        sig_notes = (
            "<p><small>Significance levels: *** p&lt;0.001, ** p&lt;0.01, "
            "* p&lt;0.05, ns = not significant (McNemar's test with continuity correction)</small></p>"
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Benchmark Evaluation Report - {report.report_id}</title>
<style>{self.IEEE_CSS}</style>
</head>
<body>
<h1>Benchmark Evaluation Report</h1>
<div class="author">IntegrityDesk Evaluation Tribunal &mdash; {report.timestamp}</div>

<div class="abstract">
<p>This report presents a statistically rigorous comparison of {report.num_tools} plagiarism
detection tools evaluated on the <strong>{report.dataset_name}</strong> dataset
({report.dataset_size} pairs, threshold={report.threshold}).
Results include bootstrap confidence intervals (95%), McNemar's significance tests,
and effect size analysis.</p>
</div>

<h2>1. Tool Rankings</h2>
<table>
<tr><th>Rank</th><th>Tool</th><th>Precision</th><th>Recall</th><th>F1 (95% CI)</th><th>Accuracy</th><th>TP</th><th>FP</th><th>TN</th><th>FN</th></tr>
{rows}
</table>

<h2>2. Statistical Significance Matrix</h2>
<p>Pairwise McNemar's test p-values for F1 score comparison:</p>
<table class="sig-matrix">
{sig_rows}
</table>
{sig_notes}

<h2>3. Best Tool</h2>
<p><strong>{ranking.best_tool}</strong> ranks highest. {ranking.confidence_statement}</p>

<h2>4. Reproducibility</h2>
<div class="hash">Report Hash: {report.reproducibility_hash}</div>
<p>Dataset: {report.dataset_name} | Pairs: {report.dataset_size} | Threshold: {report.threshold}</p>
<p>Generated: {report.timestamp}</p>

<div class="footer">
IntegrityDesk Evaluation Tribunal &mdash; Automated Benchmark Report<br>
Reproducibility Hash: {report.reproducibility_hash}
</div>
</body>
</html>"""
        return html

    def _build_json(self, report: BenchmarkReport) -> Dict[str, Any]:
        return {
            "report_id": report.report_id,
            "timestamp": report.timestamp,
            "dataset": {
                "name": report.dataset_name,
                "size": report.dataset_size,
            },
            "threshold": report.threshold,
            "ranking": report.ranking.to_dict(),
            "reproducibility_hash": report.reproducibility_hash,
            "metadata": report.metadata,
        }


def generate_benchmark_report(
    tool_scores: Dict[str, List[float]],
    labels: List[int],
    dataset_name: str = "benchmark",
    threshold: float = 0.5,
    output_dir: Optional[Path] = None,
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> BenchmarkReport:
    """
    One-shot function: run full evaluation and generate report.

    Args:
        tool_scores: Dict mapping tool name to list of similarity scores.
        labels: Ground truth binary labels.
        dataset_name: Name of the dataset.
        threshold: Classification threshold.
        output_dir: Directory to save reports.
        ci_level: Confidence interval level.
        n_bootstrap: Number of bootstrap resamples.

    Returns:
        BenchmarkReport object.
    """
    from src.evaluation.comparison_engine import rank_tools

    ranking = rank_tools(tool_scores, labels, threshold, ci_level, n_bootstrap)

    report = BenchmarkReport(
        report_id=f"benchmark_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.datetime.now().isoformat(),
        dataset_name=dataset_name,
        dataset_size=len(labels),
        num_tools=len(tool_scores),
        threshold=threshold,
        ranking=ranking,
        tool_scores=tool_scores,
        labels=labels,
        metadata={
            "ci_level": ci_level,
            "n_bootstrap": n_bootstrap,
            "python_version": __import__("sys").version,
            "platform": __import__("platform").platform(),
        },
    )

    if output_dir:
        gen = IEEEStyleReportGenerator()
        gen.save_html(report, output_dir / "report.html")
        gen.save_json(report, output_dir / "report.json")
        gen.save_pdf(report, output_dir / "report.pdf")

    return report
