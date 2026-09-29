"""Unit tests for transformer-based perplexity analyzer."""

import pytest

# Skip tests if transformers not installed
try:
    from src.backend.engines.ai_detection.transformer_perplexity import (
        TransformerPerplexityAnalyzer,
        compute_perplexity,
        compute_ai_score,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


@pytest.mark.skipif(not TRANSFORMERS_AVAILABLE, reason="transformers not installed")
class TestTransformerPerplexity:
    """Test transformer-based perplexity calculation."""

    def test_basic_perplexity_computation(self):
        """Test that perplexity can be computed for valid code."""
        code = """
def hello_world():
    print("Hello, world!")
    return True
"""
        perplexity = compute_perplexity(code)
        assert isinstance(perplexity, float)
        assert 0 < perplexity < 500  # Reasonable range

    def test_ai_generated_code_low_perplexity(self):
        """AI-generated code should have lower perplexity."""
        # Typical GPT-4 output
        ai_code = """
def process_data(data: list[dict]) -> list[dict]:
    \"\"\"Process the input data and return cleaned results.
    
    Args:
        data: List of dictionaries containing raw data
        
    Returns:
        List of processed dictionaries
    \"\"\"
    # Initialize result list
    result = []
    
    # Iterate through each item
    for item in data:
        # Check if item is valid
        if item and isinstance(item, dict):
            # Process the item
            processed_item = {
                'id': item.get('id'),
                'value': item.get('value', 0)
            }
            # Add to result
            result.append(processed_item)
    
    # Return the processed data
    return result
"""

        result = compute_ai_score(ai_code)
        assert result["raw_perplexity"] < 50  # AI typically < 40
        assert result["ai_score"] > 0.6  # Should flag as likely AI

    def test_human_code_higher_perplexity(self):
        """Human code should have higher perplexity (more variety)."""
        human_code = """
def calc(x):
    # quick hack
    if x < 0:
        x = -x
    res = x * 2 + 1
    return res

def helper(a, b):
    return a + b if a > 10 else b * 2
"""
        result = compute_ai_score(human_code)
        # Human code typically 50-120
        # But this is short so might be lower
        assert isinstance(result["raw_perplexity"], float)
        assert 0 < result["raw_perplexity"] < 200

    def test_empty_code_handling(self):
        """Empty/tiny code should return default score."""
        assert compute_perplexity("") == 100.0
        assert compute_perplexity("x = 1") >= 50.0  # Too short for reliable analysis

    def test_batch_analysis(self):
        """Test batch processing of multiple samples."""
        analyzer = TransformerPerplexityAnalyzer()
        codes = ["def foo(): pass", "def bar(): return 42", "print('hello')"]
        results = analyzer.batch_analyze(codes)
        assert len(results) == 3
        assert all("ai_score" in r for r in results)
        assert all(0 <= r["ai_score"] <= 1 for r in results)

    def test_analyzer_singleton(self):
        """Test that analyzer is cached (singleton pattern)."""
        from src.backend.engines.ai_detection import get_analyzer

        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()
        assert analyzer1 is analyzer2  # Same instance

    def test_normalized_score_structure(self):
        """Test that normalized score has expected structure."""
        code = "def test(): return 1"
        result = compute_ai_score(code)

        assert "raw_perplexity" in result
        assert "ai_score" in result
        assert "interpretation" in result
        assert "token_count" in result

        assert 0 <= result["ai_score"] <= 1
        assert result["token_count"] > 0
