"""Report Generator - Professional plagiarism reports with side-by-side diff highlighting.

Features:
1. Side-by-side diff view with add/remove/changed line highlighting
2. Similarity cluster visualization (SVG graph)
3. Feature breakdown per comparison
4. HTML + JSON export
"""
import json
import difflib
import math
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ComparisonDetail:
    file_a: str
    file_b: str
    score: float
    risk: str
    features: Dict[str, float] = field(default_factory=dict)
    code_a: str = ""
    code_b: str = ""

def _generate_side_by_side_diff(code_a: str, code_b: str, file_a: str = "", file_b: str = "", context: int = 5) -> str:
    """Generate side-by-side HTML diff with color coding."""
    a_lines = code_a.splitlines(keepends=True)
    b_lines = code_b.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile=file_a or "File A",
        tofile=file_b or "File B",
        lineterm="",
        n=context
    ))
    
    if not diff:
        return "<p style='color:#28a745'>Files are identical</p>"
    
    html = "<div class='diff-container'><table class='diff-table'><thead><tr>"
    html += f"<th class='diff-header from'>{diff[0]}</th>"
    html += f"<th class='diff-header to'>{diff[1]}</th>"
    html += "</tr></thead><tbody>"
    
    for line in diff[2:]:
        if line.startswith('---') or line.startswith('+++'):
            continue
        cls = 'diff-add' if line.startswith('+') else 'diff-del' if line.startswith('-') else 'diff-ctx'
        escaped = line.replace('&', '&').replace('<', '<').replace('>', '>')
        
        if line.startswith('@@'):
            html += f"<tr class='diff-hunk'><td colspan='2'>{escaped}</td><td colspan='2'></td></tr>"
        elif line.startswith('-'):
            html += f"<tr class='diff-del'><td class='diff-ln'>-</td><td class='diff-code'>{escaped[1:]}</td><td></td><td></td></tr>"
        elif line.startswith('+'):
            html += f"<tr class='diff-add'><td></td><td></td><td class='diff-ln'>+</td><td class='diff-code'>{escaped[1:]}</td></tr>"
        else:
            html += f"<tr class='diff-ctx'><td></td><td class='diff-code'>{escaped[1:]}</td><td></td><td class='diff-code'>{escaped[1:]}</td></tr>"
    
    html += "</tbody></table></div>"
    return html

_RISK_COLORS = {
    "CRITICAL": "#dc3545", "HIGH": "#fd7e14",
    "MEDIUM": "#ffc107", "LOW": "#28a745"
}

_CSS = """
body{font-family:system-ui,-apple-system,sans-serif;margin:20px;color:#1a1a1a}
.summary{background:#f5f5f5;padding:15px;margin:15px 0;border-radius:8px}
.risk{padding:3px 10px;border-radius:4px;font-weight:bold;color:#fff}
.pair{border:1px solid #e0e0e0;padding:20px;margin:15px 0;border-radius:8px}
.table{width:100%;border-collapse:collapse;margin:10px 0}
th,td{padding:10px;text-align:left;border-bottom:1px solid #eee}
th{background:#f5f5f5}
.feature{background:#e9ecef;padding:3px 10px;margin:2px;border-radius:4px;font-size:12px;display:inline-block}
.chart{width:100%;max-width:800px;margin:20px auto}
details{margin-top:10px}
summary{cursor:pointer;color:#0969da;font-weight:500}

/* Diff styles */
.diff-container{overflow-x:auto;margin-top:10px}
.diff-table{width:100%;border-collapse:collapse;font-family:monospace;font-size:13px}
.diff-header{background:#e8e8e8;padding:4px 8px;text-align:left;font-weight:bold}
.diff-hunk{background:#f0f0f0}
.diff-ctx td{background:#f8f8f8}
.diff-add td{background:#e6ffec}
.diff-del td{background:#ffebe9}
.diff-ln{width:30px;text-align:center;color:#666}
.diff-code{white-space:pre-wrap;padding:2px 8px}
"""

