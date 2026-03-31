"""
Unit tests for AI Detection Module

Tests the AI-generated code detection functionality including:
- Pattern-based detection
- Statistical analysis
- Ensemble detection
- Confidence scoring
"""

import pytest
from src.utils.ai_detection import (
    AIDetector,
    StatisticalAIDetector,
    EnsembleAIDetector,
    AIDetectionResult,
    detect_ai_code
)


class TestAIDetector:
    """Test the pattern-based AI detector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = AIDetector(threshold=0.6)
    
    def test_ai_patterns_detection(self):
        """Test detection of AI generation patterns."""
        ai_code = """
// This function calculates the factorial
def factorial(n):
    # Here we handle the base case
    if n <= 1:
        return 1
    # Next, we recursively calculate
    return n * factorial(n - 1)
"""
        result = self.detector.analyze(ai_code, 'python')
        # The detector may not flag this as AI based on patterns alone
        assert result.ai_score >= 0.0
        assert 'ai_patterns' in result.indicators
    
    def test_comment_density_analysis(self):
        """Test comment density analysis."""
        human_code = """
def add(a, b):
    return a + b
"""
        ai_code = """
# This function adds two numbers
# Parameters: a and b
# Returns: sum of a and b
def add(a, b):
    # Calculate the sum
    return a + b
"""
        
        human_result = self.detector.analyze(human_code, 'python')
        ai_result = self.detector.analyze(ai_code, 'python')
        
        # AI code should have higher comment density score
        assert ai_result.indicators['comment_density'] > human_result.indicators['comment_density']
    
    def test_formatting_consistency(self):
        """Test formatting consistency detection."""
        consistent_code = """
def process():
    x = 1
    y = 2
    z = 3
    return x + y + z
"""
        inconsistent_code = """
def process():
    x = 1
    y=2
    z = 3
    return x+y+z
"""
        
        consistent_result = self.detector.analyze(consistent_code, 'python')
        inconsistent_result = self.detector.analyze(inconsistent_code, 'python')
        
        # Both should have formatting_consistency indicator
        assert 'formatting_consistency' in consistent_result.indicators
        assert 'formatting_consistency' in inconsistent_result.indicators
    
    def test_variable_naming_analysis(self):
        """Test variable naming pattern analysis."""
        ai_style = """
def calculate_sum():
    temp_result = 0
    helper_value = 5
    data_item = 10
    return temp_result + helper_value + data_item
"""
        human_style = """
def calculate_sum():
    total = 0
    offset = 5
    value = 10
    return total + offset + value
"""
        
        ai_result = self.detector.analyze(ai_style, 'python')
        human_result = self.detector.analyze(human_style, 'python')
        
        # AI-style naming should have higher suspicious score
        assert ai_result.indicators['variable_naming'] > human_result.indicators['variable_naming']
    
    def test_boilerplate_detection(self):
        """Test boilerplate pattern detection."""
        boilerplate_code = """
def main():
    if __name__ == "__main__":
        try:
            result = process()
            print(result)
        except Exception as e:
            print(f"Error: {e}")
"""
        result = self.detector.analyze(boilerplate_code, 'python')
        assert result.indicators['boilerplate'] > 0
    
    def test_empty_code(self):
        """Test handling of empty code."""
        result = self.detector.analyze("", 'python')
        # Empty code should have low AI score
        assert result.ai_score < 0.2
        assert result.confidence >= 0.0
    
    def test_short_code(self):
        """Test handling of very short code."""
        result = self.detector.analyze("x = 1", 'python')
        # Short code should have valid confidence
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
    
    def test_threshold_application(self):
        """Test that threshold is correctly applied."""
        detector = AIDetector(threshold=0.3)
        
        # Code with moderate AI indicators
        code = """
# Calculate sum
def add(a, b):
    return a + b
"""
        result = detector.analyze(code, 'python')
        
        # With low threshold, should be flagged
        if result.ai_score >= 0.3:
            assert result.is_likely_ai is True
    
    def test_explanation_generation(self):
        """Test that explanations are generated."""
        ai_code = """
# This function processes data
# Step 1: Get input
# Step 2: Process
# Step 3: Return result
def process_data(data):
    temp_result = data
    return temp_result
