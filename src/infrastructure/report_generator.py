"""Report Generator - Professional plagiarism reports with diff highlighting.

Generates:
1. HTML report with side-by-side code comparison
2. JSON report for API integration
3. PDF report (requires weasyprint: pip install weasyprint)
4. Diff highlighting for matched regions
5. Clustering visualization (similarity matrix scatterplot as HTML/SVG)
"""
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import difflib
import itertools
import math

@dataclass
class ComparisonDetail:
    file_a: str
    file_b: str
    score: float
    risk: str
    features: Dict[str, float] = field(default_factory=dict)
    code_a: str = ""
    code_b: str = ""
    matched_regions: List[Dict[str, Any]] = field(default_factory=list)
    diffs: List[Dict[str, Any]] = field(default_factory=list)

def _diff_html(a: str, b: str, n: int = 5) -> List[Dict]:
    """Generate diff chunks between two texts."""
    a_lines, b_lines = a.splitlines(), b.splitlines()
    diff = list(difflib.unified_diff(a_lines, b_lines, lineterm='', n=n))
    return diff[:200]

def _cluster_data(pairs: List[Dict]) -> Dict[str, Any]:
    """Build cluster data from comparison pairs for visualization."""
    clusters = {}
    for p in pairs:
        fa, fb, score = p['file_a'], p['file_b'], p['score']
        clusters.setdefault(fa, {})
        clusters.setdefault(fb, {})
        if score > 0.5:
            clusters[fa][fb] = score
            clusters[fb][fa] = score
    return clusters

class ReportGenerator:
    def __init__(self, title="CodeProvenance - Plagiarism Report",
                 institution="", course="", assignment="", threshold=0.5,
                 output_dir=Path("./reports")):
        self.title, self.institution, self.course, self.assignment = title, institution, course, assignment
        self.threshold = threshold
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(self, comparisons: List[ComparisonDetail], path: Path=None) -> Path:
        p = path or self.output_dir / "report.html"
        css = """
        body{font-family:Arial,sans-serif;margin:20px}
        .summary{background:#f5f5f5;padding:15px;margin:15px 0;border-radius:5px}
        .risk-CRITICAL{color:#fff;background:#dc3545;padding:3px 8px;border-radius:3px;font-weight:bold}
        .risk-HIGH{color:#fff;background:#fd7e14;padding:3px 8px;border-radius:3px;font-weight:bold}
        .risk-MEDIUM{color:#000;background:#ffc107;padding:3px 8px;border-radius:3px}
        .risk-LOW{color:#fff;background:#28a745;padding:3px 8px;border-radius:3px}
        .pair{border:1px solid #ddd;padding:15px;margin:10px 0;border-radius:5px}
        table{width:100%;border-collapse:collapse;margin:10px 0}
        th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left}
        th{background:#f5f5f5}
        pre{background:#f8f9fa;padding:10px;overflow-x:auto;max-height:300px}
        .diff-line{font-family:monospace;font-size:12px;white-space:pre}
        .diff-add{background:#e6ffec;color:#1a7f37}
        .diff-del{background:#ffebe9;color:#cf222e}
        .chart{width:100%;max-width:800px;margin:20px auto}
        """
        total = len(comparisons)
        suspicious = [c for c in comparisons if c.score >= self.threshold]
        
        clusters = _cluster_data([{'file_a':c.file_a,'file_b':c.file_b,'score':c.score} for c in comparisons])
        
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{self.title}</title><style>{css}</style></head><body>"
        html += f"<h1>{self.title}</h1>"
        html += f"<div class='summary'><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')} | <b>Threshold:</b> {self.threshold} | <b>Total pairs:</b> {total} | <b>Suspicious:</b> {len(suspicious)}</div>"
        
        # Cluster visualization
        html += "<h2>Similarity Clusters</h2>"
        html += "<div class='chart'><svg viewBox='0 0 800 400'>"
        
        nodes = list(clusters.keys())[:20]
        n = len(nodes)
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / n
            x, y = 400 + 150 * math.cos(angle), 200 + 150 * math.sin(angle)
            color = "#dc3545" if any(v > 0.8 for v in clusters.get(node, {}).values()) else "#fd7e14" if any(v > 0.6 for v in clusters.get(node, {}).values()) else "#28a745"
            html += f"<circle cx='{x}' cy='{y}' r='15' fill='{color}' stroke='#fff' stroke-width='2'/>"
            html += f"<text x='{x}' y='{y+4}' text-anchor='middle' fill='#fff' font-size='10'>{node[:10]}</text>"
        
        pairs_added = set()
        for i, f1 in enumerate(nodes):
            for f2, score in clusters.get(f1, {}).items():
                if f2 in nodes and (f1, f2) not in pairs_added:
                    idx1, idx2 = nodes.index(f1), nodes.index(f2)
                    if idx1 <= idx2:
                        angle1, angle2 = 2*math.pi*idx1/n, 2*math.pi*idx2/n
                        x1, y1 = 400+150*math.cos(angle1), 200+150*math.sin(angle1)
                        x2, y2 = 400+150*math.cos(angle2), 200+150*math.sin(angle2)
                        html += f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#666' stroke-width='{score*3}' opacity='0.6'/>"
                        pairs_added.add((f2, f1))
        html += "</svg></div>"
        
        # Comparisons
        html += "<h2>Comparisons</h2>"
        for c in comparisons:
            risk_class = f"risk-{c.risk}"
            html += f"<div class='pair'><div style='display:flex;justify-content:space-between;align-items:center'><h3>{c.file_a} ↔ {c.file_b}</h3><span class='{risk_class}'>{c.risk} ({c.score:.3f})</span></div>"
            
            # Features
            html += "<div style='margin:5px 0'>" + "".join(f"<span style='background:#e9ecef;padding:2px 8px;margin:2px;border-radius:3px;font-size:12px'>{k}: {v:.3f}</span>" for k,v in sorted(c.features.items(), key=lambda x:-x[1])) + "</div>"
            
            # Code comparison
            if c.code_a and c.code_b:
                html += "<details><summary style='cursor:pointer'>View Diff</summary>"
                html += "<table style='width:100%'><tr><th>' + c.file_a + '</th><th>' + c.file_b + '</th></tr>"
                html += "<tr><td style='vertical-align:top'><pre>" + self._safe_html(c.code_a[:500]) + "</pre></td>"
                html += "<td style='vertical-align:top'><pre>" + self._safe_html(c.code_b[:500]) + "</pre></td></tr></table></details>"
            
            # Diff
            if c.diffs:
                html += "<details><summary style='cursor:pointer'>View Unified Diff</summary><div class='diff-line'"
                for line in c.diffs:
                    cls = 'diff-add' if line.startswith('+') else 'diff-del' if line.startswith('-') else ''
                    html += f"<div class='{cls}'>{self._safe_html(line)}</div>"
                html += "</div></details>"
            html += "</div>"
        
        html += f"<div style='text-align:center;margin-top:20px;color:#666;font-size:12px'>Generated by CodeProvenance</div></body></html>"
        p.write_text(html, encoding='utf-8')
        return p

    def generate_json(self, comps: List[ComparisonDetail], path: Path=None) -> Path:
        p = path or self.output_dir / "report.json"
        data = {'title': self.title, 'threshold': self.threshold, 'generated': datetime.now().isoformat(),
                'comparisons': [{'file_a': c.file_a, 'file_b': c.file_b, 'score': round(c.score,3), 'risk': c.risk, 'features': {k: round(v,3) for k,v in c.features.items()}} for c in comps]}
        p.write_text(json.dumps(data, indent=2))
        return p

    def _safe_html(self, text):
        return text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