class ReportGenerator:
    """Generates professional plagiarism reports with diff highlighting."""
    
    def __init__(self, title="CodeProvenance Report", institution="", course="",
                 assignment="", threshold=0.5, output_dir=Path("./reports")):
        self.title = title
        self.institution = institution
        self.course = course
        self.assignment = assignment
        self.threshold = threshold
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _risk_color(score):
        if score >= 0.9: return _RISK_COLORS["CRITICAL"]
        if score >= 0.75: return _RISK_COLORS["HIGH"]
        if score >= 0.5: return _RISK_COLORS["MEDIUM"]
        return _RISK_COLORS["LOW"]
    
    @staticmethod
    def _risk_label(score):
        if score >= 0.9: return "CRITICAL"
        if score >= 0.75: return "HIGH"
        if score >= 0.5: return "MEDIUM"
        return "LOW"
    
    def _cluster_svg(self, pairs):
        """Generate SVG similarity cluster visualization."""
        clusters = {}
        for p in pairs:
            fa = getattr(p, 'file_a', '') or p.get('file_a', '') if hasattr(p, 'get') else getattr(p, 'file_a', '')
            fb = getattr(p, 'file_b', '') or p.get('file_b', '') if hasattr(p, 'get') else getattr(p, 'file_b', '')
            score = getattr(p, 'score', 0) or p.get('score', 0) if hasattr(p, 'get') else getattr(p, 'score', 0)
            if score > 0.5:
                clusters.setdefault(fa, {})[fb] = score
                clusters.setdefault(fb, {})[fa] = score
        
        nodes = list(clusters.keys())[:20]
        n = len(nodes)
        svg = "<svg viewBox='0 0 800 400'>"
        
        # Draw edges
        added = set()
        for i, f1 in enumerate(nodes):
            for f2, score in clusters.get(f1, {}).items():
                if f2 in nodes and f"{f2}->{f1}" not in added:
                    a1, a2 = 2*math.pi*i/n, 2*math.pi*nodes.index(f2)/n
                    x1, y1 = 400+150*math.cos(a1), 200+150*math.sin(a1)
                    x2, y2 = 400+150*math.cos(a2), 200+150*math.sin(a2)
                    svg += f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#666' stroke-width='{score*3}' opacity='0.6'/>"
                    added.add(f"{f1}->{f2}")
        
        # Draw nodes
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / n
            x, y = 400 + 150 * math.cos(angle), 200 + 150 * math.sin(angle)
            max_score = max(clusters.get(node, {}).values(), default=0)
            color = "#dc3545" if max_score > 0.8 else "#fd7e14" if max_score > 0.6 else "#28a745"
            svg += f"<circle cx='{x}' cy='{y}' r='15' fill='{color}' stroke='#fff' stroke-width='2'/>"
            svg += f"<text x='{x}' y='{y+4}' text-anchor='middle' fill='#fff' font-size='10'>{node[:10]}</text>"
        
        return svg + "</svg>"

    def generate_html(self, comparisons: list, path: Path = None) -> Path:
        """Generate complete HTML report with side-by-side diffs."""
        p = path or self.output_dir / "report.html"
        total = len(comparisons)
        suspicious = [c for c in comparisons if c.score >= self.threshold]
        
        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>{self.title}</title>
<style>{_CSS}</style></head><body>
<h1>{self.title}</h1>
<div class='info'>Institution: {self.institution} | Course: {self.course} | Assignment: {self.assignment}</div>
<div class='summary'><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')} | <strong>Threshold:</strong> {self.threshold} | <strong>Total pairs:</strong> {total} | <strong>Suspicious:</strong> {len(suspicious)}</div>"""

        # Cluster visualization
        html += "<h2>Similarity Clusters</h2>"
        html += f"<div class='chart'>{self._cluster_svg(comparisons)}</div>"
        
        # Comparisons with side-by-side diffs
        html += "<h2>Comparisons</h2>"
        for c in comparisons:
            color = self._risk_color(c.score)
            label = self._risk_label(c.score)
            html += f"""<div class='pair'>
<div style='display:flex;justify-content:space-between;align-items:center'>
<h3>{c.file_a} ↔ {c.file_b}</h3>
<span class='risk' style='background:{color}'>{label} ({c.score:.3f})</span>
</div>
<div style='margin:10px 0'>{" ".join(f"<span class='feature'>{k}: {v:.3f}</span>" for k, v in sorted(c.features.items(), key=lambda x: -x[1]))}</div>"""
            
            # Side-by-side diff
            if c.code_a and c.code_b:
                html += f"<details><summary>View Side-by-Side Diff</summary>"
                html += _generate_side_by_side_diff(c.code_a, c.code_b, c.file_a, c.file_b)
                html += "</details>"
            
            html += "</div>"
        
        html += "<div style='text-align:center;margin-top:30px;color:#666;font-size:12px'>Generated by CodeProvenance</div></body></html>"
        p.write_text(html, encoding='utf-8')
        return p
    
    def generate_json(self, comparisons: list, path: Path = None) -> Path:
        """Generate JSON report."""
        p = path or self.output_dir / "report.json"
        data = {
            'title': self.title, 'threshold': self.threshold,
            'generated': datetime.now().isoformat(),
            'comparisons': [
                {'file_a': c.file_a, 'file_b': c.file_b, 'score': round(c.score, 3),
                 'risk': self._risk_label(c.score),
                 'features': {k: round(v, 3) for k, v in c.features.items()}}
                for c in comparisons
            ]
        }
        p.write_text(json.dumps(data, indent=2))
        return p