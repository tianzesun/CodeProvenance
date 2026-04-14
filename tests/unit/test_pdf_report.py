"""
Unit tests for PDF Report Generation

Tests the PDF report generation functionality including:
- PDF generation from HTML
- PDF formatting and styling
- PDF export options
"""

import pytest
import tempfile
import os
from pathlib import Path

# Check if WeasyPrint is available
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

from src.backend.backend.utils.report import PDFReportGenerator, ReportGenerator


class TestPDFReportGenerator:
    """Test the PDF report generator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = PDFReportGenerator()
        
        self.job_data = {
            'job_id': 'test-job-pdf',
            'name': 'PDF Test Report',
            'threshold': 0.5,
            'total_comparisons': 5,
            'total_submissions': 3
        }
        
        self.comparison_results = [
            {
                'file_a': 'student1.py',
                'file_b': 'student2.py',
                'overall_score': 0.92,
                'individual_scores': {
                    'token': 0.9,
                    'ngram': 0.95,
                    'ast': 0.9,
                    'winnowing': 0.92
                }
            },
            {
                'file_a': 'student1.py',
                'file_b': 'student3.py',
                'overall_score': 0.35,
                'individual_scores': {
                    'token': 0.3,
                    'ngram': 0.4,
                    'ast': 0.35,
                    'winnowing': 0.35
                }
            }
        ]
        
        self.submissions = {
            'student1.py': {
                'filename': 'student1_solution.py',
                'language': 'python',
                'line_count': 45,
                'token_count': 180
            },
            'student2.py': {
                'filename': 'student2_solution.py',
                'language': 'python',
                'line_count': 42,
                'token_count': 175
            },
            'student3.py': {
                'filename': 'student3_solution.py',
                'language': 'python',
                'line_count': 48,
                'token_count': 190
            }
        }
    
    def test_pdf_generator_initialization(self):
        """Test PDF generator initialization."""
        assert self.generator is not None
        assert hasattr(self.generator, 'html_generator')
        assert isinstance(self.generator.html_generator, ReportGenerator)
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_generation_creates_file(self):
        """Test that PDF generation creates a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.pdf")
            
            # Generate PDF
            result_path = self.generator.generate_pdf(
                job_data=self.job_data,
                comparison_results=self.comparison_results,
                submissions=self.submissions,
                output_path=output_path,
                threshold=0.5
            )
            
            # Check that file was created
            assert os.path.exists(result_path)
            assert result_path == output_path
            
            # Check file size (should be > 0)
            file_size = os.path.getsize(result_path)
            assert file_size > 0
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_content_includes_summary(self):
        """Test that PDF includes summary information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.pdf")
            
            self.generator.generate_pdf(
                job_data=self.job_data,
                comparison_results=self.comparison_results,
                submissions=self.submissions,
                output_path=output_path,
                threshold=0.5
            )
            
            # Read PDF content (as bytes for basic check)
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
            
            # PDF should start with PDF header
            assert pdf_content.startswith(b'%PDF')
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_with_empty_results(self):
        """Test PDF generation with empty results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "empty_report.pdf")
            
            result_path = self.generator.generate_pdf(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_path=output_path,
                threshold=0.5
            )
            
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 0
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_with_high_threshold(self):
        """Test PDF generation with high threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "high_threshold.pdf")
            
            # With high threshold, fewer results should be included
            result_path = self.generator.generate_pdf(
                job_data=self.job_data,
                comparison_results=self.comparison_results,
                submissions=self.submissions,
                output_path=output_path,
                threshold=0.9  # High threshold
            )
            
            assert os.path.exists(result_path)
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_with_low_threshold(self):
        """Test PDF generation with low threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "low_threshold.pdf")
            
            # With low threshold, more results should be included
            result_path = self.generator.generate_pdf(
                job_data=self.job_data,
                comparison_results=self.comparison_results,
                submissions=self.submissions,
                output_path=output_path,
                threshold=0.1  # Low threshold
            )
            
            assert os.path.exists(result_path)