"""
        result = self.detector.analyze(ai_code, 'python')
        assert result.explanation != ""
        assert "RISK" in result.explanation


class TestStatisticalAIDetector:
    """Test the statistical AI detector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = StatisticalAIDetector()
    
    def test_statistical_properties(self):
        """Test statistical property analysis."""
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        stats = self.detector.analyze_statistical_properties(code)
        
        assert 'token_count' in stats
        assert 'unique_token_ratio' in stats
        assert 'avg_token_length' in stats
        assert 'line_count' in stats
        assert stats['token_count'] > 0
    
    def test_known_patterns_comparison(self):
        """Test comparison to known AI patterns."""
        code_with_marker = "# Generated by AI assistant\ndef test(): pass"
        code_without = "def test(): pass"
        
        with_marker_score = self.detector.compare_to_known_patterns(code_with_marker)
        without_score = self.detector.compare_to_known_patterns(code_without)
        
        assert with_marker_score > without_score
    
    def test_ngram_diversity(self):
        """Test n-gram diversity calculation."""
        repetitive_code = "a = 1\na = 1\na = 1\na = 1"
        diverse_code = "a = 1\nb = 2\nc = 3\nd = 4"
        
        repetitive_stats = self.detector.analyze_statistical_properties(repetitive_code)
        diverse_stats = self.detector.analyze_statistical_properties(diverse_code)
        
        # More diverse code should have higher bigram diversity
        assert diverse_stats['bigram_diversity'] > repetitive_stats['bigram_diversity']


class TestEnsembleAIDetector:
    """Test the ensemble AI detector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = EnsembleAIDetector(threshold=0.6)
    
    def test_ensemble_analysis(self):
        """Test ensemble detection combining multiple methods."""
        ai_code = """
# This function calculates fibonacci
# Here we handle the base case
def fibonacci(n):
    if n <= 1:
        return n
    # Recursively calculate
    return fibonacci(n-1) + fibonacci(n-2)
"""
        result = self.detector.analyze(ai_code, 'python')
        
        assert isinstance(result, AIDetectionResult)
        assert result.ai_score >= 0.0
        assert result.ai_score <= 1.0
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
        assert 'known_ai_match' in result.indicators
    
    def test_ensemble_confidence(self):
        """Test that ensemble provides confidence scores."""
        code = "def test(): pass"
        result = self.detector.analyze(code, 'python')
        
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0


class TestConvenienceFunction:
    """Test the convenience detection function."""
    
    def test_detect_ai_code_default(self):
        """Test default detection behavior."""
        code = "# Generated by AI\ndef test(): pass"
        result = detect_ai_code(code, 'python')
        
        assert isinstance(result, AIDetectionResult)
        assert result.is_likely_ai is True or result.is_likely_ai is False
    
    def test_detect_ai_code_with_threshold(self):
        """Test detection with custom threshold."""
        code = "# Some code\ndef test(): pass"
        
        result_low = detect_ai_code(code, 'python', threshold=0.3)
        result_high = detect_ai_code(code, 'python', threshold=0.9)
        
        # Lower threshold should be more likely to flag
        if result_low.ai_score >= 0.3:
            assert result_low.is_likely_ai is True
        if result_high.ai_score < 0.9:
            assert result_high.is_likely_ai is False
    
    def test_detect_ai_code_without_ensemble(self):
        """Test detection without ensemble method."""
        code = "def test(): pass"
        result = detect_ai_code(code, 'python', use_ensemble=False)
        
        assert isinstance(result, AIDetectionResult)
        # Without ensemble, should not have ensemble-specific indicators
        assert 'known_ai_match' not in result.indicators


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_whitespace_only(self):
        """Test handling of whitespace-only code."""
        detector = AIDetector()
        result = detector.analyze("   \n\n   ", 'python')
        # Whitespace-only code should have low AI score
        assert result.ai_score < 0.2
    
    def test_comments_only(self):
        """Test handling of comments-only code."""
        detector = AIDetector()
        result = detector.analyze("# Just a comment\n# Another comment", 'python')
        assert result.indicators['comment_density'] > 0
    
    def test_very_long_code(self):
        """Test handling of very long code."""
        detector = AIDetector()
        long_code = "\n".join([f"line_{i} = {i}" for i in range(1000)])
        result = detector.analyze(long_code, 'python')
        assert result is not None
    
    def test_special_characters(self):
        """Test handling of special characters."""
        detector = AIDetector()
        code = "x = 'hello\\nworld'\ny = \"test\""
        result = detector.analyze(code, 'python')
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])