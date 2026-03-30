"""
Report Generation Module for CodeProvenance.

Generates professional HTML, PDF, and JSON reports for similarity analysis results.
"""

import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class ReportGenerator:
    """
    Generates similarity analysis reports in multiple formats.
    
    Supports:
    - HTML: Interactive web-based reports with syntax highlighting
    - JSON: Structured data for programmatic access
    - CSV: Matrix format for spreadsheet analysis
    """
    
    def __init__(
        self,
        title: str = "CodeProvenance Similarity Report",
        include_code_snippets: bool = True,
        syntax_highlighting: bool = True
    ):
        """
        Initialize the report generator.
        
        Args:
            title: Report title
            include_code_snippets: Include code snippets in report
            syntax_highlighting: Use syntax highlighting (HTML only)
        """
        self.title = title
        self.include_code_snippets = include_code_snippets
        self.syntax_highlighting = syntax_highlighting
        self.generated_at = datetime.utcnow().isoformat()
    
    def generate_html(
        self,
        job_data: Dict[str, Any],
        comparison_results: List[Dict[str, Any]],
        submissions: Dict[str, Any],
        threshold: float = 0.5
    ) -> str:
        """
        Generate HTML similarity report.
        
        Args:
            job_data: Job metadata
            comparison_results: List of similarity results
            submissions: Dictionary of submission data
            threshold: Similarity threshold for flagging
            
        Returns:
            HTML report string
        """
        suspicious_pairs = [
            r for r in comparison_results
            if r.get('overall_score', 0) >= threshold
        ]
        suspicious_pairs.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
        
        html = self._generate_html_header()
        html += self._generate_html_summary(job_data, suspicious_pairs, threshold)
        html += self._generate_html_submissions_table(submissions)
        html += self._generate_html_similarity_matrix(comparison_results, submissions, threshold)
        html += self._generate_html_suspicious_pairs(suspicious_pairs, submissions)
        html += self._generate_html_footer()
        
        return html
    
    def _generate_html_header(self) -> str:
        """Generate HTML header with styles."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        header .meta {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .card {{
            background: white;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .card h2 {{
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        
        .stat-card.warning .stat-value {{
            color: #f56565;
        }}
        
        .stat-card.success .stat-value {{
            color: #48bb78;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .score {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .score.high {{
            background: #fed7d7;
            color: #c53030;
        }}
        
        .score.medium {{
            background: #fefcbf;
            color: #b7791f;
        }}
        
        .score.low {{
            background: #c6f6d5;
            color: #276749;
        }}
        
        .pair-card {{
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        
        .pair-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .pair-files {{
            font-weight: 600;
            color: #2d3748;
        }}
        
        .pair-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            font-size: 0.9em;
            color: #666;
        }}
        
        .code-comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
        }}
        
        .code-block {{
            background: #1a1a2e;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .code-header {{
            background: #2d2d44;
            color: #eee;
            padding: 10px 15px;
            font-size: 0.85em;
        }}
        
        .code-content {{
            padding: 15px;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        pre {{
            margin: 0;
            white-space: pre-wrap;
            font-family: 'Fira Code', 'Monaco', 'Courier New', monospace;
            font-size: 0.85em;
            line-height: 1.5;
        }}
        
        /* Syntax highlighting */
        .keyword {{ color: #c678dd; }}
        .string {{ color: #98c379; }}
        .number {{ color: #d19a66; }}
        .comment {{ color: #5c6370; font-style: italic; }}
        .function {{ color: #61afef; }}
        .variable {{ color: #e06c75; }}
        .operator {{ color: #56b6c2; }}
        
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
        }}
        
        .badge-critical {{ background: #fed7d7; color: #c53030; }}
        .badge-warning {{ background: #fefcbf; color: #b7791f; }}
        .badge-info {{ background: #bee3f8; color: #2b6cb0; }}
        
        .filter-bar {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .filter-btn:hover, .filter-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        
        .algorithm-breakdown {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        
        .algorithm-score {{
            font-size: 0.8em;
            padding: 3px 8px;
            background: #eee;
            border-radius: 4px;
        }}
        
        footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 0.85em;
        }}
        
        @media print {{
            body {{ background: white; }}
            .card {{ box-shadow: none; border: 1px solid #eee; }}
            .filter-bar {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{self.title}</h1>
            <div class="meta">
                Generated: {self.generated_at} | CodeProvenance v1.0
            </div>
        </header>
"""
    
    def _generate_html_summary(
        self,
        job_data: Dict[str, Any],
        suspicious_pairs: List[Dict[str, Any]],
        threshold: float
    ) -> str:
        """Generate summary section."""
        total_comparisons = job_data.get('total_comparisons', 0)
        flagged = len(suspicious_pairs)
        high_severity = len([p for p in suspicious_pairs if p.get('overall_score', 0) >= 0.8])
        
        return f"""
        <div class="card">
            <h2>📊 Analysis Summary</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{total_comparisons}</div>
                    <div class="stat-label">Total Comparisons</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-value">{flagged}</div>
                    <div class="stat-label">Flagged (≥{threshold:.0%})</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-value">{high_severity}</div>
                    <div class="stat-label">High Severity (≥80%)</div>
                </div>
                <div class="stat-card success">
                    <div class="stat-value">{total_comparisons - flagged}</div>
                    <div class="stat-label">Clean Submissions</div>
                </div>
            </div>
            
            <div class="filter-bar">
                <button class="filter-btn active" onclick="filterPairs('all')">All ({len(suspicious_pairs)})</button>
                <button class="filter-btn" onclick="filterPairs('critical')">Critical ({high_severity})</button>
                <button class="filter-btn" onclick="filterPairs('warning')">Warning ({len(suspicious_pairs) - high_severity})</button>
            </div>
        </div>
"""
    
    def _generate_html_submissions_table(self, submissions: Dict[str, Any]) -> str:
        """Generate submissions table."""
        rows = []
        for file_id, data in submissions.items():
            filename = data.get('filename', 'Unknown')
            lines = data.get('line_count', 0)
            tokens = data.get('token_count', 0)
            lang = data.get('language', 'Unknown')
            
            rows.append(f"""
                <tr>
                    <td><code>{filename}</code></td>
                    <td>{lang}</td>
                    <td>{lines}</td>
                    <td>{tokens}</td>
                    <td><span class="badge badge-info">{file_id[:8]}...</span></td>
                </tr>
            """)
        
        return f"""
        <div class="card">
            <h2>📁 Submissions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Filename</th>
                        <th>Language</th>
                        <th>Lines</th>
                        <th>Tokens</th>
                        <th>ID</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
"""
    
    def _generate_html_similarity_matrix(
        self,
        results: List[Dict[str, Any]],
        submissions: Dict[str, Any],
        threshold: float
    ) -> str:
        """Generate similarity matrix table."""
        rows = []
        for r in sorted(results, key=lambda x: x.get('overall_score', 0), reverse=True)[:50]:
            file_a = r.get('file_a', '')
            file_b = r.get('file_b', '')
            score = r.get('overall_score', 0)
            
            score_class = 'high' if score >= 0.7 else 'medium' if score >= 0.5 else 'low'
            
            name_a = submissions.get(file_a, {}).get('filename', file_a[:20])
            name_b = submissions.get(file_b, {}).get('filename', file_b[:20])
            
            rows.append(f"""
                <tr data-severity="{'critical' if score >= 0.8 else 'warning' if score >= threshold else 'low'}">
                    <td><code>{name_a}</code></td>
                    <td><code>{name_b}</code></td>
                    <td><span class="score {score_class}">{score:.1%}</span></td>
                </tr>
            """)
        
        return f"""
        <div class="card">
            <h2>🔗 Similarity Matrix (Top 50)</h2>
            <table>
                <thead>
                    <tr>
                        <th>File A</th>
                        <th>File B</th>
                        <th>Similarity</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        
        <script>
        function filterPairs(severity) {{
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            document.querySelectorAll('tr[data-severity]').forEach(row => {{
                if (severity === 'all') {{
                    row.style.display = '';
                }} else if (severity === 'critical') {{
                    row.style.display = row.dataset.severity === 'critical' ? '' : 'none';
                }} else if (severity === 'warning') {{
                    row.style.display = row.dataset.severity === 'warning' ? '' : 'none';
                }}
            }});
        }}
        </script>
"""
    
    def _generate_html_suspicious_pairs(
        self,
        suspicious_pairs: List[Dict[str, Any]],
        submissions: Dict[str, Any]
    ) -> str:
        """Generate detailed suspicious pairs section."""
        if not suspicious_pairs:
            return """
        <div class="card">
            <h2>⚠️ Suspicious Pairs</h2>
            <p style="text-align: center; color: #48bb78; padding: 40px;">
                ✅ No suspicious pairs detected above threshold!
            </p>
        </div>
"""
        
        pair_cards = []
        for i, pair in enumerate(suspicious_pairs[:20], 1):
            file_a = pair.get('file_a', '')
            file_b = pair.get('file_b', '')
            score = pair.get('overall_score', 0)
            individual = pair.get('individual_scores', {})
            
            name_a = submissions.get(file_a, {}).get('filename', 'Unknown')
            name_b = submissions.get(file_b, {}).get('filename', 'Unknown')
            
            severity = 'Critical' if score >= 0.8 else 'Warning'
            badge_class = 'badge-critical' if score >= 0.8 else 'badge-warning'
            
            algo_breakdown = ''.join([
                f'<span class="algorithm-score">{k}: {v:.1%}</span>'
                for k, v in individual.items()
            ])
            
            pair_cards.append(f"""
                <div class="pair-card" data-score="{score:.2f}">
                    <div class="pair-header">
                        <span class="pair-files">{i}. {name_a} ↔ {name_b}</span>
                        <div>
                            <span class="score {'high' if score >= 0.7 else 'medium'}">{score:.1%}</span>
                            <span class="badge {badge_class}">{severity}</span>
                        </div>
                    </div>
                    <div class="pair-details">
                        <div>📊 Overall: {score:.2%}</div>
                        <div>🔄 Comparisons: {pair.get('comparison_count', 1)}</div>
                    </div>
                    <div class="algorithm-breakdown">
                        {algo_breakdown}
                    </div>
                </div>
            """)
        
        return f"""
        <div class="card">
            <h2>⚠️ Suspicious Pairs (Detailed)</h2>
            {''.join(pair_cards)}
        </div>
"""
    
    def _generate_html_footer(self) -> str:
        """Generate HTML footer."""
        return """
        <footer>
            <p>Generated by CodeProvenance - Software Similarity Detection System</p>
            <p>This report is for educational integrity review purposes only.</p>
        </footer>
    </div>
</body>
</html>
"""
    
    def generate_json(
        self,
        job_data: Dict[str, Any],
        comparison_results: List[Dict[str, Any]],
        submissions: Dict[str, Any],
        threshold: float = 0.5
    ) -> str:
        """
        Generate JSON report.
        
        Args:
            job_data: Job metadata
            comparison_results: List of similarity results
            submissions: Dictionary of submission data
            threshold: Similarity threshold
            
        Returns:
            JSON report string
        """
        suspicious_pairs = [
            r for r in comparison_results
            if r.get('overall_score', 0) >= threshold
        ]
        
        report = {
            'metadata': {
                'title': self.title,
                'generated_at': self.generated_at,
                'generator': 'CodeProvenance v1.0',
                'threshold': threshold
            },
            'summary': {
                'total_comparisons': job_data.get('total_comparisons', 0),
                'total_submissions': len(submissions),
                'suspicious_pairs_count': len(suspicious_pairs),
                'high_severity_count': len([p for p in suspicious_pairs if p.get('overall_score', 0) >= 0.8])
            },
            'job': job_data,
            'submissions': submissions,
            'comparisons': comparison_results,
            'suspicious_pairs': sorted(
                suspicious_pairs,
                key=lambda x: x.get('overall_score', 0),
                reverse=True
            )
        }
        
        return json.dumps(report, indent=2)
    
    def generate_csv(
        self,
        comparison_results: List[Dict[str, Any]],
        submissions: Dict[str, Any]
    ) -> str:
        """
        Generate CSV similarity matrix.
        
        Args:
            comparison_results: List of similarity results
            submissions: Dictionary of submission data
            
        Returns:
            CSV report string
        """
        lines = ['file_a,file_b,overall_score,token_score,ngram_score,ast_score,winnowing_score']
        
        for r in comparison_results:
            file_a = r.get('file_a', '')
            file_b = r.get('file_b', '')
            score = r.get('overall_score', 0)
            individual = r.get('individual_scores', {})
            
            name_a = submissions.get(file_a, {}).get('filename', file_a)
            name_b = submissions.get(file_b, {}).get('filename', file_b)
            
            token = individual.get('token', 0)
            ngram = individual.get('ngram', 0)
            ast = individual.get('ast', 0)
            winnowing = individual.get('winnowing', 0)
            
            lines.append(f'"{name_a}","{name_b}",{score:.4f},{token:.4f},{ngram:.4f},{ast:.4f},{winnowing:.4f}')
        
        return '\n'.join(lines)
    
    def save_report(
        self,
        report_content: str,
        output_path: str,
        format: str = 'html'
    ) -> str:
        """
        Save report to file.
        
        Args:
            report_content: Report content
            output_path: Output file path
            format: Report format ('html', 'json', 'csv')
            
        Returns:
            Absolute path to saved file
        """
        path = Path(output_path)
        
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return str(path.absolute())