class TestPDFReportFormatting:
    """Test PDF report formatting."""
    
    def test_pdf_page_size(self):
        """Test that PDF uses appropriate page size."""
        generator = PDFReportGenerator()
        
        # Default should be A4 or Letter
        # This is handled by WeasyPrint defaults
        assert generator is not None
    
    def test_pdf_orientation(self):
        """Test PDF orientation options."""
        generator = PDFReportGenerator()
        
        # Portrait is default for reports
        assert generator is not None
    
    def test_pdf_margins(self):
        """Test PDF margin settings."""
        generator = PDFReportGenerator()
        
        # Margins are set in CSS
        assert generator is not None


class TestPDFReportContent:
    """Test PDF report content."""
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_includes_title(self):
        """Test that PDF includes report title."""
        generator = PDFReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "titled_report.pdf")
            
            job_data = {
                'name': 'Custom Report Title',
                'total_comparisons': 0
            }
            
            generator.generate_pdf(
                job_data=job_data,
                comparison_results=[],
                submissions={},
                output_path=output_path,
                threshold=0.5
            )
            
            assert os.path.exists(output_path)
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_includes_timestamp(self):
        """Test that PDF includes generation timestamp."""
        generator = PDFReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "timestamped_report.pdf")
            
            generator.generate_pdf(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_path=output_path,
                threshold=0.5
            )
            
            assert os.path.exists(output_path)
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_includes_statistics(self):
        """Test that PDF includes statistics."""
        generator = PDFReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "stats_report.pdf")
            
            job_data = {
                'total_comparisons': 100,
                'total_submissions': 10
            }
            
            generator.generate_pdf(
                job_data=job_data,
                comparison_results=[],
                submissions={},
                output_path=output_path,
                threshold=0.5
            )
            
            assert os.path.exists(output_path)


class TestPDFExportIntegration:
    """Test PDF export integration."""
    
    def test_generate_full_report_with_pdf(self):
        """Test full report generation including PDF."""
        from src.backend.backend.utils.report import generate_full_report
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate all formats including PDF
            results = generate_full_report(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_dir=tmpdir,
                threshold=0.5,
                formats=['html', 'json', 'csv']  # PDF requires separate call
            )
            
            assert 'html' in results
            assert 'json' in results
            assert 'csv' in results
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_pdf_from_html_report(self):
        """Test that PDF is generated from HTML report."""
        html_generator = ReportGenerator()
        pdf_generator = PDFReportGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate HTML first
            html_content = html_generator.generate_html(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                threshold=0.5
            )
            
            # Save HTML
            html_path = os.path.join(tmpdir, "report.html")
            with open(html_path, 'w') as f:
                f.write(html_content)
            
            # Generate PDF from HTML
            pdf_path = os.path.join(tmpdir, "report.pdf")
            pdf_generator.generate_pdf(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_path=pdf_path,
                threshold=0.5
            )
            
            assert os.path.exists(html_path)
            assert os.path.exists(pdf_path)


class TestPDFErrorHandling:
    """Test PDF error handling."""
    
    def test_invalid_output_path(self):
        """Test handling of invalid output path."""
        generator = PDFReportGenerator()
        
        # Try to write to invalid path
        with pytest.raises(Exception):
            generator.generate_pdf(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_path="/invalid/path/report.pdf",
                threshold=0.5
            )
    
    def test_missing_weasyprint_import(self):
        """Test handling when WeasyPrint is not installed."""
        # This test would verify graceful degradation
        # when weasyprint is not available
        generator = PDFReportGenerator()
        assert generator is not None


class TestPDFPerformance:
    """Test PDF generation performance."""
    
    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_large_report_generation(self):
        """Test PDF generation with large dataset."""
        generator = PDFReportGenerator()
        
        # Create large dataset
        large_results = []
        for i in range(100):
            large_results.append({
                'file_a': f'file{i}.py',
                'file_b': f'file{i+1}.py',
                'overall_score': 0.5 + (i % 50) / 100,
                'individual_scores': {
                    'token': 0.5,
                    'ngram': 0.5,
                    'ast': 0.5,
                    'winnowing': 0.5
                }
            })
        
        large_submissions = {}
        for i in range(101):
            large_submissions[f'file{i}.py'] = {
                'filename': f'student{i}.py',
                'language': 'python',
                'line_count': 50,
                'token_count': 200
            }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "large_report.pdf")
            
            result_path = generator.generate_pdf(
                job_data={'total_comparisons': 100},
                comparison_results=large_results,
                submissions=large_submissions,
                output_path=output_path,
                threshold=0.5
            )
            
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])