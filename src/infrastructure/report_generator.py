"""Professional Report Generator for Code Similarity Analysis.

Generates HTML, PDF, and JSON reports with:
- Side-by-side code highlighting
- Similarity heatmaps
- Risk level indicators
- AI detection results
- Professional formatting

Usage:
    from src.infrastructure.report_generator import ReportGenerator
    generator = ReportGenerator()
    html_report = generator.generate_html_report(analysis_results)
    generator.save_report(html_report, "report.html")
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate professional plagiarism detection reports."""
    
    def __init__(self, institution_name: str = "CodeProvenance", branding_color: str = "#2563eb") -> None:
        """Initialize report generator.
        
        Args:
            institution_name: Name of the institution/course
            branding_color: Primary color for branding (hex)
        """
        self.institution_name = institution_name
        self.branding_color = branding_color
    
    def generate_html_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive HTML report.
        
        Args:
            results: Analysis results from the detection service
            
        Returns:
            HTML string of the report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = results.get("summary", {})
        pairs = results.get("pairs", [])
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Similarity Report - {self.institution_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .code-block {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.875rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .highlight-added {{
            background-color: #dcfce7;
            border-left: 3px solid #22c55e;
        }}
        .highlight-removed {{
            background-color: #fee2e2;
            border-left: 3px solid #ef4444;
        }}
        .highlight-similar {{
            background-color: #fef3c7;
            border-left: 3px solid #f59e0b;
        }}
        .risk-critical {{
            background-color: #dc2626;
        }}
        .risk-high {{
            background-color: #ea580c;
        }}
        .risk-medium {{
            background-color: #ca8a04;
        }}
        .risk-low {{
            background-color: #16a34a;
        }}
        @media print {{
            .no-print {{ display: none; }}
            .page-break {{ page-break-before: always; }}
        }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold text-gray-900">Code Similarity Report</h1>
                    <p class="mt-1 text-sm text-gray-500">{self.institution_name}</p>
                </div>
                <div class="text-right">
                    <p class="text-sm text-gray-500">Generated: {timestamp}</p>
                    <p class="text-sm text-gray-500">Report ID: {results.get('report_id', 'N/A')}</p>
                </div>
            </div>
        </div>
    </header>

    <!-- Summary Dashboard -->
    <main class="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <!-- Key Metrics -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow p-6">
                <dt class="text-sm font-medium text-gray-500 truncate">Total Files</dt>
                <dd class="mt-1 text-3xl font-semibold text-gray-900">{summary.get('total_files', 0)}</dd>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <dt class="text-sm font-medium text-gray-500 truncate">Total Pairs</dt>
                <dd class="mt-1 text-3xl font-semibold text-gray-900">{summary.get('total_pairs', 0)}</dd>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <dt class="text-sm font-medium text-gray-500 truncate">Suspicious Pairs</dt>
                <dd class="mt-1 text-3xl font-semibold text-red-600">{summary.get('suspicious_pairs', 0)}</dd>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <dt class="text-sm font-medium text-gray-500 truncate">Avg Similarity</dt>
                <dd class="mt-1 text-3xl font-semibold text-gray-900">{summary.get('average_similarity', 0):.1%}</dd>
            </div>
        </div>

        <!-- Risk Distribution -->
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-lg font-medium text-gray-900">Risk Distribution</h3>
            </div>
            <div class="p-6">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {self._generate_risk_cards(summary.get('risk_distribution', {}))}
                </div>
            </div>
        </div>

        <!-- AI Detection Summary -->
        {self._generate_ai_summary(results.get('ai_detection', {}))}

        <!-- Similarity Heatmap -->
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-lg font-medium text-gray-900">Similarity Heatmap</h3>
            </div>
            <div class="p-6">
                {self._generate_heatmap(pairs)}
            </div>
        </div>

        <!-- Detailed Pairs -->
        <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-lg font-medium text-gray-900">Detailed Analysis ({len(pairs)} pairs)</h3>
            </div>
            <div class="divide-y divide-gray-200">
                {self._generate_pair_details(pairs)}
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t mt-12">
        <div class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
            <p class="text-center text-sm text-gray-500">
                Generated by CodeProvenance | {self.institution_name} | {timestamp}
            </p>
        </div>
    </footer>

    <script>
        // Add interactivity for expanding/collapsing details
        document.querySelectorAll('.toggle-details').forEach(button => {{
            button.addEventListener('click', function() {{
                const details = this.nextElementSibling;
                details.classList.toggle('hidden');
                this.textContent = details.classList.contains('hidden') ? 'Show Details' : 'Hide Details';
            }});
        }});
    </script>
</body>
</html>"""
        
        return html
    
    def generate_json_report(self, results: Dict[str, Any]) -> str:
        """Generate a JSON report for API consumption.
        
        Args:
            results: Analysis results from the detection service
            
        Returns:
            JSON string of the report
        """
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "institution": self.institution_name,
                "version": "1.0",
                "report_id": results.get("report_id", "N/A"),
            },
            "summary": results.get("summary", {}),
            "pairs": results.get("pairs", []),
            "ai_detection": results.get("ai_detection", {}),
            "web_analysis": results.get("web_analysis", {}),
            "recommendations": self._generate_recommendations(results),
        }
        
        return json.dumps(report, indent=2, default=str)
    
    def save_report(self, content: str, filepath: str) -> None:
        """Save report to file.
        
        Args:
            content: Report content (HTML or JSON)
            filepath: Path to save the file
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        logger.info(f"Report saved to {filepath}")
    
    def _generate_risk_cards(self, distribution: Dict[str, int]) -> str:
        """Generate risk level cards HTML."""
        risk_levels = [
            ("Critical", distribution.get("critical", 0), "bg-red-100 text-red-800 border-red-200"),
            ("High", distribution.get("high", 0), "bg-orange-100 text-orange-800 border-orange-200"),
            ("Medium", distribution.get("medium", 0), "bg-yellow-100 text-yellow-800 border-yellow-200"),
            ("Low", distribution.get("low", 0), "bg-green-100 text-green-800 border-green-200"),
        ]
        
        cards = []
        for name, count, color_class in risk_levels:
            cards.append(f"""
            <div class="border rounded-lg p-4 {color_class}">
                <dt class="text-sm font-medium"> {name} Risk</dt>
                <dd class="mt-1 text-2xl font-bold">{count}</dd>
            </div>
            """)
        
        return "".join(cards)
    
    def _generate_ai_summary(self, ai_data: Dict[str, Any]) -> str:
        """Generate AI detection summary section."""
        if not ai_data:
            return ""
        
        ai_flagged = ai_data.get("flagged_count", 0)
        total_files = ai_data.get("total_files", 0)
        
        return f"""
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-lg font-medium text-gray-900">AI Detection Summary</h3>
            </div>
            <div class="p-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="bg-purple-50 rounded-lg p-4 border border-purple-200">
                        <dt class="text-sm font-medium text-purple-700">AI-Flagged Files</dt>
                        <dd class="mt-1 text-2xl font-bold text-purple-900">{ai_flagged}</dd>
                    </div>
                    <div class="bg-purple-50 rounded-lg p-4 border border-purple-200">
                        <dt class="text-sm font-medium text-purple-700">Total Files Analyzed</dt>
                        <dd class="mt-1 text-2xl font-bold text-purple-900">{total_files}</dd>
                    </div>
                    <div class="bg-purple-50 rounded-lg p-4 border border-purple-200">
                        <dt class="text-sm font-medium text-purple-700">AI Detection Rate</dt>
                        <dd class="mt-1 text-2xl font-bold text-purple-900">{(ai_flagged/total_files*100) if total_files > 0 else 0:.1f}%</dd>
                    </div>
                </div>
            </div>
        </div>
        """
    
    def _generate_heatmap(self, pairs: List[Dict[str, Any]]) -> str:
        """Generate similarity heatmap visualization."""
        if not pairs:
            return "<p class='text-gray-500'>No pairs to display.</p>"
        
        # Sort by similarity score
        sorted_pairs = sorted(pairs, key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        rows = []
        for i, pair in enumerate(sorted_pairs[:20]):  # Top 20
            score = pair.get("similarity_score", 0)
            file_a = pair.get("file_a", "Unknown")
            file_b = pair.get("file_b", "Unknown")
            risk = pair.get("risk_level", "LOW")
            
            # Color based on score
            if score >= 0.9:
                color = "bg-red-500"
            elif score >= 0.75:
                color = "bg-orange-500"
            elif score >= 0.5:
                color = "bg-yellow-500"
            else:
                color = "bg-green-500"
            
            rows.append(f"""
            <div class="flex items-center py-3 border-b border-gray-100 last:border-0">
                <div class="w-8 h-8 rounded {color} flex items-center justify-center text-white text-sm font-bold mr-4">
                    {i+1}
                </div>
                <div class="flex-1">
                    <div class="flex justify-between items-center">
                        <span class="text-sm font-medium text-gray-900">{file_a} vs {file_b}</span>
                        <span class="text-sm font-bold text-gray-900">{score:.1%}</span>
                    </div>
                    <div class="mt-1 w-full bg-gray-200 rounded-full h-2">
                        <div class="h-2 rounded-full {color}" style="width: {score*100}%"></div>
                    </div>
                </div>
                <span class="ml-4 px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700">{risk}</span>
            </div>
            """)
        
        return f"""
        <div class="space-y-2">
            {''.join(rows)}
        </div>
        """
    
    def _generate_pair_details(self, pairs: List[Dict[str, Any]]) -> str:
        """Generate detailed pair comparison sections."""
        if not pairs:
            return "<p class='p-6 text-gray-500'>No pairs to display.</p>"
        
        details = []
        for pair in pairs:
            file_a = pair.get("file_a", "Unknown")
            file_b = pair.get("file_b", "Unknown")
            score = pair.get("similarity_score", 0)
            risk = pair.get("risk_level", "LOW")
            engines = pair.get("engine_scores", {})
            ai_info = pair.get("ai_detection", {})
            
            # Risk badge color
            risk_colors = {
                "CRITICAL": "bg-red-100 text-red-800",
                "HIGH": "bg-orange-100 text-orange-800",
                "MEDIUM": "bg-yellow-100 text-yellow-800",
                "LOW": "bg-green-100 text-green-800",
            }
            risk_class = risk_colors.get(risk, "bg-gray-100 text-gray-800")
            
            # Engine scores
            engine_html = ""
            for engine_name, engine_score in engines.items():
                engine_html += f"""
                <div class="flex justify-between py-1">
                    <span class="text-sm text-gray-600">{engine_name.replace('_', ' ').title()}</span>
                    <span class="text-sm font-medium">{engine_score:.1%}</span>
                </div>
                """
            
            # AI detection info
            ai_html = ""
            if ai_info:
                ai_prob = ai_info.get("ai_probability", 0)
                ai_confidence = ai_info.get("confidence", 0)
                indicators = ai_info.get("indicators", [])
                
                ai_html = f"""
                <div class="mt-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
                    <h4 class="text-sm font-medium text-purple-900 mb-2">AI Detection</h4>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <span class="text-xs text-purple-700">AI Probability</span>
                            <p class="text-sm font-bold text-purple-900">{ai_prob:.1%}</p>
                        </div>
                        <div>
                            <span class="text-xs text-purple-700">Confidence</span>
                            <p class="text-sm font-bold text-purple-900">{ai_confidence:.1%}</p>
                        </div>
                    </div>
                    {f'<p class="mt-2 text-xs text-purple-700">Indicators: {", ".join(indicators[:3])}</p>' if indicators else ''}
                </div>
                """
            
            details.append(f"""
            <div class="p-6 hover:bg-gray-50 transition-colors">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-3">
                            <h4 class="text-lg font-medium text-gray-900">{file_a}</h4>
                            <span class="text-gray-400">↔</span>
                            <h4 class="text-lg font-medium text-gray-900">{file_b}</h4>
                        </div>
                        <div class="mt-2 flex items-center gap-4">
                            <span class="text-2xl font-bold text-gray-900">{score:.1%}</span>
                            <span class="px-3 py-1 rounded-full text-sm font-medium {risk_class}">{risk}</span>
                        </div>
                    </div>
                    <button class="no-print toggle-details px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800">
                        Show Details
                    </button>
                </div>
                <div class="hidden mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h5 class="text-sm font-medium text-gray-700 mb-2">Engine Scores</h5>
                        {engine_html}
                    </div>
                    <div>
                        {ai_html}
                    </div>
                </div>
            </div>
            """)
        
        return "".join(details)
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []
        summary = results.get("summary", {})
        
        suspicious_count = summary.get("suspicious_pairs", 0)
        total_pairs = summary.get("total_pairs", 0)
        
        if suspicious_count > 0:
            recommendations.append(f"Review {suspicious_count} suspicious pairs manually")
        
        if total_pairs > 0 and suspicious_count / total_pairs > 0.3:
            recommendations.append("High plagiarism rate detected - consider reviewing assignment design")
        
        ai_data = results.get("ai_detection", {})
        if ai_data.get("flagged_count", 0) > 0:
            recommendations.append(f"Investigate {ai_data['flagged_count']} files for potential AI-generated code")
        
        if not recommendations:
            recommendations.append("No significant issues detected")
        
        return recommendations
