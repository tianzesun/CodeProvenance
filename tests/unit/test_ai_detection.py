"""Unit tests for AI Detection Engine."""
import pytest
from src.backend.backend.engines.similarity.ai_detection import AIDetectionEngine


@pytest.fixture
def detector() -> AIDetectionEngine:
    """Create a detector instance for testing."""
    return AIDetectionEngine()


class TestAIDetectionEngine:
    """Test suite for AIDetectionEngine."""
    
    def test_short_code_returns_error(self, detector: AIDetectionEngine) -> None:
        """Test that very short code returns an error."""
        result = detector.analyze("x = 1")
        assert result["ai_probability"] == 0.0
        assert result["error"] == "Code too short for analysis"
    
    def test_empty_code_returns_error(self, detector: AIDetectionEngine) -> None:
        """Test that empty code returns an error."""
        result = detector.analyze("")
        assert result["ai_probability"] == 0.0
        assert result["error"] == "Code too short for analysis"
    
    def test_returns_valid_structure(self, detector: AIDetectionEngine) -> None:
        """Test that analysis returns expected structure."""
        code = """
def hello():
    print("Hello, world!")
    
hello()
"""
        result = detector.analyze(code)
        assert "ai_probability" in result
        assert "confidence" in result
        assert "signals" in result
        assert "indicators" in result
        assert isinstance(result["ai_probability"], float)
        assert 0.0 <= result["ai_probability"] <= 1.0
    
    def test_perplexity_calculation(self, detector: AIDetectionEngine) -> None:
        """Test perplexity score calculation."""
        # Code with low entropy (repetitive) should score higher
        repetitive_code = """
x = 1
x = 1
x = 1
x = 1
x = 1
"""
        result = detector.analyze(repetitive_code)
        assert result["signals"]["perplexity"] > 0.5  # High AI score for repetitive
        
        # Code with high entropy (varied) should score lower
        varied_code = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total

result = calculate_sum([1, 2, 3, 4, 5])
print(f"Sum: {result}")
"""
        result = detector.analyze(varied_code)
        assert result["signals"]["perplexity"] < 0.5  # Lower AI score
    
    def test_burstiness_calculation(self, detector: AIDetectionEngine) -> None:
        """Test burstiness score calculation."""
        # Uniform code should have high AI score
        uniform_code = """
line1 = "hello"
line2 = "world"
line3 = "test"
line4 = "code"
line5 = "done"
"""
        result = detector.analyze(uniform_code)
        assert result["signals"]["burstiness"] > 0.3  # More uniform = higher AI score
    
    def test_stylometry_formal_comments(self, detector: AIDetectionEngine) -> None:
        """Test stylometry detection of formal comment patterns."""
        # Code with formal, title-case comments (AI-like)
        formal_comments_code = """
# Initialize The Main Function
def main():
    # Here Is The Processing Logic
    result = process_data()
    # Return The Final Output
    return result
"""
        result = detector.analyze(formal_comments_code)
        assert result["signals"]["stylometry"] > 0.3  # Higher AI score for formal comments
    
    def test_pattern_repetition_detection(self, detector: AIDetectionEngine) -> None:
        """Test pattern repetition detection."""
        # Code with LLM-like patterns
        llm_pattern_code = """
# Let us implement the solution
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def process_data(data):
    # Here is the processing logic
    result = data.process()
    return result
"""
        result = detector.analyze(llm_pattern_code)
        assert result["signals"]["pattern_repetition"] > 0.2
    
    def test_combine_signals(self, detector: AIDetectionEngine) -> None:
        """Test signal combination produces valid probability."""
        signals = {
            "perplexity": 0.7,
            "burstiness": 0.6,
            "stylometry": 0.5,
            "pattern_repetition": 0.4,
        }
        combined = detector._combine_signals(signals)
        assert 0.0 <= combined <= 1.0
    
    def test_confidence_calculation(self, detector: AIDetectionEngine) -> None:
        """Test confidence calculation based on signal agreement."""
        # High agreement (all signals similar) should give high confidence
        agreeing_signals = {
            "perplexity": 0.7,
            "burstiness": 0.7,
            "stylometry": 0.7,
            "pattern_repetition": 0.7,
        }
        confidence = detector._calculate_confidence(agreeing_signals)
        assert confidence > 0.7  # High confidence for agreement
        
        # Low agreement (signals vary) should give lower confidence
        disagreeing_signals = {
            "perplexity": 0.9,
            "burstiness": 0.1,
            "stylometry": 0.5,
            "pattern_repetition": 0.3,
        }
        confidence = detector._calculate_confidence(disagreeing_signals)
        assert confidence < 0.7  # Lower confidence for disagreement
    
    def test_identify_indicators(self, detector: AIDetectionEngine) -> None:
        """Test indicator identification."""
        code = """
result = process_data()
result = calculate_sum()
result = handle_input()
result = compute_output()
"""
        indicators = detector._identify_indicators(code)
        assert any("generic" in ind.lower() for ind in indicators)
    
    def test_tokenize_code(self, detector: AIDetectionEngine) -> None:
        """Test code tokenization."""
        code = "def hello_world(): return 42"
        tokens = detector._tokenize_code(code)
        assert "def" in tokens
        assert "hello_world" in tokens
        assert "return" in tokens
        assert "42" in tokens
    
    def test_language_parameter(self, detector: AIDetectionEngine) -> None:
        """Test that language parameter is accepted and returned."""
        code = "func main() { fmt.Println(\"Hello\") }"
        result = detector.analyze(code, language="go")
        assert result["language"] == "go"
    
    def test_realistic_human_code(self, detector: AIDetectionEngine) -> None:
        """Test detection on realistic human-written code."""
        human_code = """
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

# Test the function
for i in range(10):
    print(fibonacci(i), end=' ')
"""
        result = detector.analyze(human_code)
        # Human code should have lower AI probability
        assert result["ai_probability"] < 0.5
        assert result["confidence"] > 0.3
    
    def test_realistic_ai_like_code(self, detector: AIDetectionEngine) -> None:
        """Test detection on code that looks AI-generated."""
        ai_like_code = """
# Let us implement a comprehensive solution for data processing

import numpy as np
import pandas as pd
from typing import List, Dict, Optional

def process_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    \"\"\"Process the input data and return the results.
    
    This function takes a list of dictionaries and processes them
    to produce a comprehensive output.
    \"\"\"
    # Initialize the result dictionary
    result = {}
    
    # Process each item in the data
    for item in data:
        # Calculate the processed value
        processed_value = item.get('value', 0) * 2
        
        # Add to result
        result[item.get('key', 'unknown')] = processed_value
    
    # Return the final result
    return result

# Here is the main execution
if __name__ == "__main__":
    # Create sample data
    sample_data = [
        {'key': 'a', 'value': 1},
        {'key': 'b', 'value': 2},
    ]
    
    # Process and display results
    output = process_data(sample_data)
    print(f"Results: {output}")
"""
        result = detector.analyze(ai_like_code)
        # AI-like code should have higher AI probability
        assert result["ai_probability"] > 0.3
        assert len(result["indicators"]) > 0