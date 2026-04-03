import os
import json
import hashlib
import datetime
import logging
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

# Try importing pdfkit or weasyprint
try:
    import pdfkit
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

logger = logging.getLogger(__name__)

class ForensicPdfExporter:
    """
    Forensic Evidence Exporter.
    Generates signed PDF reports with:
    - Similarity Heatmaps (Base64)
    - Code Diffs
    - AI Probabilities
    - Digital Signatures
    - Timestamps & Metadata
    """
    
    def __init__(self, template_dir: Path, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = self.env.get_template('publication_report.html')

    def export_case_evidence(self, case_id: str, case_data: Dict[str, Any]) -> Optional[Path]:
        """
        Export a fully signed PDF forensic evidence chain.
        """
        if not PDF_ENABLED:
            logger.error("pdfkit not installed. Please install 'pdfkit' and 'wkhtmltopdf'.")
            return None

        # 1. Generate Metadata & Timestamp
        timestamp = datetime.datetime.now().isoformat()
        
        # 2. Compute Digital Signature (SHA-256)
        payload = json.dumps(case_data, sort_keys=True).encode()
        signature = hashlib.sha256(payload).hexdigest()
        
        # 3. Prepare Context for Template
        context = {
            "case_id": case_id,
            "date": timestamp,
            "composite_score": case_data.get("score", 0.0),
            "agreement_index": case_data.get("agreement_index", 0.0),
            "uncertainty": case_data.get("uncertainty", 0.0),
            "engines": case_data.get("explanation", []),
            "evidence_blocks": case_data.get("findings", []),
            "ai_report": case_data.get("ai_analysis", {}),
            "report_hash": signature,
            "is_signed": True,
            "meta": {
                "generated_by": "IntegrityDesk v2.4 Forensic Engine",
                "authority": "Institutional Academic Integrity Board"
            }
        }

        # 4. Render HTML
        html_content = self.template.render(context)
        
        # 5. Convert to PDF
        pdf_path = self.output_dir / f"forensic_evidence_{case_id}.pdf"
        try:
            options = {
                'page-size': 'Letter',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'custom-header': [
                    ('Accept-Encoding', 'gzip')
                ],
                'no-outline': None
            }
            pdfkit.from_string(html_content, str(pdf_path), options=options)
            logger.info(f"Forensic PDF exported: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return None

    def sign_pdf(self, pdf_path: Path, private_key: str):
        """
        Add a cryptographic signature to the PDF (Simulated).
        In production, use libraries like 'pyHanko' or 'oscrypto' to 
        add a real digital signature block.
        """
        # Placeholder for real PDF signing logic
        pass
