"""Unit tests for AI Detector pipeline and reporting.

Tests the complete end-to-end pipeline and report generation.
"""


from src.backend.engines.ai.models import SignalScores
from src.backend.engines.ai.pipeline import (
    batch_detect_ai_code,
    compare_detection_results,
    compute_all_signals,
    detect_ai_generated_code,
    find_llm_pattern_lines,
    get_detection_summary,
)
from src.backend.engines.ai.reporting import (
    format_report_as_text,
    generate_agreement_analysis,
    generate_detection_report,
    generate_evidence_summary,
    generate_limitations_section,
    generate_overall_assessment,
    generate_recommendations,
    generate_signal_breakdown,
)
from tests.fixtures.ai_detector.fixtures import (
    get_ai_samples,
    get_edge_case_samples,
    get_human_samples,
)


# ============================================================================
# PIPELINE TESTS
# ============================================================================


class TestPipeline:
    """Tests for AI detection pipeline."""

    def test_compute_all_signals(self):
        """Test computing all signals."""
        code = "x = 1\ny = 2\nz = x + y"
        signals = compute_all_signals(code)

        assert isinstance(signals, SignalScores)
        assert all(0.0 <= s <= 1.0 for s in signals.to_dict().values())

    def test_compute_all_signals_with_human_code(self):
        """Test computing signals with human code."""
        human_samples = get_human_samples()

        for code in human_samples.values():
            signals = compute_all_signals(code)
            assert isinstance(signals, SignalScores)
            assert all(0.0 <= s <= 1.0 for s in signals.to_dict().values())

    def test_compute_all_signals_with_ai_code(self):
        """Test computing signals with AI code."""
        ai_samples = get_ai_samples()

        for code in ai_samples.values():
            signals = compute_all_signals(code)
            assert isinstance(signals, SignalScores)
            assert all(0.0 <= s <= 1.0 for s in signals.to_dict().values())

    def test_detect_ai_generated_code_human(self):
        """Test detection with human code."""
        code = """
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total
"""
        result = detect_ai_generated_code(code)

        assert result.ai_probability >= 0.0
        assert result.confidence >= 0.0
        assert result.risk_level in ["Very Low", "Low", "Moderate", "Elevated", "High"]

    def test_detect_ai_generated_code_ai(self):
        """Test detection with AI code."""
        code = '''
def process_data(input_data):
    """Process input data and return results."""
    result = []
    for item in input_data:
        processed_item = {
            'id': item.get('id'),
            'value': item.get('value', 0),
            'status': 'processed'
        }
        result.append(processed_item)
    return result
'''
        result = detect_ai_generated_code(code)

        assert result.ai_probability >= 0.0
        assert result.confidence >= 0.0
        assert result.risk_level in ["Very Low", "Low", "Moderate", "Elevated", "High"]

    def test_detect_ai_generated_code_with_evidence(self):
        """Test detection with evidence annotation."""
        code = """
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total
"""
        result = detect_ai_generated_code(code, include_evidence=True)

        assert isinstance(result.flagged_lines, list)
        assert all(isinstance(line, int) for line in result.flagged_lines)

    def test_find_llm_pattern_lines(self):
        """Test finding lines with LLM patterns."""
        code = '''
def process_data(input_data):
    """Process input data and return results."""
    result = []
    for item in input_data:
        if item is None:
            continue
        result.append(item)
    return result
'''
        flagged_lines = find_llm_pattern_lines(code)

        assert isinstance(flagged_lines, list)
        assert all(isinstance(line, int) for line in flagged_lines)
        assert len(flagged_lines) > 0

    def test_get_detection_summary(self):
        """Test getting detection summary."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)
        summary = get_detection_summary(result)

        assert "ai_probability" in summary
        assert "confidence" in summary
        assert "risk_level" in summary
        assert "is_high_confidence" in summary
        assert "is_medium_confidence" in summary
        assert "is_low_confidence" in summary

    def test_batch_detect_ai_code(self):
        """Test batch detection."""
        samples = {
            "sample1": "x = 1\ny = 2",
            "sample2": "def func():\n    return 42",
            "sample3": "class MyClass:\n    pass",
        }

        results = batch_detect_ai_code(samples)

        assert len(results) == 3
        assert all(r is not None for r in results.values())

    def test_compare_detection_results(self):
        """Test comparing detection results."""
        code1 = "x = 1\ny = 2"
        code2 = "x = 1\ny = 2\nz = x + y"

        result1 = detect_ai_generated_code(code1)
        result2 = detect_ai_generated_code(code2)

        comparison = compare_detection_results(result1, result2)

        assert "ai_probability_diff" in comparison
        assert "confidence_diff" in comparison
        assert "risk_level_same" in comparison


# ============================================================================
# REPORTING TESTS
# ============================================================================


class TestReporting:
    """Tests for report generation."""

    def test_generate_detection_report(self):
        """Test generating detection report."""
        code = "x = 1\ny = 2\nz = x + y"
        result = detect_ai_generated_code(code)

        report = generate_detection_report(result, code)

        assert "metadata" in report
        assert "executive_summary" in report
        assert "overall_assessment" in report
        assert "signal_breakdown" in report
        assert "agreement_analysis" in report
        assert "evidence_summary" in report
        assert "limitations" in report
        assert "recommendations" in report

    def test_generate_executive_summary(self):
        """Test generating executive summary."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        from src.backend.engines.ai.reporting import generate_executive_summary

        summary = generate_executive_summary(result)

        assert "overall_risk" in summary
        assert "ai_probability" in summary
        assert "confidence" in summary
        assert "summary" in summary
        assert "key_findings" in summary

    def test_generate_overall_assessment(self):
        """Test generating overall assessment."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        assessment = generate_overall_assessment(result)

        assert "risk_level" in assessment
        assert "ai_probability" in assessment
        assert "confidence" in assessment
        assert "confidence_level" in assessment
        assert "recommendation" in assessment

    def test_generate_signal_breakdown(self):
        """Test generating signal breakdown."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        from src.backend.engines.ai.reliability import assess_all_signal_reliabilities

        reliabilities = assess_all_signal_reliabilities(code)
        breakdown = generate_signal_breakdown(result.signals, reliabilities)

        assert len(breakdown) == 8
        for signal_name, signal_info in breakdown.items():
            assert "label" in signal_info
            assert "score" in signal_info
            assert "reliability" in signal_info
            assert "interpretation" in signal_info

    def test_generate_agreement_analysis(self):
        """Test generating agreement analysis."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        from src.backend.engines.ai.agreement import analyze_signal_agreement

        agreement = analyze_signal_agreement(result.signals)
        analysis = generate_agreement_analysis(agreement)

        assert "agreement_level" in analysis
        assert "agreement_score" in analysis
        assert "direction" in analysis
        assert "supporting_signals" in analysis
        assert "contradicting_signals" in analysis
        assert "interpretation" in analysis

    def test_generate_evidence_summary(self):
        """Test generating evidence summary."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        evidence = generate_evidence_summary(result, code)

        assert "indicators" in evidence
        assert "flagged_lines" in evidence
        assert "flagged_lines_count" in evidence
        assert "total_lines" in evidence
        assert "flagged_percentage" in evidence

    def test_generate_limitations_section(self):
        """Test generating limitations section."""
        limitations = generate_limitations_section()

        assert "title" in limitations
        assert "limitations" in limitations
        assert "recommendations" in limitations
        assert len(limitations["limitations"]) > 0
        assert len(limitations["recommendations"]) > 0

    def test_generate_recommendations(self):
        """Test generating recommendations."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        recommendations = generate_recommendations(result)

        assert "risk_level" in recommendations
        assert "recommendations" in recommendations
        assert len(recommendations["recommendations"]) > 0

    def test_format_report_as_text(self):
        """Test formatting report as text."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)

        report = generate_detection_report(result, code)
        text_report = format_report_as_text(report)

        assert isinstance(text_report, str)
        assert "AI DETECTION REPORT" in text_report
        assert "EXECUTIVE SUMMARY" in text_report
        assert "SIGNAL BREAKDOWN" in text_report
        assert "LIMITATIONS" in text_report


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestPipelineIntegration:
    """Integration tests for complete pipeline."""

    def test_pipeline_with_human_samples(self):
        """Test pipeline with human code samples."""
        human_samples = get_human_samples()

        for name, code in human_samples.items():
            result = detect_ai_generated_code(code)
            report = generate_detection_report(result, code)
            text_report = format_report_as_text(report)

            assert result.ai_probability >= 0.0
            assert result.confidence >= 0.0
            assert "AI DETECTION REPORT" in text_report

    def test_pipeline_with_ai_samples(self):
        """Test pipeline with AI code samples."""
        ai_samples = get_ai_samples()

        for name, code in ai_samples.items():
            result = detect_ai_generated_code(code)
            report = generate_detection_report(result, code)
            text_report = format_report_as_text(report)

            assert result.ai_probability >= 0.0
            assert result.confidence >= 0.0
            assert "AI DETECTION REPORT" in text_report

    def test_pipeline_with_edge_cases(self):
        """Test pipeline with edge case samples."""
        edge_cases = get_edge_case_samples()

        for name, code in edge_cases.items():
            result = detect_ai_generated_code(code)
            report = generate_detection_report(result, code)
            text_report = format_report_as_text(report)

            assert result.ai_probability >= 0.0
            assert result.confidence >= 0.0
            assert "AI DETECTION REPORT" in text_report

    def test_end_to_end_pipeline(self):
        """Test complete end-to-end pipeline."""
        code = """
def calculate_average(numbers):
    '''Calculate the average of a list of numbers.'''
    if not numbers:
        return 0
    
    total = sum(numbers)
    count = len(numbers)
    return total / count

# Test
values = [1, 2, 3, 4, 5]
avg = calculate_average(values)
print(f"Average: {avg}")
"""

        # Step 1: Detect
        result = detect_ai_generated_code(code)
        assert result is not None

        # Step 2: Generate report
        report = generate_detection_report(result, code)
        assert report is not None

        # Step 3: Format as text
        text_report = format_report_as_text(report)
        assert text_report is not None

        # Step 4: Verify report contents
        assert "AI DETECTION REPORT" in text_report
        assert "EXECUTIVE SUMMARY" in text_report
        assert "SIGNAL BREAKDOWN" in text_report
        assert "AGREEMENT ANALYSIS" in text_report
        assert "EVIDENCE SUMMARY" in text_report
        assert "LIMITATIONS" in text_report
        assert "RECOMMENDATIONS" in text_report

    def test_batch_pipeline(self):
        """Test batch detection pipeline."""
        samples = {
            "human1": "x = 1\ny = 2",
            "human2": "def func():\n    return 42",
            "ai1": 'def process(data):\n    """Process data."""\n    return [x * 2 for x in data]',
        }

        results = batch_detect_ai_code(samples)

        assert len(results) == 3
        for name, result in results.items():
            assert result is not None
            assert result.ai_probability >= 0.0
            assert result.confidence >= 0.0


