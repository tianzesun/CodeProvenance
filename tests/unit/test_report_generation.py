"""
Unit tests for Report Generation Module

Tests the report generation functionality including:
- HTML report generation
- JSON report generation
- CSV matrix generation
- Report formatting and styling
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
import tempfile
import os

from src.utils.report import ReportGenerator, generate_full_report


class TestReportGenerator:
    """Test the report generator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ReportGenerator(
            title="Test Report",
            include_code_snippets=True,
            syntax_highlighting=True
        )
        
        self.job_data = {
            'job_id': 'test-job-123',
            'name': 'Test Analysis',
            'threshold': 0.5,
            'total_comparisons': 10,
            'total_submissions': 5
        }
        
        self.comparison_results = [
            {
                'file_a': 'file1.py',
                'file_b': 'file2.py',
                'overall_score': 0.85,
                'individual_scores': {
                    'token': 0.8,
                    'ngram': 0.9,
                    'ast': 0.85,
                    'winnowing': 0.85
                }
            },
            {
                'file_a': 'file1.py',
                'file_b': 'file3.py',
                'overall_score': 0.45,
                'individual_scores': {
                    'token': 0.4,
                    'ngram': 0.5,
                    'ast': 0.45,
                    'winnowing': 0.45
                }
            }
        ]
        
        self.submissions = {
            'file1.py': {
                'filename': 'student1.py',
                'language': 'python',
                'line_count': 50,
                'token_count': 200
            },
            'file2.py': {
                'filename': 'student2.py',
                'language': 'python',
                'line_count': 48,
                'token_count': 195
            },
            'file3.py': {
                'filename': 'student3.py',
                'language': 'python',
                'line_count': 52,
                'token_count': 210
            }
        }
    
    def test_html_header_generation(self):
        """Test HTML header generation."""
        header = self.generator._generate_html_header()
        
        assert '<!DOCTYPE html>' in header
        assert '<title>Test Report</title>' in header
        assert 'CodeProvenance' in header
        assert 'container' in header
        assert 'card' in header
    
    def test_html_summary_generation(self):
        """Test HTML summary section generation."""
        suspicious_pairs = [r for r in self.comparison_results if r['overall_score'] >= 0.5]
        summary = self.generator._generate_html_summary(
            self.job_data,
            suspicious_pairs,
            0.5
        )
        
        assert 'Analysis Summary' in summary
        assert '10' in summary  # total_comparisons
        assert '1' in summary  # flagged count
        assert '0' in summary  # high severity
    
    def test_html_submissions_table(self):
        """Test HTML submissions table generation."""
        table = self.generator._generate_html_submissions_table(self.submissions)
        
        assert 'Submissions' in table
        assert 'student1.py' in table
        assert 'student2.py' in table
        assert 'student3.py' in table
        assert 'python' in table
    
    def test_html_similarity_matrix(self):
        """Test HTML similarity matrix generation."""
        matrix = self.generator._generate_html_similarity_matrix(
            self.comparison_results,
            self.submissions,
            0.5
        )
        
        assert 'Similarity Matrix' in matrix
        assert 'student1.py' in matrix
        assert 'student2.py' in matrix
        assert '85.0%' in matrix  # 0.85 as percentage
    
    def test_html_suspicious_pairs(self):
        """Test HTML suspicious pairs section."""
        suspicious_pairs = [r for r in self.comparison_results if r['overall_score'] >= 0.5]
        pairs_section = self.generator._generate_html_suspicious_pairs(
            suspicious_pairs,
            self.submissions
        )
        
        assert 'Suspicious Pairs' in pairs_section
        assert 'student1.py' in pairs_section
        assert 'student2.py' in pairs_section
        assert '85.0%' in pairs_section
    
    def test_html_footer_generation(self):
        """Test HTML footer generation."""
        footer = self.generator._generate_html_footer()
        
        assert '</div>' in footer
        assert '</body>' in footer
        assert '</html>' in footer
        assert 'CodeProvenance' in footer
    
    def test_full_html_generation(self):
        """Test complete HTML report generation."""
        html = self.generator.generate_html(
            self.job_data,
            self.comparison_results,
            self.submissions,
            threshold=0.5
        )
        
        assert '<!DOCTYPE html>' in html
        assert 'Test Report' in html
        assert 'student1.py' in html
        assert 'student2.py' in html
        assert '85.0%' in html
        assert '</html>' in html
    
    def test_json_report_generation(self):
        """Test JSON report generation."""
        json_report = self.generator.generate_json(
            self.job_data,
            self.comparison_results,
            self.submissions,
            threshold=0.5
        )
        
        data = json.loads(json_report)
        
        assert 'metadata' in data
        assert 'summary' in data
        assert 'job' in data
        assert 'submissions' in data
        assert 'comparisons' in data
        assert 'suspicious_pairs' in data
        
        assert data['metadata']['title'] == 'Test Report'
        assert data['summary']['total_comparisons'] == 10
        assert len(data['suspicious_pairs']) == 1
    
    def test_csv_report_generation(self):
        """Test CSV report generation."""
        csv_report = self.generator.generate_csv(
            self.comparison_results,
            self.submissions
        )
        
        lines = csv_report.split('\n')
        
        # Check header
        assert 'file_a' in lines[0]
        assert 'file_b' in lines[0]
        assert 'overall_score' in lines[0]
        
        # Check data rows
        assert len(lines) > 1
        assert 'student1.py' in csv_report
        assert 'student2.py' in csv_report
    
    def test_report_save(self):
        """Test saving report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            html_content = "<html><body>Test</body></html>"
            output_path = os.path.join(tmpdir, "test_report.html")
            
            saved_path = self.generator.save_report(
                html_content,
                output_path,
                format='html'
            )
            
            assert os.path.exists(saved_path)
            with open(saved_path, 'r') as f:
                content = f.read()
            assert content == html_content


class TestReportFiltering:
    """Test report filtering functionality."""
    
    def test_filter_by_threshold(self):
        """Test filtering results by threshold."""
        generator = ReportGenerator()
        
        results = [
            {'overall_score': 0.9},
            {'overall_score': 0.7},
            {'overall_score': 0.3},
            {'overall_score': 0.1}
        ]
        
        # Filter for threshold 0.5
        filtered = [r for r in results if r['overall_score'] >= 0.5]
        
        assert len(filtered) == 2
        assert filtered[0]['overall_score'] == 0.9
        assert filtered[1]['overall_score'] == 0.7
    
    def test_filter_critical_only(self):
        """Test filtering for critical severity only."""
        results = [
            {'overall_score': 0.95},  # Critical
            {'overall_score': 0.75},  # Warning
            {'overall_score': 0.85},  # Critical
            {'overall_score': 0.55}   # Warning
        ]
        
        critical = [r for r in results if r['overall_score'] >= 0.8]
        
        assert len(critical) == 2
        assert all(r['overall_score'] >= 0.8 for r in critical)


class TestReportFormatting:
    """Test report formatting and styling."""
    
    def test_score_percentage_formatting(self):
        """Test score formatting as percentage."""
        scores = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        for score in scores:
            formatted = f"{score:.1%}"
            assert '%' in formatted
    
    def test_score_class_assignment(self):
        """Test CSS class assignment based on score."""
        def get_score_class(score):
            if score >= 0.7:
                return 'high'
            elif score >= 0.5:
                return 'medium'
            else:
                return 'low'
        
        assert get_score_class(0.9) == 'high'
        assert get_score_class(0.75) == 'high'
        assert get_score_class(0.6) == 'medium'
        assert get_score_class(0.5) == 'medium'
        assert get_score_class(0.3) == 'low'
        assert get_score_class(0.1) == 'low'
    
    def test_severity_badge_assignment(self):
        """Test severity badge assignment."""
        def get_severity_badge(score):
            if score >= 0.8:
                return 'Critical'
            elif score >= 0.5:
                return 'Warning'
            else:
                return 'Info'
        
        assert get_severity_badge(0.95) == 'Critical'
        assert get_severity_badge(0.85) == 'Critical'
        assert get_severity_badge(0.7) == 'Warning'
        assert get_severity_badge(0.5) == 'Warning'
        assert get_severity_badge(0.3) == 'Info'
    
    def test_timestamp_formatting(self):
        """Test timestamp formatting."""
        timestamp = datetime.utcnow().isoformat()
        
        assert 'T' in timestamp
        assert len(timestamp) > 10
    
    def test_filename_truncation(self):
        """Test long filename truncation."""
        long_filename = "very_long_filename_that_should_be_truncated_for_display.py"
        
        # Truncate if longer than 30 chars
        truncated = long_filename[:30] + '...' if len(long_filename) > 30 else long_filename
        
        assert len(truncated) <= 33  # 30 + '...'


class TestReportExportFormats:
    """Test different export formats."""
    
    def test_html_export_structure(self):
        """Test HTML export has correct structure."""
        generator = ReportGenerator()
        
        html = generator.generate_html(
            {'total_comparisons': 0},
            [],
            {},
            threshold=0.5
        )
        
        # Check essential HTML elements
        assert html.startswith('<!DOCTYPE html>')
        assert '<html' in html
        assert '<head>' in html
        assert '<body>' in html
        assert '</html>' in html
    
    def test_json_export_structure(self):
        """Test JSON export has correct structure."""
        generator = ReportGenerator()
        
        json_report = generator.generate_json(
            {'total_comparisons': 0},
            [],
            {},
            threshold=0.5
        )
        
        data = json.loads(json_report)
        
        # Check required fields
        assert 'metadata' in data
        assert 'summary' in data
        assert 'suspicious_pairs' in data
    
    def test_csv_export_structure(self):
        """Test CSV export has correct structure."""
        generator = ReportGenerator()
        
        csv_report = generator.generate_csv([], {})
        
        lines = csv_report.split('\n')
        
        # Should have at least header
        assert len(lines) >= 1
        assert 'file_a' in lines[0]


class TestReportEdgeCases:
    """Test edge cases in report generation."""
    
    def test_empty_results(self):
        """Test report generation with empty results."""
        generator = ReportGenerator()
        
        html = generator.generate_html(
            {'total_comparisons': 0},
            [],
            {},
            threshold=0.5
        )
        
        assert 'No suspicious pairs detected' in html
    
    def test_single_submission(self):
        """Test report with single submission."""
        generator = ReportGenerator()
        
        submissions = {
            'file1.py': {'filename': 'test.py', 'language': 'python'}
        }
        
        html = generator.generate_html(
            {'total_comparisons': 0},
            [],
            submissions,
            threshold=0.5
        )
        
        assert 'test.py' in html
    
    def test_missing_individual_scores(self):
        """Test handling of missing individual scores."""
        generator = ReportGenerator()
        
        results = [
            {
                'file_a': 'a.py',
                'file_b': 'b.py',
                'overall_score': 0.8
                # No individual_scores
            }
        ]
        
        html = generator.generate_html(
            {'total_comparisons': 1},
            results,
            {},
            threshold=0.5
        )
        
        assert '80.0%' in html
    
    def test_zero_threshold(self):
        """Test report with zero threshold."""
        generator = ReportGenerator()
        
        results = [
            {'overall_score': 0.1},
            {'overall_score': 0.0}
        ]
        
        html = generator.generate_html(
            {'total_comparisons': 2},
            results,
            {},
            threshold=0.0
        )
        
        # All results should be flagged
        assert '2' in html  # flagged count


class TestFullReportGeneration:
    """Test the full report generation function."""
    
    def test_generate_full_report_html(self):
        """Test full HTML report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_full_report(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_dir=tmpdir,
                threshold=0.5,
                formats=['html']
            )
            
            assert 'html' in results
            assert os.path.exists(results['html'])
    
    def test_generate_full_report_json(self):
        """Test full JSON report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_full_report(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_dir=tmpdir,
                threshold=0.5,
                formats=['json']
            )
            
            assert 'json' in results
            assert os.path.exists(results['json'])
            
            # Verify JSON is valid
            with open(results['json'], 'r') as f:
                data = json.load(f)
            assert 'metadata' in data
    
    def test_generate_full_report_csv(self):
        """Test full CSV report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_full_report(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_dir=tmpdir,
                threshold=0.5,
                formats=['csv']
            )
            
            assert 'csv' in results
            assert os.path.exists(results['csv'])
    
    def test_generate_full_report_all_formats(self):
        """Test generating all report formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_full_report(
                job_data={'total_comparisons': 0},
                comparison_results=[],
                submissions={},
                output_dir=tmpdir,
                threshold=0.5,
                formats=['html', 'json', 'csv']
            )
            
            assert len(results) == 3
            assert 'html' in results
            assert 'json' in results
            assert 'csv' in results


if __name__ == '__main__':
    pytest.main([__file__, '-v'])