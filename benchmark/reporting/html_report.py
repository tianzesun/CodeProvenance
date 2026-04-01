"""HTML report writer for benchmark results.

Provides human-readable HTML reports for visualization and sharing.
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #e3f2fd; border-radius: 4px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1976d2; }}
        .metric-label {{ color: #666; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>Generated: {timestamp}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        {summary_content}
    </div>
    
    <h2>Results by Engine</h2>
    {table_content}
</body>
</html>
"""


class HTMLReportWriter:
    """Writes benchmark results to HTML format.
    
    Usage:
        writer = HTMLReportWriter("report.html")
        writer.write(title, results)
    """
    
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
    
    def write(
        self,
        title: str,
        results: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """Write results to HTML file.
        
        Args:
            title: Report title.
            results: Benchmark results dict.
            metadata: Optional metadata dict.
            
        Returns:
            Path to written file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        summary_metrics = results.get('summary', {})
        summary_content = self._build_summary_metrics(summary_metrics)
        table_content = self._build_results_table(results.get('engine_results', []))
        
        html = HTML_TEMPLATE.format(
            title=title,
            timestamp=timestamp,
            summary_content=summary_content,
            table_content=table_content
        )
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            f.write(html)
        
        return str(self.output_path)
    
    def _build_summary_metrics(self, metrics: Dict[str, float]) -> str:
        """Build summary metrics HTML."""
        items = []
        for name, value in metrics.items():
            if isinstance(value, float):
                items.append(
                    f'<div class="metric">'
                    f'<div class="metric-value">{value:.4f}</div>'
                    f'<div class="metric-label">{name}</div>'
                    f'</div>'
                )
        return "".join(items)
    
    def _build_results_table(self, engine_results: List[Dict[str, Any]]) -> str:
        """Build results table HTML."""
        if not engine_results:
            return "<p>No engine results available.</p>"
        
        html = """<table>
            <thead>
                <tr>
                    <th>Engine</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1</th>
                    <th>Accuracy</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for engine in sorted(engine_results, key=lambda x: x.get('f1', 0), reverse=True):
            html += f"""<tr>
                <td>{engine.get('engine_name', 'Unknown')}</td>
                <td>{engine.get('precision', 0):.4f}</td>
                <td>{engine.get('recall', 0):.4f}</td>
                <td>{engine.get('f1', 0):.4f}</td>
                <td>{engine.get('accuracy', 0):.4f}</td>
            </tr>
            """
        
        html += """</tbody></table>"""
        return html