# ============================================================================
# REPORT QUALITY TESTS
# ============================================================================


class TestReportQuality:
    """Tests for report quality and completeness."""

    def test_report_contains_all_sections(self):
        """Test that report contains all required sections."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)
        report = generate_detection_report(result, code)

        required_sections = [
            "metadata",
            "executive_summary",
            "overall_assessment",
            "signal_breakdown",
            "agreement_analysis",
            "evidence_summary",
            "limitations",
            "recommendations",
        ]

        for section in required_sections:
            assert section in report, f"Missing section: {section}"

    def test_report_text_is_readable(self):
        """Test that text report is readable."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)
        report = generate_detection_report(result, code)
        text_report = format_report_as_text(report)

        # Check for key sections
        assert "=" * 80 in text_report
        assert "EXECUTIVE SUMMARY" in text_report
        assert "SIGNAL BREAKDOWN" in text_report
        assert "LIMITATIONS" in text_report

        # Check that it's not empty
        assert len(text_report) > 500

    def test_report_has_actionable_recommendations(self):
        """Test that report has actionable recommendations."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)
        report = generate_detection_report(result, code)

        recommendations = report["recommendations"]["recommendations"]

        assert len(recommendations) > 0
        assert all(isinstance(r, str) for r in recommendations)
        assert all(len(r) > 10 for r in recommendations)

    def test_report_explains_limitations(self):
        """Test that report explains limitations."""
        code = "x = 1\ny = 2"
        result = detect_ai_generated_code(code)
        report = generate_detection_report(result, code)

        limitations = report["limitations"]["limitations"]

        assert len(limitations) > 0
        assert all(isinstance(limitation, str) for limitation in limitations)
        assert all(len(limitation) > 20 for limitation in limitations)