class PDFReportGenerator:
    """
    PDF report generator using WeasyPrint (HTML to PDF).
    
    Requires: pip install weasyprint
    """
    
    def __init__(self):
        self.html_generator = ReportGenerator()
    
    def generate_pdf(
        self,
        job_data: Dict[str, Any],
        comparison_results: List[Dict[str, Any]],
        submissions: Dict[str, Any],
        output_path: str,
        threshold: float = 0.5
    ) -> str:
        """
        Generate PDF report.
        
        Args:
            job_data: Job metadata
            comparison_results: List of similarity results
            submissions: Dictionary of submission data
            output_path: Output PDF file path
            threshold: Similarity threshold
            
        Returns:
            Path to generated PDF
        """
        try:
            from weasyprint import HTML
        except ImportError:
            raise ImportError(
                "WeasyPrint not installed. Install with: pip install weasyprint"
            )
        
        # Generate HTML report
        html_content = self.html_generator.generate_html(
            job_data, comparison_results, submissions, threshold
        )
        
        # Convert to PDF
        HTML(string=html_content).write_pdf(output_path)
        
        return output_path


def generate_full_report(
    job_data: Dict[str, Any],
    comparison_results: List[Dict[str, Any]],
    submissions: Dict[str, Any],
    output_dir: str = "./reports",
    threshold: float = 0.5,
    formats: List[str] = None
) -> Dict[str, str]:
    """
    Generate reports in multiple formats.
    
    Args:
        job_data: Job metadata
        comparison_results: List of similarity results
        submissions: Dictionary of submission data
        output_dir: Output directory for reports
        threshold: Similarity threshold
        formats: List of formats to generate (default: ['html', 'json', 'csv'])
        
    Returns:
        Dictionary mapping format to output path
    """
    if formats is None:
        formats = ['html', 'json', 'csv']
    
    generator = ReportGenerator()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate job hash for unique filenames
    job_hash = hashlib.md5(
        json.dumps(job_data, sort_keys=True).encode()
    ).hexdigest()[:8]
    
    results = {}
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    if 'html' in formats:
        html_content = generator.generate_html(
            job_data, comparison_results, submissions, threshold
        )
        html_path = output_path / f"similarity_report_{job_hash}_{timestamp}.html"
        generator.save_report(html_content, str(html_path), 'html')
        results['html'] = str(html_path)
    
    if 'json' in formats:
        json_content = generator.generate_json(
            job_data, comparison_results, submissions, threshold
        )
        json_path = output_path / f"similarity_report_{job_hash}_{timestamp}.json"
        generator.save_report(json_content, str(json_path), 'json')
        results['json'] = str(json_path)
    
    if 'csv' in formats:
        csv_content = generator.generate_csv(comparison_results, submissions)
        csv_path = output_path / f"similarity_matrix_{job_hash}_{timestamp}.csv"
        generator.save_report(csv_content, str(csv_path), 'csv')
        results['csv'] = str(csv_path)
    
    return results
