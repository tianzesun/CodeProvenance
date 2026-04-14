"""Tests for evidence chain PDF export pipeline."""

import json
import tempfile
from pathlib import Path

import pytest

from src.backend.backend.infrastructure.reporting.visualizations import (
    generate_similarity_heatmap,
    generate_code_diff_image,
    generate_ai_probability_chart,
    generate_engine_radar_chart,
    generate_confusion_matrix_image,
    generate_qr_code,
)
from src.backend.backend.infrastructure.reporting.evidence_pdf_exporter import (
    EvidenceChainPdfExporter,
)


SAMPLE_CASE_DATA = {
    "case_id": "TEST-2026-001",
    "student_name": "John Doe",
    "student_id": "S12345678",
    "course": "CS101 - Intro to Programming",
    "assignment": "Assignment 3: Sorting Algorithms",
    "investigator": "Prof. Jane Smith",
    "similarity_score": 0.87,
    "ai_probability": 0.32,
    "consensus_index": 0.82,
    "ci_margin": 0.03,
    "n_bootstrap": 1000,
    "dataset_hash": "abc123def456",
    "key_conclusions": [
        "High structural similarity detected between submissions.",
        "Multiple independent engines confirm the finding.",
        "AI generation probability is low — likely human-authored.",
    ],
    "tool_comparison": [
        {"name": "MOSS", "similarity": 0.82, "precision": 0.78, "recall": 0.75, "f1": 0.76, "ci_lower": 0.70, "ci_upper": 0.82},
        {"name": "JPlag", "similarity": 0.85, "precision": 0.80, "recall": 0.78, "f1": 0.79, "ci_lower": 0.73, "ci_upper": 0.85},
        {"name": "Ours", "similarity": 0.91, "precision": 0.88, "recall": 0.86, "f1": 0.87, "ci_lower": 0.82, "ci_upper": 0.92},
    ],
    "significance_statement": "Ours is significantly better than MOSS (F1: 0.87 vs 0.76, p=0.003).",
    "external_tools": [
        {"name": "MOSS", "status": "success", "summary": "82% similarity detected", "details": "Winnowing-based analysis"},
        {"name": "JPlag", "status": "success", "summary": "85% similarity detected", "details": "AST-based analysis"},
    ],
    "ai_details": [
        {"name": "CodeBERT", "probability": 0.28, "confidence": 0.92},
        {"name": "UniXcoder", "probability": 0.35, "confidence": 0.88},
        {"name": "Stylometry", "probability": 0.33, "confidence": 0.85},
    ],
    "ai_model_results": {
        "CodeBERT": 0.28,
        "UniXcoder": 0.35,
        "Stylometry": 0.33,
    },
    "confusion_stats": {"tp": 42, "fp": 5, "tn": 48, "fn": 5, "accuracy": 0.90},
    "similarity_matrix": [
        [1.0, 0.87, 0.12, 0.08],
        [0.87, 1.0, 0.15, 0.10],
        [0.12, 0.15, 1.0, 0.05],
        [0.08, 0.10, 0.05, 1.0],
    ],
    "similarity_labels": ["Student A", "Student B", "Ref 1", "Ref 2"],
    "code_a": "def sort(arr):\n    for i in range(len(arr)):\n        for j in range(i+1, len(arr)):\n            if arr[i] > arr[j]:\n                arr[i], arr[j] = arr[j], arr[i]\n    return arr",
    "code_b": "def sort(data):\n    n = len(data)\n    for i in range(n):\n        for j in range(i+1, n):\n            if data[i] > data[j]:\n                temp = data[i]\n                data[i] = data[j]\n                data[j] = temp\n    return data",
    "file_a": "student_a/sort.py",
    "file_b": "student_b/sort.py",
    "engine_performance": {
        "MOSS": {"precision": 0.78, "recall": 0.75, "f1": 0.76},
        "JPlag": {"precision": 0.80, "recall": 0.78, "f1": 0.79},
        "Ours": {"precision": 0.88, "recall": 0.86, "f1": 0.87},
    },
    "evidence_pairs": [
        {
            "file_a": "student_a/sort.py",
            "file_b": "student_b/sort.py",
            "similarity": 0.87,
            "engine": "AST Similarity",
            "a_lines": "1-6",
            "b_lines": "1-10",
            "code_a": "def sort(arr):\n    for i in range(len(arr)):\n        for j in range(i+1, len(arr)):\n            if arr[i] > arr[j]:\n                arr[i], arr[j] = arr[j], arr[i]",
            "code_b": "def sort(data):\n    n = len(data)\n    for i in range(n):\n        for j in range(i+1, n):\n            if data[i] > data[j]:",
        },
    ],
}


