import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader

class PublicationReportGenerator:
    """
    Generates academic-grade HTML reports using Jinja2 templates.
    Conforms to the "publication-style" requirement with ACM/IEEE aesthetics.
    """
    
    def __init__(self, template_dir: Path):
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = self.env.get_template('publication_report.html')

    def generate(self, case_data: Dict[str, Any], output_path: Path):
        """
        Populate the HTML template with case evidence.
        
        Args:
            case_data: Dictionary containing results from arbitration and ML fusion.
            output_path: Destination for the generated HTML report.
        """
        # 1. Prepare context for template
        context = {
            "case_id": case_data.get("id", "N/A"),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "composite_score": round(case_data.get("score", 0.0), 3),
            "composite_interpretation": self._get_interpretation(case_data.get("score", 0.0)),
            "agreement_index": round(case_data.get("agreement_index", 0.0), 3),
            "consensus_label": self._get_consensus_label(case_data.get("agreement_index", 0.0)),
            "uncertainty": round(case_data.get("uncertainty", 0.0), 3),
            "uncertainty_label": "High confidence" if case_data.get("uncertainty", 1.0) < 0.1 else "Moderate confidence",
            "engines": self._process_engines(case_data.get("explanation", [])),
            "evidence_blocks": self._process_evidence(case_data.get("findings", [])),
            "report_hash": hashlib.sha256(json.dumps(case_data, sort_keys=True).encode()).hexdigest()[:12]
        }

        # 2. Render and save
        html_content = self.template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _get_interpretation(self, score: float) -> str:
        if score > 0.85: return "Critical overlap detected requiring immediate committee review. High probability of plagiarism."
        if score > 0.6: return "High similarity scores from multiple independent forensic engines. Manual review highly recommended."
        return "Moderate similarity detected; may represent shared boilerplate or collaborative work."

    def _get_consensus_label(self, index: float) -> str:
        if index > 0.8: return "Strong Consensus"
        if index > 0.5: return "Moderate Consensus"
        return "Weak Consensus"

    def _process_engines(self, explanation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed = []
        for exp in explanation:
            processed.append({
                "name": exp.get("engine", "Unknown").upper(),
                "score": round(exp.get("score", 0.0), 3),
                "contribution": round(exp.get("contribution", 0.0), 3),
                "risk": "critical" if exp.get("score", 0) > 0.9 else ("high" if exp.get("score", 0) > 0.75 else "medium")
            })
        return processed

    def _process_evidence(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        blocks = []
        for f in findings:
            for b in f.get("evidence_blocks", []):
                blocks.append({
                    "engine": f.get("engine", "Engine"),
                    "notes": ", ".join(b.get("transformation_notes", [])),
                    "a_lines": f"{b.get('a_start_line', 0)}-{b.get('a_end_line', 0)}",
                    "b_lines": f"{b.get('b_start_line', 0)}-{b.get('b_end_line', 0)}",
                    "a_snippet": b.get("a_snippet", "Snippet A"),
                    "b_snippet": b.get("b_snippet", "Snippet B")
                })
        return blocks
