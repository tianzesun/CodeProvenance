"""Phase 7: Report Generation.

Generates reports from evaluation results:
- JSON reports (authoritative)
- HTML reports (human readable)
- LaTeX reports (for papers)

Input: EvaluationResult + config
Output: ReportOutput

Usage:
    from benchmark.pipeline.phases.report import ReportingPhase

    phase = ReportingPhase()
    report = phase.execute(evaluation_result, config)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ReportOutput:
    """Report generation output.
    
    Attributes:
        json_path: Path to JSON report.
        html_path: Path to HTML report.
        latex_path: Path to LaTeX report.
        metadata: Additional metadata.
    """
    json_path: Optional[str] = None
    html_path: Optional[str] = None
    latex_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReportingPhase:
    """Phase 7: Report Generation.
    
    This phase is responsible for:
    - Generating JSON reports (authoritative)
    - Generating HTML reports (human readable)
    - Generating LaTeX reports (for papers)
    
    Input: EvaluationResult from evaluation phase
    Output: ReportOutput with file paths
    
    Usage:
        phase = ReportingPhase()
        report = phase.execute(evaluation_result, config)
    """
    
    def execute(
        self,
        evaluation_result: Any,
        config: Dict[str, Any],
    ) -> ReportOutput:
        """Execute reporting phase.
        
        Args:
            evaluation_result: EvaluationResult from evaluation phase.
            config: Configuration for reporting.
                - output_dir: Output directory (default: reports/)
                - generate_json: Generate JSON report (default: True)
                - generate_html: Generate HTML report (default: False)
                - generate_latex: Generate LaTeX report (default: False)
                - engine_name: Engine name for report
                - dataset_name: Dataset name for report
            
        Returns:
            ReportOutput with file paths.
        """
        output_dir = Path(config.get('output_dir', 'reports/'))
        generate_json = config.get('generate_json', True)
        generate_html = config.get('generate_html', False)
        generate_latex = config.get('generate_latex', False)
        engine_name = config.get('engine_name', 'unknown')
        dataset_name = config.get('dataset_name', 'unknown')
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        report_output = ReportOutput(
            metadata={
                'timestamp': timestamp,
                'engine_name': engine_name,
                'dataset_name': dataset_name,
            }
        )
        
        # Generate JSON report
        if generate_json:
            json_path = self._generate_json_report(
                evaluation_result, output_dir, timestamp, engine_name, dataset_name
            )
            report_output.json_path = str(json_path)
        
        # Generate HTML report
        if generate_html:
            html_path = self._generate_html_report(
                evaluation_result, output_dir, timestamp, engine_name, dataset_name
            )
            report_output.html_path = str(html_path)
        
        # Generate LaTeX report
        if generate_latex:
            latex_path = self._generate_latex_report(
                evaluation_result, output_dir, timestamp, engine_name, dataset_name
            )
            report_output.latex_path = str(latex_path)
        
        return report_output
    
    def _generate_json_report(
        self,
        evaluation_result: Any,
        output_dir: Path,
        timestamp: str,
        engine_name: str,
        dataset_name: str,
    ) -> Path:
        """Generate JSON report.
        
        Args:
            evaluation_result: Evaluation result.
            output_dir: Output directory.
            timestamp: Timestamp string.
            engine_name: Engine name.
            dataset_name: Dataset name.
            
        Returns:
            Path to generated JSON file.
        """
        json_path = output_dir / f"benchmark_{timestamp}.json"
        
        report_data = {
            "metadata": {
                "timestamp": timestamp,
                "engine": engine_name,
                "dataset": dataset_name,
            },
            "metrics": {
                "precision": getattr(evaluation_result, 'precision', 0.0),
                "recall": getattr(evaluation_result, 'recall', 0.0),
                "f1": getattr(evaluation_result, 'f1', 0.0),
                "accuracy": getattr(evaluation_result, 'accuracy', 0.0),
                "map_score": getattr(evaluation_result, 'map_score', 0.0),
                "mrr_score": getattr(evaluation_result, 'mrr_score', 0.0),
                "threshold": getattr(evaluation_result, 'threshold', 0.5),
            },
            "confusion_matrix": {
                "tp": getattr(evaluation_result, 'tp', 0),
                "fp": getattr(evaluation_result, 'fp', 0),
                "tn": getattr(evaluation_result, 'tn', 0),
                "fn": getattr(evaluation_result, 'fn', 0),
            },
        }
        
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        return json_path
    
    def _generate_html_report(
        self,
        evaluation_result: Any,
        output_dir: Path,
        timestamp: str,
        engine_name: str,
        dataset_name: str,
    ) -> Path:
        """Generate HTML report.
        
        Args:
            evaluation_result: Evaluation result.
            output_dir: Output directory.
            timestamp: Timestamp string.
            engine_name: Engine name.
            dataset_name: Dataset name.
            
        Returns:
            Path to generated HTML file.
        """
        html_path = output_dir / f"report_{timestamp}.html"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Report - {engine_name} on {dataset_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .metric {{ font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Benchmark Report</h1>
    <p><strong>Engine:</strong> {engine_name}</p>
    <p><strong>Dataset:</strong> {dataset_name}</p>
    <p><strong>Timestamp:</strong> {timestamp}</p>
    
    <h2>Metrics</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
        <tr>
            <td class="metric">Precision</td>
            <td>{getattr(evaluation_result, 'precision', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">Recall</td>
            <td>{getattr(evaluation_result, 'recall', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">F1 Score</td>
            <td>{getattr(evaluation_result, 'f1', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">Accuracy</td>
            <td>{getattr(evaluation_result, 'accuracy', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">MAP Score</td>
            <td>{getattr(evaluation_result, 'map_score', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">MRR Score</td>
            <td>{getattr(evaluation_result, 'mrr_score', 0.0):.4f}</td>
        </tr>
        <tr>
            <td class="metric">Threshold</td>
            <td>{getattr(evaluation_result, 'threshold', 0.5):.2f}</td>
        </tr>
    </table>
    
    <h2>Confusion Matrix</h2>
    <table>
        <tr>
            <th></th>
            <th>Predicted Positive</th>
            <th>Predicted Negative</th>
        </tr>
        <tr>
            <td><strong>Actual Positive</strong></td>
            <td>{getattr(evaluation_result, 'tp', 0)}</td>
            <td>{getattr(evaluation_result, 'fn', 0)}</td>
        </tr>
        <tr>
            <td><strong>Actual Negative</strong></td>
            <td>{getattr(evaluation_result, 'fp', 0)}</td>
            <td>{getattr(evaluation_result, 'tn', 0)}</td>
        </tr>
    </table>
</body>
</html>
"""
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        return html_path
    
    def _generate_latex_report(
        self,
        evaluation_result: Any,
        output_dir: Path,
        timestamp: str,
        engine_name: str,
        dataset_name: str,
    ) -> Path:
        """Generate LaTeX report.
        
        Args:
            evaluation_result: Evaluation result.
            output_dir: Output directory.
            timestamp: Timestamp string.
            engine_name: Engine name.
            dataset_name: Dataset name.
            
        Returns:
            Path to generated LaTeX file.
        """
        latex_path = output_dir / f"report_{timestamp}.tex"
        
        latex_content = f"""\\documentclass{{article}}
\\usepackage{{booktabs}}
\\usepackage{{graphicx}}

\\title{{Benchmark Report: {engine_name} on {dataset_name}}}
\\author{{CodeProvenance}}
\\date{{{timestamp}}}

\\begin{{document}}

\\maketitle

\\section{{Results}}

\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{lr}}
\\toprule
\\textbf{{Metric}} & \\textbf{{Value}} \\\\
\\midrule
Precision & {getattr(evaluation_result, 'precision', 0.0):.4f} \\\\
Recall & {getattr(evaluation_result, 'recall', 0.0):.4f} \\\\
F1 Score & {getattr(evaluation_result, 'f1', 0.0):.4f} \\\\
Accuracy & {getattr(evaluation_result, 'accuracy', 0.0):.4f} \\\\
MAP Score & {getattr(evaluation_result, 'map_score', 0.0):.4f} \\\\
MRR Score & {getattr(evaluation_result, 'mrr_score', 0.0):.4f} \\\\
Threshold & {getattr(evaluation_result, 'threshold', 0.5):.2f} \\\\
\\bottomrule
\\end{{tabular}}
\\caption{{Benchmark Metrics}}
\\end{{table}}

\\section{{Confusion Matrix}}

\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{lrr}}
\\toprule
& \\textbf{{Predicted Positive}} & \\textbf{{Predicted Negative}} \\\\
\\midrule
\\textbf{{Actual Positive}} & {getattr(evaluation_result, 'tp', 0)} & {getattr(evaluation_result, 'fn', 0)} \\\\
\\textbf{{Actual Negative}} & {getattr(evaluation_result, 'fp', 0)} & {getattr(evaluation_result, 'tn', 0)} \\\\
\\bottomrule
\\end{{tabular}}
\\caption{{Confusion Matrix}}
\\end{{table}}

\\end{{document}}
"""
        
        with open(latex_path, 'w') as f:
            f.write(latex_content)
        
        return latex_path