class TestVisualizationGenerators:
    def test_heatmap_returns_base64_uri(self):
        matrix = [[1.0, 0.8], [0.8, 1.0]]
        labels = ["A", "B"]
        uri = generate_similarity_heatmap(matrix, labels)
        assert uri.startswith("data:image/png;base64,")

    def test_heatmap_default_labels(self):
        matrix = [[1.0, 0.5], [0.5, 1.0]]
        uri = generate_similarity_heatmap(matrix)
        assert uri.startswith("data:image/png;base64,")

    def test_code_diff_returns_base64_uri(self):
        code_a = "def foo():\n    return 1"
        code_b = "def bar():\n    return 2"
        uri = generate_code_diff_image(code_a, code_b)
        assert uri.startswith("data:image/png;base64,")

    def test_code_diff_identical_files(self):
        code = "def foo():\n    return 1"
        uri = generate_code_diff_image(code, code)
        assert uri.startswith("data:image/png;base64,")

    def test_ai_chart_returns_base64_uri(self):
        results = {"CodeBERT": 0.28, "UniXcoder": 0.35, "Stylometry": 0.90}
        uri = generate_ai_probability_chart(results)
        assert uri.startswith("data:image/png;base64,")

    def test_radar_chart_returns_base64_uri(self):
        scores = {
            "MOSS": {"precision": 0.78, "recall": 0.75, "f1": 0.76},
            "JPlag": {"precision": 0.80, "recall": 0.78, "f1": 0.79},
        }
        uri = generate_engine_radar_chart(scores)
        assert uri.startswith("data:image/png;base64,")

    def test_confusion_matrix_returns_base64_uri(self):
        uri = generate_confusion_matrix_image(tp=42, fp=5, tn=48, fn=5)
        assert uri.startswith("data:image/png;base64,")

    def test_qr_code_returns_base64_uri(self):
        uri = generate_qr_code("https://example.com/report/123")
        assert uri.startswith("data:image/png;base64,")

    def test_qr_code_scannable_size(self):
        uri = generate_qr_code("https://example.com/test", size=300)
        assert uri.startswith("data:image/png;base64,")
        assert len(uri) > 500


class TestEvidenceChainPdfExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        template_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "reporting" / "templates"
        return EvidenceChainPdfExporter(
            template_dir=template_dir,
            output_dir=tmp_path / "evidence",
        )

    def test_export_html(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        assert html_path is not None
        assert html_path.exists()
        content = html_path.read_text()
        assert "Academic Integrity Evidence Report" in content
        assert "John Doe" in content
        assert "CS101" in content
        assert "TEST-2026-001" in content
        assert "data:image/png;base64," in content

    def test_export_html_contains_risk_label(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        content = html_path.read_text()
        assert "Critical" in content or "High" in content

    def test_export_html_contains_tool_table(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        content = html_path.read_text()
        assert "MOSS" in content
        assert "JPlag" in content
        assert "Ours" in content

    def test_export_html_contains_hash(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        content = html_path.read_text()
        assert "Integrity Hash:" in content
        assert "sha-256" in content.lower() or "sha256" in content.lower()

    def test_export_html_contains_watermark(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        content = html_path.read_text()
        assert "Confidential" in content
        assert "Academic Integrity Committee" in content

    def test_export_html_contains_signature_area(self, exporter, tmp_path):
        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "test.html")
        content = html_path.read_text()
        assert "Investigator Signature" in content
        assert "Committee Chair" in content

    def test_export_pdf_requires_backend(self, exporter, tmp_path):
        from src.backend.backend.infrastructure.reporting.evidence_pdf_exporter import PDF_BACKEND
        if PDF_BACKEND is None:
            result = exporter.export(SAMPLE_CASE_DATA, tmp_path / "test.pdf")
            assert result is None
        else:
            result = exporter.export(SAMPLE_CASE_DATA, tmp_path / "test.pdf")
            assert result is not None
            assert result.exists()
            assert result.stat().st_size > 0

    def test_minimal_case_data(self, exporter, tmp_path):
        minimal = {"case_id": "MIN-001"}
        html_path = exporter.export_html(minimal, tmp_path / "minimal.html")
        assert html_path is not None
        assert html_path.exists()
        content = html_path.read_text()
        assert "MIN-001" in content


class TestEvidenceChainIntegration:
    """Integration test: full pipeline from case data to HTML report."""

    def test_full_pipeline_produces_complete_report(self, tmp_path):
        template_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "reporting" / "templates"
        exporter = EvidenceChainPdfExporter(
            template_dir=template_dir,
            output_dir=tmp_path,
        )

        html_path = exporter.export_html(SAMPLE_CASE_DATA, tmp_path / "full_report.html")
        assert html_path.exists()

        content = html_path.read_text()

        required_sections = [
            "Evidence Report",
            "Overall Similarity Score",
            "Match Overview",
            "Similarity Heatmap",
            "AI Writing Analysis",
            "Code Comparison Evidence",
            "Report Integrity",
            "Investigator Signature",
        ]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

        assert "data:image/png;base64," in content
        assert len(content) > 10000
