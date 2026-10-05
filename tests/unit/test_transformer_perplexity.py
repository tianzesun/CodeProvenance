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
        """Test that perplexity can be computed for code long enough to score.

        ``compute_perplexity`` returns ``None`` below ``MIN_TOKENS`` (32) rather
        than a fabricated number, so a real value needs a real amount of code.
        """
        code = "\n".join(
            f"def helper_{i}(value):\n    total = value + {i}\n    return total"
            for i in range(8)
        )
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
        """Too-short input reports "unavailable" instead of a made-up number.

        The old behaviour returned a hardcoded ``100.0`` for empty input, which
        is indistinguishable from a genuinely measured perplexity. Callers then
        treated unavailability as "human", so a short or unscoreable submission
        silently read as clean. ``None`` forces them to say so instead.
        """
        assert compute_perplexity("") is None
        assert compute_perplexity("x = 1") is None

    def test_short_code_is_reported_unavailable_not_scored(self):
        """``compute_ai_score`` mirrors that: available=False, ai_score=None."""
        result = compute_ai_score("def tiny(): pass")

        assert result["available"] is False
        assert result["ai_score"] is None
        assert result["raw_perplexity"] is None
        assert "unavailable" in result["interpretation"].lower()

    def test_batch_analysis(self):
        """Test batch processing of multiple samples."""
        analyzer = TransformerPerplexityAnalyzer()
        codes = [f"def fn_{i}(x):\n    return x + {i}\n" for i in range(6)]
        results = analyzer.batch_analyze(codes)
        assert len(results) == 6
        assert all("ai_score" in r for r in results)
        # ai_score is None when the sample could not be scored; where it is a
        # number it must be a probability.
        for r in results:
            assert r["ai_score"] is None or 0 <= r["ai_score"] <= 1

    def test_analyzer_singleton(self):
        """Test that analyzer is cached (singleton pattern)."""
        from src.backend.engines.ai_detection import get_analyzer

        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()
        assert analyzer1 is analyzer2  # Same instance

    def test_normalized_score_structure(self):
        """Test that normalized score has expected structure."""
        code = "\n".join(
            f"def fn_{i}(value):\n    return value * {i + 1}" for i in range(8)
        )
        result = compute_ai_score(code)

        assert "raw_perplexity" in result
        assert "ai_score" in result
        assert "interpretation" in result
        assert "token_count" in result

        assert 0 <= result["ai_score"] <= 1
        assert result["token_count"] > 0
