"""Report generation for EvalForge v2.

Generates:
- JSON machine-readable results
- LaTeX tables for publication
- HTML dashboard
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from src.backend.evalforge.core import BenchmarkResult
from src.backend.evalforge.pipelines.runner import BenchmarkRunner


@dataclass
class ReportGenerator:
    """Generates benchmark reports in multiple formats."""
    
    runner: BenchmarkRunner
    evaluation: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.evaluation is None:
            self.evaluation = self.runner.evaluate()
    
    def to_json(self, path: Path) -> None:
        """Save full report as JSON."""
        report = {
            "dataset_name": self.runner.dataset.name,
            "detectors": [d.name for d in self.runner.detectors],
            "n_pairs": len(self.runner.dataset),
            "evaluation": self.evaluation,
            "results": [
                {
                    "pair_id": r.pair_id,
                    "detector": r.detector_name,
                    "score": round(r.score, 4),
                    "confidence": round(r.confidence, 4),
                    "label": r.label,
                    "transform_path": r.transform_path,
                }
                for r in self.runner.results
            ]
        }
        path.write_text(json.dumps(report, indent=2))
    
    def to_latex_table(self, path: Path) -> None:
        """Generate LaTeX table for publication."""
        latex = r"""\begin{table*}[t]
\centering
\caption{Plagiarism detection performance comparison. Higher is better.}
\label{tab:results}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrrrrrr}
\toprule
Detector & Precision & Recall & F1 & ROC-AUC & PR-AUC & ECE \\
\midrule
"""
        
        for detector_name, data in self.evaluation.items():
            if detector_name == "agreement":
                continue
            
            metrics = data["metrics"]
            latex += f"{detector_name.title()} & "
            latex += f"{metrics['precision']:.3f} & "
            latex += f"{metrics['recall']:.3f} & "
            latex += f"{metrics['f1']:.3f} & "
            latex += f"{metrics['roc_auc']:.3f} & "
            latex += f"{metrics['pr_auc']:.3f} & "
            latex += f"{metrics['ece']:.3f} \\\\\n"
        
        latex += r"""\bottomrule
\end{tabular}%
}
\end{table*}
"""
        path.write_text(latex)
    
    def to_html(self, path: Path) -> None:
        """Generate interactive HTML dashboard."""
        detector_names = [d for d in self.evaluation if d != "agreement"]
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>EvalForge Benchmark Report</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        .card {{ background: #f8fafc; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; font-weight: 600; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-size: 2rem; font-weight: 700; color: #0f172a; }}
        .metric-label {{ color: #64748b; font-size: 0.875rem; }}
    </style>
</head>
<body>
    <h1>EvalForge Benchmark Report</h1>
    <p>Dataset: <strong>{self.runner.dataset.name}</strong></p>
    <p>Pairs tested: <strong>{len(self.runner.dataset)}</strong></p>
    
    <div class="card">
        <h2>Performance Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Detector</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1</th>
                    <th>ROC-AUC</th>
                    <th>PR-AUC</th>
                    <th>ECE</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for detector_name, data in self.evaluation.items():
            if detector_name == "agreement":
                continue
            
            metrics = data["metrics"]
            html += f"""
                <tr>
                    <td><strong>{detector_name.title()}</strong></td>
                    <td>{metrics['precision']:.3f}</td>
                    <td>{metrics['recall']:.3f}</td>
                    <td><strong>{metrics['f1']:.3f}</strong></td>
                    <td>{metrics['roc_auc']:.3f}</td>
                    <td>{metrics['pr_auc']:.3f}</td>
                    <td>{metrics['ece']:.4f}</td>
                </tr>
"""
        
        html += f"""
            </tbody>
        </table>
    </div>
    
    <div class="card">
        <h2>Per Clone Type Performance</h2>
        <div class="metric-grid">
"""
        
        # Show per-clone-type performance for best detector
        best_detector = max(
            (d for d in self.evaluation if d != "agreement"),
            key=lambda d: self.evaluation[d]["metrics"]["f1"]
        )
        
        per_type = self.evaluation[best_detector]["metrics"]["per_clone_type"]
        clone_type_names = ["Unrelated", "Low Similarity", "Structural Clone", "Semantic Clone", "Exact Clone"]
        
        for clone_type, data in per_type.items():
            html += f"""
            <div class="metric">
                <div class="metric-value">{data['mean_score']:.2f}</div>
                <div class="metric-label">{clone_type_names[int(clone_type)]} (n={data['count']})</div>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        path.write_text(html)
    
    def summary(self) -> str:
        """Generate text summary."""
        lines = []
        lines.append(f"Benchmark Summary: {self.runner.dataset.name}")
        lines.append("=" * 50)
        lines.append(f"Total pairs: {len(self.runner.dataset)}")
        lines.append(f"Detectors: {len(self.runner.detectors)}")
        lines.append("")
        
        # Find best detector by F1
        best_f1 = 0.0
        best_detector = None
        
        for detector_name, data in self.evaluation.items():
            if detector_name == "agreement":
                continue
            
            f1 = data["metrics"]["f1"]
            if f1 > best_f1:
                best_f1 = f1
                best_detector = detector_name
        
        lines.append(f"Best performance: {best_detector} (F1 = {best_f1:.3f})")
        lines.append("")
        lines.append("All detectors:")
        
        for detector_name, data in self.evaluation.items():
            if detector_name == "agreement":
                continue
            
            metrics = data["metrics"]
            lines.append(f"  {detector_name:12}  F1: {metrics['f1']:.3f}  ROC-AUC: {metrics['roc_auc']:.3f}  PR-AUC: {metrics['pr_auc']:.3f}")
        
        return "\n".join(lines)


def generate_standard_report(runner: BenchmarkRunner, output_dir: Path) -> None:
    """Generate all standard report formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    reporter = ReportGenerator(runner)
    
    reporter.to_json(output_dir / "results.json")
    reporter.to_latex_table(output_dir / "results.tex")
    reporter.to_html(output_dir / "report.html")
    
    summary = reporter.summary()
    (output_dir / "summary.txt").write_text(summary)
    
    print(summary)
    print(f"\nReports saved to: {output_dir}")